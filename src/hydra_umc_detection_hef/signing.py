# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/signing.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Ed25519 signature of the registry file.

The registry says which compiled model a node may load and which checksum it must have; whoever can edit it can swap a
model. A detached signature (`registry.json.sig`, 64 bytes written as hex) made with a key that stays off the node lets a
node that only holds the public key refuse a registry that was not signed by the owner of the private key.

The check is off until a public key is configured (`--public-key` or HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE); once it is
configured a missing or wrong signature is an error, never a warning. A key file holds 32 bytes, raw or as 64 hex digits.
Signing needs the optional `cryptography` package; nothing else in the project does.
"""
from __future__ import annotations

import binascii
import os
from pathlib import Path

from .registry import RegistryError

PUBLIC_KEY_ENV = "HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE"
SIGNATURE_SUFFIX = ".sig"


def signature_path(registry_path: Path) -> Path:
    return registry_path.with_name(registry_path.name + SIGNATURE_SUFFIX)


def _ed25519():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:
        raise RegistryError("signing the registry needs the optional 'cryptography' package (pip install cryptography)") from exc
    return ed25519, InvalidSignature


def _decode_hex(text: str, size: int, what: str) -> bytes:
    try:
        data = binascii.unhexlify(text.strip())
    except (binascii.Error, ValueError) as exc:
        raise RegistryError(f"{what} is not valid hexadecimal") from exc
    if len(data) != size:
        raise RegistryError(f"{what} must be {size} bytes")
    return data


def read_key(path: Path) -> bytes:
    """A 32-byte key from a file that holds the raw bytes or 64 hexadecimal digits. Never printed."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise RegistryError(f"could not read the key file {path}: {exc}") from exc
    if len(data) == 32:
        return data
    return _decode_hex(data.decode("ascii", errors="replace"), 32, f"key file {path}")


def generate_keypair(private_path: Path, public_path: Path) -> None:
    """Write a new key pair; refuses to overwrite either file. The private file is created readable by its owner only."""
    ed25519, _ = _ed25519()
    from cryptography.hazmat.primitives import serialization

    for path in (private_path, public_path):
        if Path(path).exists():
            raise RegistryError(f"{path} already exists - refusing to overwrite a key")
    key = ed25519.Ed25519PrivateKey.generate()
    raw_private = key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    raw_public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    descriptor = os.open(str(private_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(raw_private.hex() + "\n")
    Path(public_path).write_text(raw_public.hex() + "\n", encoding="ascii")


def sign_registry(registry_path: Path, private_key_file: Path) -> Path:
    """Write `<registry>.sig` for the registry as it is now; sign again after every `registry add`."""
    ed25519, _ = _ed25519()
    try:
        data = Path(registry_path).read_bytes()
    except OSError as exc:
        raise RegistryError(f"could not read registry {registry_path}: {exc}") from exc
    key = ed25519.Ed25519PrivateKey.from_private_bytes(read_key(private_key_file))
    target = signature_path(Path(registry_path))
    target.write_text(key.sign(data).hex() + "\n", encoding="ascii")
    return target


def verify_registry_bytes(data: bytes, registry_path: Path, public_key_file: Path) -> None:
    """Raise RegistryError unless `<registry>.sig` is a valid signature of exactly these bytes."""
    ed25519, InvalidSignature = _ed25519()
    sig_file = signature_path(Path(registry_path))
    try:
        sig_text = sig_file.read_text(encoding="ascii")
    except (OSError, UnicodeDecodeError) as exc:
        raise RegistryError(f"registry {registry_path} has no readable signature {sig_file.name}: {exc}") from exc
    signature = _decode_hex(sig_text, 64, f"signature {sig_file.name}")
    public = ed25519.Ed25519PublicKey.from_public_bytes(read_key(public_key_file))
    try:
        public.verify(signature, data)
    except InvalidSignature as exc:
        raise RegistryError(f"the signature of registry {registry_path} does not match its content and the public key") from exc


def resolve_public_key(explicit: str | None) -> Path | None:
    """The public key file asked for on the command line, else the one in the environment, else none (check off)."""
    value = explicit or os.environ.get(PUBLIC_KEY_ENV) or ""
    return Path(value) if value.strip() else None
