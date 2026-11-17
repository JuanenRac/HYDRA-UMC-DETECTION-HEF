# =============================================================================
# HYDRA-UMC-DETECTION-HEF - tests/test_checksum_cache.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The hashes of model files that did not change can be kept, and only when the service is asked to."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from hydra_umc_detection_hef.compatibility import LoadOutcome, safe_load
from hydra_umc_detection_hef.registry import ChecksumCache, ModelEntry, read_verified


def _entry(name: str, data: bytes) -> ModelEntry:
    return ModelEntry(
        name="det", version="1.0.0", task="detection", hailo_arch="hailo8", input_shape=(8, 8, 3), classes=("a",), hef_path=name,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def test_the_second_check_of_an_unchanged_file_does_not_hash_it_again(tmp_path: Path) -> None:
    (tmp_path / "m.hef").write_bytes(b"model" * 100)
    entry, cache = _entry("m.hef", b"model" * 100), ChecksumCache()
    assert read_verified(entry, tmp_path, cache=cache, want_data=False) == (True, None)
    assert read_verified(entry, tmp_path, cache=cache, want_data=False) == (True, None)
    assert (cache.hits, cache.misses) == (1, 1)


def test_a_changed_file_is_hashed_again_and_refused(tmp_path: Path) -> None:
    path = tmp_path / "m.hef"
    path.write_bytes(b"model" * 100)
    entry, cache = _entry("m.hef", b"model" * 100), ChecksumCache()
    assert read_verified(entry, tmp_path, cache=cache, want_data=False)[0] is True
    path.write_bytes(b"other" * 100)                                   # same size, new modification time
    os.utime(path, ns=(1, 1))
    assert read_verified(entry, tmp_path, cache=cache, want_data=False)[0] is False
    path.write_bytes(b"model" * 100 + b"x")                            # another size
    assert read_verified(entry, tmp_path, cache=cache, want_data=False)[0] is False
    assert cache.hits == 0


def test_the_cache_is_not_used_when_the_bytes_are_wanted_or_there_is_no_cache(tmp_path: Path) -> None:
    (tmp_path / "m.hef").write_bytes(b"model")
    entry, cache = _entry("m.hef", b"model"), ChecksumCache()
    assert read_verified(entry, tmp_path, cache=cache) == (True, b"model")
    assert (cache.hits, cache.misses) == (0, 0)
    assert read_verified(entry, tmp_path, want_data=False) == (True, b"model")


def test_the_cache_holds_at_most_its_limit_and_one_state_per_file(tmp_path: Path) -> None:
    cache = ChecksumCache(max_entries=2)
    for index in range(3):
        (tmp_path / f"{index}.hef").write_bytes(bytes([index]) * 10)
        cache.sha256(tmp_path / f"{index}.hef")
    assert len(cache._known) == 2
    path = tmp_path / "2.hef"
    path.write_bytes(b"new content")
    cache.sha256(path)
    assert len([key for key in cache._known if key[0] == str(path)]) == 1


def test_safe_load_uses_the_cache_only_when_it_is_given_and_still_refuses_a_bad_file(tmp_path: Path) -> None:
    path = tmp_path / "m.hef"
    path.write_bytes(b"model")
    entry, cache = _entry("m.hef", b"model"), ChecksumCache()
    assert safe_load(entry, tmp_path, "hailo8", checksum_cache=cache).outcome is LoadOutcome.READY
    assert safe_load(entry, tmp_path, "hailo8", checksum_cache=cache).outcome is LoadOutcome.READY
    assert cache.hits == 1
    kept = safe_load(entry, tmp_path, "hailo8", keep_bytes=True, checksum_cache=cache)
    assert kept.data == b"model" and cache.hits == 1                   # the bytes that are handed over are always the bytes that were hashed
    path.write_bytes(b"MODEL")
    os.utime(path, ns=(2, 2))
    assert safe_load(entry, tmp_path, "hailo8", checksum_cache=cache).outcome is LoadOutcome.REJECTED_CHECKSUM_MISMATCH
