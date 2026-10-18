import hashlib
import dataclasses
import json

import pytest

from hydra_umc_detection_hef.registry import (
    RegistryError,
    add_entry,
    compute_sha256,
    duplicate_versions,
    find_latest,
    load_registry,
    load_registry_or_empty,
    verify_checksum,
    write_registry,
)


def _write_registry(path, entries):
    path.write_text(json.dumps(entries), encoding="utf-8")


def _entry(name="pcb-defect", version="0.1.0", task="detection", sha256="a" * 64, hailo_arch="hailo8"):
    return {
        "name": name, "version": version, "task": task,
        "input_shape": [640, 640, 3], "classes": ["solder_bridge", "missing_component"],
        "hef_path": f"{name}-{version}.hef", "sha256": sha256, "hailo_arch": hailo_arch,
    }


def _parsed_entry(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    return load_registry(reg_path)[0]


def test_load_registry_valid(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    entries = load_registry(reg_path)
    assert len(entries) == 1
    assert entries[0].name == "pcb-defect"
    assert entries[0].version_tuple == (0, 1, 0)


def test_load_registry_missing_field(tmp_path):
    reg_path = tmp_path / "registry.json"
    bad = _entry()
    del bad["sha256"]
    _write_registry(reg_path, [bad])
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_bad_version(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="v1")])
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_bad_sha256(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(sha256="not-hex")])
    with pytest.raises(RegistryError):
        load_registry(reg_path)


# regression: bool is a subclass of int in Python, so
# isinstance(True, int) is True and True <= 0 is False (True == 1) - a
# dimension of `True` used to sail through this check as a "valid
# positive integer" instead of being rejected.
def test_load_registry_rejects_a_boolean_input_shape_dimension(tmp_path):
    reg_path = tmp_path / "registry.json"
    bad = _entry()
    bad["input_shape"] = [True, 640, 3]
    _write_registry(reg_path, [bad])
    with pytest.raises(RegistryError, match="input_shape"):
        load_registry(reg_path)


def test_load_registry_unknown_hailo_arch(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo9-doesnt-exist")])
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_rejects_absolute_hef_path(tmp_path):
    reg_path = tmp_path / "registry.json"
    bad = _entry()
    bad["hef_path"] = str(tmp_path / "outside" / "evil.hef")
    _write_registry(reg_path, [bad])
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_accepts_every_known_hailo_arch(tmp_path):
    from hydra_umc_detection_hef.registry import KNOWN_HAILO_ARCHS

    for arch in sorted(KNOWN_HAILO_ARCHS):
        reg_path = tmp_path / f"registry-{arch}.json"
        _write_registry(reg_path, [_entry(hailo_arch=arch)])
        entries = load_registry(reg_path)
        assert entries[0].hailo_arch == arch


def test_load_registry_not_a_list(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_rejects_non_object_entry_and_non_text_fields(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, ["not an entry"])
    with pytest.raises(RegistryError, match="JSON object"):
        load_registry(reg_path)

    invalid = _entry()
    invalid["name"] = 7
    _write_registry(reg_path, [invalid])
    with pytest.raises(RegistryError, match="name"):
        load_registry(reg_path)


def test_load_registry_malformed_json(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_duplicate_versions(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="0.1.0"), _entry(version="0.1.0"), _entry(version="0.2.0")])
    entries = load_registry(reg_path)
    dupes = duplicate_versions(entries)
    assert dupes == [("pcb-defect", "0.1.0")]


def test_find_latest_picks_highest_version(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="0.1.0"), _entry(version="0.10.0"), _entry(version="0.2.0")])
    entries = load_registry(reg_path)
    latest = find_latest(entries, "pcb-defect")
    assert latest.version == "0.10.0"


def test_find_latest_filters_by_task(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(task="detection", version="0.2.0"), _entry(task="pose", version="0.9.0")])
    entries = load_registry(reg_path)
    latest = find_latest(entries, "pcb-defect", task="pose")
    assert latest.version == "0.9.0"


def test_find_latest_no_match_returns_none(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    entries = load_registry(reg_path)
    assert find_latest(entries, "nonexistent-model") is None


def test_compute_sha256(tmp_path):
    f = tmp_path / "model.hef"
    f.write_bytes(b"fake hef bytes")
    expected = hashlib.sha256(b"fake hef bytes").hexdigest()
    assert compute_sha256(f) == expected


def test_verify_checksum_match(tmp_path):
    content = b"fake hef bytes"
    digest = hashlib.sha256(content).hexdigest()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(content)

    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(sha256=digest)])
    entry = load_registry(reg_path)[0]

    assert verify_checksum(entry, models_dir) is True


def test_verify_checksum_mismatch(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"different bytes")

    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(sha256="a" * 64)])
    entry = load_registry(reg_path)[0]

    assert verify_checksum(entry, models_dir) is False


def test_verify_checksum_missing_file_returns_none(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    entry = load_registry(reg_path)[0]

    assert verify_checksum(entry, tmp_path / "nowhere") is None


def test_verify_checksum_rejects_path_traversal(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    outside = tmp_path / "outside.hef"
    outside.write_bytes(b"secret bytes outside models_dir")

    # the parser already refuses "..", so build the entry by hand to keep
    # exercising the second line of defence in verify_checksum
    entry = dataclasses.replace(_parsed_entry(tmp_path), hef_path="../../../../outside.hef")

    with pytest.raises(RegistryError):
        verify_checksum(entry, models_dir)


def test_verify_checksum_rejects_traversal_into_prefix_matching_sibling(tmp_path):
    # A naive str.startswith(str(models_dir)) containment check would
    # wrongly let this through, since "models_evil" starts with "models".
    # The real fix resolves both paths and checks real containment.
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    evil_sibling = tmp_path / "models_evil"
    evil_sibling.mkdir()
    (evil_sibling / "secret.hef").write_bytes(b"secret bytes in sibling dir")

    entry = dataclasses.replace(_parsed_entry(tmp_path), hef_path="../models_evil/secret.hef")

    with pytest.raises(RegistryError):
        verify_checksum(entry, models_dir)


def test_verify_checksum_allows_legitimate_relative_subdirectory(tmp_path):
    content = b"fake hef bytes"
    digest = hashlib.sha256(content).hexdigest()
    models_dir = tmp_path / "models"
    (models_dir / "v1").mkdir(parents=True)
    (models_dir / "v1" / "pcb-defect-0.1.0.hef").write_bytes(content)

    reg_path = tmp_path / "registry.json"
    good = _entry(sha256=digest)
    good["hef_path"] = "v1/pcb-defect-0.1.0.hef"
    _write_registry(reg_path, [good])
    entry = load_registry(reg_path)[0]

    assert verify_checksum(entry, models_dir) is True


# ---------------------------------------------------------------------------
# add_entry() / write_registry() / load_registry_or_empty()
# ---------------------------------------------------------------------------
# Found while auditing the code: today the
# registry JSON is hand-edited, including the sha256 that
# verify_checksum() only ever checks, never generates.


def test_load_registry_or_empty_returns_empty_list_for_a_missing_file(tmp_path):
    assert load_registry_or_empty(tmp_path / "does-not-exist.json") == []


def test_load_registry_or_empty_still_loads_a_real_file(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    assert len(load_registry_or_empty(reg_path)) == 1


def test_add_entry_hashes_the_real_file_not_a_caller_supplied_digest(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    content = b"real fake hef bytes"
    (models_dir / "pcb-defect-0.2.0.hef").write_bytes(content)

    entry = add_entry(
        [],
        models_dir=models_dir,
        name="pcb-defect",
        version="0.2.0",
        task="detection",
        input_shape=(640, 640, 3),
        classes=("solder_bridge", "missing_component"),
        hef_path="pcb-defect-0.2.0.hef",
        hailo_arch="hailo8",
    )

    assert entry.sha256 == hashlib.sha256(content).hexdigest()
    assert entry.name == "pcb-defect"
    assert entry.version == "0.2.0"


def test_add_entry_rejects_a_missing_file(tmp_path):
    with pytest.raises(RegistryError):
        add_entry(
            [],
            models_dir=tmp_path,
            name="pcb-defect",
            version="0.2.0",
            task="detection",
            input_shape=(640, 640, 3),
            classes=("a",),
            hef_path="this-file-does-not-exist.hef",
            hailo_arch="hailo8",
        )


def test_add_entry_rejects_a_duplicate_name_and_version(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"content")
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    existing_entries = load_registry(reg_path)

    with pytest.raises(RegistryError):
        add_entry(
            existing_entries,
            models_dir=models_dir,
            name="pcb-defect",
            version="0.1.0",
            task="detection",
            input_shape=(640, 640, 3),
            classes=("a",),
            hef_path="pcb-defect-0.1.0.hef",
            hailo_arch="hailo8",
        )


def test_add_entry_rejects_path_traversal_the_same_way_verify_checksum_does(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    outside = tmp_path / "outside.hef"
    outside.write_bytes(b"secret bytes outside models_dir")

    with pytest.raises(RegistryError):
        add_entry(
            [],
            models_dir=models_dir,
            name="pcb-defect",
            version="0.1.0",
            task="detection",
            input_shape=(640, 640, 3),
            classes=("a",),
            hef_path="../outside.hef",
            hailo_arch="hailo8",
        )


def test_add_entry_rejects_an_invalid_field_the_same_way_load_registry_does(tmp_path):
    # add_entry() runs the assembled entry through the exact same
    # _parse_entry() gate load_registry() does - not a separate,
    # potentially divergent set of rules.
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"content")

    with pytest.raises(RegistryError):
        add_entry(
            [],
            models_dir=models_dir,
            name="pcb-defect",
            version="0.1.0",
            task="detection",
            input_shape=(640, 640, 3),
            classes=("a",),
            hef_path="pcb-defect-0.1.0.hef",
            hailo_arch="not-a-real-hailo-arch",
        )


def test_write_registry_round_trips_through_load_registry(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"content")

    entry = add_entry(
        [],
        models_dir=models_dir,
        name="pcb-defect",
        version="0.1.0",
        task="detection",
        input_shape=(640, 640, 3),
        classes=("solder_bridge", "missing_component"),
        hef_path="pcb-defect-0.1.0.hef",
        hailo_arch="hailo8",
    )

    reg_path = tmp_path / "registry.json"
    write_registry(reg_path, [entry])

    reloaded = load_registry(reg_path)
    assert reloaded == [entry]


def _entry_objects(tmp_path, version):
    reg = tmp_path / "source.json"
    _write_registry(reg, [_entry(version=version)])
    return load_registry(reg)


def test_write_registry_round_trips_and_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "registry.json"
    write_registry(path, _entry_objects(tmp_path, "0.1.0"))
    assert [e.version for e in load_registry(path)] == ["0.1.0"]
    assert sorted(p.name for p in tmp_path.iterdir() if p.name != "source.json") == ["registry.json"]


def test_a_write_that_fails_midway_keeps_the_previous_registry(tmp_path, monkeypatch):
    # the registry is the trust source for every model a deployment loads: a power cut or a
    # full disk while it is rewritten used to leave a truncated file and no registry at all
    import os

    path = tmp_path / "registry.json"
    write_registry(path, _entry_objects(tmp_path, "0.1.0"))
    before = path.read_bytes()
    new_entries = _entry_objects(tmp_path, "0.2.0")

    def interrupted(descriptor):
        raise OSError("disk full")

    monkeypatch.setattr(os, "fsync", interrupted)
    with pytest.raises(OSError):
        write_registry(path, new_entries)
    monkeypatch.undo()

    assert path.read_bytes() == before
    assert [e.version for e in load_registry(path)] == ["0.1.0"]
    assert sorted(p.name for p in tmp_path.iterdir() if p.name != "source.json") == ["registry.json"]


def test_a_hef_path_with_parent_segments_is_rejected_when_the_registry_is_read(tmp_path):
    reg_path = tmp_path / "registry.json"
    bad = _entry()
    bad["hef_path"] = "../../etc/passwd"
    _write_registry(reg_path, [bad])
    with pytest.raises(RegistryError, match="'..'"):
        load_registry(reg_path)


def test_repeated_class_labels_are_rejected(tmp_path):
    reg_path = tmp_path / "registry.json"
    bad = _entry()
    bad["classes"] = ["ok", "ok"]
    _write_registry(reg_path, [bad])
    with pytest.raises(RegistryError, match="classes"):
        load_registry(reg_path)


def test_two_entries_for_the_same_version_with_different_files_are_ambiguous(tmp_path):
    from hydra_umc_detection_hef.registry import AmbiguousModelError

    reg_path = tmp_path / "registry.json"
    other = _entry()
    other["hef_path"] = "other.hef"
    other["sha256"] = "b" * 64
    _write_registry(reg_path, [_entry(), other])
    entries = load_registry(reg_path)
    with pytest.raises(AmbiguousModelError):
        find_latest(entries, "pcb-defect")


def test_a_specific_version_can_be_asked_for(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="0.1.0"), _entry(version="0.2.0")])
    entries = load_registry(reg_path)
    assert find_latest(entries, "pcb-defect").version == "0.2.0"
    assert find_latest(entries, "pcb-defect", version="0.1.0").version == "0.1.0"
    assert find_latest(entries, "pcb-defect", version="9.9.9") is None


def test_concurrent_registry_adds_do_not_lose_entries(tmp_path):
    import threading

    from hydra_umc_detection_hef.registry import add_entry, load_registry_or_empty, registry_lock

    models = tmp_path / "models"
    models.mkdir()
    for i in range(6):
        (models / f"m{i}.hef").write_bytes(b"model %d" % i)
    reg_path = tmp_path / "registry.json"

    def add(i):
        with registry_lock(reg_path):
            entries = load_registry_or_empty(reg_path)
            entries.append(add_entry(
                entries, models_dir=models, name=f"m{i}", version="0.1.0", task="detection",
                input_shape=(640, 640, 3), classes=("a",), hef_path=f"m{i}.hef", hailo_arch="hailo8",
            ))
            write_registry(reg_path, entries)

    threads = [threading.Thread(target=add, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(e.name for e in load_registry(reg_path)) == [f"m{i}" for i in range(6)]
    assert not list(tmp_path.glob("*.tmp")) and not list(tmp_path.glob("*.lock"))
