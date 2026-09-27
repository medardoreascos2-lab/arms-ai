"""Explicit Windows-local V3 provisioning. Import/startup never creates authority.

Only protected key bytes reach disk. Callers must run as the NinjaTrader user.
The CLI provisions authority only; publish_config is an explicit backend API.
"""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import uuid

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3

HEADER = b"ARMS_DPAPI_CURRENT_USER_V3\n"
ENTROPY = b"arms.native.authority.v3"
DOMAIN = b"arms.native.configuration.v3\0"
SCHEMA = "ARMS_CONTROLLED_CONFIG_V3"
PATH_FIELDS = ("command_directory", "activation_directory", "state_directory", "reconciliation_directory")


def authority_root() -> Path:
    if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
        raise ValueError("Windows local application data required")
    return safe_path(Path(os.environ["LOCALAPPDATA"]) / "ARMS-AI" / "sim-native-v3", authority=True)


def safe_path(value, *, authority=False) -> Path:
    path = Path(value)
    if not path.is_absolute() or str(path).startswith("\\\\"):
        raise ValueError("absolute local path required")
    repo = Path(__file__).resolve().parents[2]
    resolved = path.resolve()
    if authority and (resolved == repo or repo in resolved.parents):
        raise ValueError("authority/runtime path cannot be inside repository")
    if authority and (any("onedrive" in part.lower() for part in path.parts) or "custom" in [p.lower() for p in path.parts]):
        raise ValueError("cloud/Custom storage prohibited")
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or getattr(parent, "is_junction", lambda: False)()
                or getattr(parent.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError("redirected path prohibited")
    return resolved


def dpapi(data: bytes, *, protect: bool) -> bytes:
    """CurrentUser only; CRYPTPROTECT_UI_FORBIDDEN, never LOCAL_MACHINE."""
    if os.name != "nt" or not data or len(data) > 65536:
        raise ValueError("invalid Windows DPAPI input")
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    def blob(value):
        buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
        return Blob(len(value), buffer), buffer
    source, source_buffer = blob(data)
    entropy, entropy_buffer = blob(ENTROPY)
    output = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    method = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    method.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    method.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        if not method(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(output)):
            raise ValueError("DPAPI CurrentUser operation failed")
        return ctypes.string_at(output.data, output.size)
    finally:
        if output.data:
            ctypes.memset(output.data, 0, output.size)
            kernel.LocalFree(output.data)
        ctypes.memset(source_buffer, 0, len(data))
        ctypes.memset(entropy_buffer, 0, len(ENTROPY))


def _restrict_directory(path: Path):
    # Protected DACL: the effective Windows user and SYSTEM only. No key in argv.
    encoded_path = base64.b64encode(str(path).encode("utf-8")).decode("ascii")
    script = """$ErrorActionPreference='Stop'
$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('%s'))
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$existing=Get-Acl -LiteralPath $p
$rules=@($existing.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
$expected=@($sid.Value,'S-1-5-18')
$private=$existing.AreAccessRulesProtected -and $existing.GetOwner([Security.Principal.SecurityIdentifier]).Value -eq $sid.Value -and $rules.Count -eq 2
foreach($rule in $rules) {
 if($rule.IdentityReference.Value -notin $expected -or $rule.AccessControlType -ne 'Allow' -or $rule.FileSystemRights -ne 'FullControl' -or $rule.InheritanceFlags -ne 'ContainerInherit,ObjectInherit' -or $rule.PropagationFlags -ne 'None' -or $rule.IsInherited) { $private=$false }
}
if($private -and @($rules.IdentityReference.Value | Select-Object -Unique).Count -eq 2) { exit 0 }
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
foreach($identity in @($sid,(New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
 $rule=New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
 $acl.AddAccessRule($rule)
}
$acl.SetOwner($sid)
Set-Acl -LiteralPath $p -AclObject $acl
""" % encoded_path
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
        base64.b64encode(script.encode("utf-16-le")).decode("ascii")], capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError("private authority directory permissions unavailable")


def _atomic(path: Path, data: bytes, *, create_only=False):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if create_only:
            os.rename(temporary, path)  # Windows rename never replaces an existing target.
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_authority(root=None) -> bytes:
    path = safe_path(root, authority=True) if root is not None else authority_root()
    artifact = safe_path(path / "authority.dpapi", authority=True)
    if artifact.stat().st_size > 65536:
        raise ValueError("oversized authority encoding")
    wire = artifact.read_bytes()
    if not wire.startswith(HEADER) or len(wire) > 65536:
        raise ValueError("invalid authority encoding")
    key = dpapi(wire[len(HEADER):], protect=False)
    if len(key) != 32:
        raise ValueError("invalid authority length")
    return key


def authority_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()


def provision_authority(root=None) -> str:
    """Operator initiated, create once, no implicit rotation or repair."""
    path = safe_path(root, authority=True) if root is not None else authority_root()
    if (path / "authority.dpapi").exists():
        return authority_id(load_authority(path))
    path.mkdir(parents=True, exist_ok=True)
    _restrict_directory(path)
    key = secrets.token_bytes(32)
    protected = HEADER + dpapi(key, protect=True)
    try:
        _atomic(path / "authority.dpapi", protected, create_only=True)
    except FileExistsError:
        pass  # A concurrent explicit provisioner won; never replace its identity.
    return authority_id(load_authority(path))


def canonical(values: dict[str, str]) -> bytes:
    if type(values) is not dict or any(type(k) is not str or type(v) is not str for k, v in values.items()):
        raise ValueError("flat string configuration required")
    return json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def read_authenticated_config(root=None):
    """Authenticate exact canonical bytes; freshness is checked by verify_config."""
    path = safe_path(root, authority=True) if root is not None else authority_root()
    key = load_authority(path)
    payload = safe_path(path / "controlled-v3-config.json", authority=True).read_bytes()
    signature = safe_path(path / "controlled-v3-config.sig", authority=True).read_bytes()
    if not hmac.compare_digest(signature, hmac.new(key, DOMAIN + payload, hashlib.sha256).hexdigest().encode("ascii")):
        raise ValueError("configuration signature invalid")
    values = json.loads(payload)
    if canonical(values) != payload or values.get("authority_id") != authority_id(key):
        raise ValueError("configuration canonical bytes or authority invalid")
    generation = values.get("configuration_generation", "")
    if (not generation.isascii() or not generation.isdecimal() or int(generation) < 1
            or str(int(generation)) != generation):
        raise ValueError("configuration generation invalid")
    return values


def verify_config(*, binding, paths, risk_version, configuration_generation, now_us, root=None):
    """Read-only verification; never renews, provisions, or repairs artifacts."""
    values = read_authenticated_config(root)
    binding.manager()
    expected = {**binding.claims(), **{k: str(safe_path(paths[k], authority=True)) for k in PATH_FIELDS},
        "schema": SCHEMA, "version": "3", "configuration_generation": str(configuration_generation),
        "native_account": binding.native_account_name, "provider": binding.provider,
        "instrument": binding.instrument, "runtime_generation": str(binding.runtime_generation), "risk_version": risk_version}
    if set(values) != set(expected) | {"authority_id", "issued_at", "issued_us", "expires_us"} or any(values.get(k) != v for k,v in expected.items()):
        raise ValueError("configuration pins or schema mismatch")
    if (len({values[k].casefold() for k in PATH_FIELDS}) != 4
            or any(not Path(values[k]).is_dir() for k in PATH_FIELDS)):
        raise ValueError("configuration directories invalid")
    issued, expires = int(values["issued_us"]), int(values["expires_us"])
    if (type(now_us) is not int or not 0 < issued <= now_us < expires
            or str(issued) != values["issued_us"] or str(expires) != values["expires_us"]
            or values["issued_at"] != (datetime(1970, 1, 1, tzinfo=timezone.utc)+timedelta(microseconds=issued)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")):
        raise ValueError("configuration validity invalid or expired")
    return values


def publish_config(*, binding: SimNativeAccountV3, configuration_generation: int,
                   risk_version: str, paths: dict, issued_us: int, expires_us: int, root=None,
                   require_next_generation=False):
    """Explicit authoritative backend call; no defaults for freshness or identity.

    Expected generation/fingerprint/account/path pins must also be configured on
    the existing native owner. Republishing a generation with new content fails.
    """
    if type(binding) is not SimNativeAccountV3 or type(configuration_generation) is not int or configuration_generation < 1:
        raise ValueError("explicit binding and configuration generation required")
    binding.manager()
    if (type(issued_us) is not int or type(expires_us) is not int or not 0 < issued_us < expires_us
            or type(risk_version) is not str or not risk_version or set(paths) != set(PATH_FIELDS)):
        raise ValueError("explicit configuration policy required")
    checked = {name: str(safe_path(paths[name])) for name in PATH_FIELDS}
    if len(set(v.casefold() for v in checked.values())) != len(PATH_FIELDS) or any(not Path(v).is_dir() for v in checked.values()):
        raise ValueError("distinct existing runtime directories required")
    path = safe_path(root, authority=True) if root is not None else authority_root()
    key = load_authority(path)  # Never provisions implicitly.
    values = {**binding.claims(), **checked, "schema": SCHEMA, "configuration_generation": str(configuration_generation),
        "authority_id": authority_id(key), "native_account": binding.native_account_name, "provider": binding.provider,
        "instrument": binding.instrument, "runtime_generation": str(binding.runtime_generation), "risk_version": risk_version,
        "version": "3", "issued_at": (datetime(1970, 1, 1, tzinfo=timezone.utc)+timedelta(microseconds=issued_us)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "issued_us": str(issued_us), "expires_us": str(expires_us)}
    payload = canonical(values)
    signature = hmac.new(key, DOMAIN + payload, hashlib.sha256).hexdigest().encode("ascii")
    # Exclusive publisher lock also serializes generation checks.
    lock = path / "configuration-publish.lock"
    stream = lock.open("xb")
    try:
        config = path / "controlled-v3-config.json"
        sig = path / "controlled-v3-config.sig"
        generation = 0
        if config.exists() or sig.exists():
            old = config.read_bytes()
            if not hmac.compare_digest(sig.read_bytes(), hmac.new(key, DOMAIN + old, hashlib.sha256).hexdigest().encode()):
                raise ValueError("existing configuration is inconsistent; explicit recovery required")
            generation = int(json.loads(old)["configuration_generation"])
            if generation >= configuration_generation:
                if old == payload:
                    return values
                raise ValueError("configuration generation cannot be reused or rolled back")
        if require_next_generation and configuration_generation != generation + 1:
            raise ValueError("next explicit configuration must use prior generation plus one")
        _atomic(config, payload)
        _atomic(sig, signature)  # Readers reject a torn pair; signature commits exact bytes.
    finally:
        stream.close()
        lock.unlink()
    return values


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Explicit CurrentUser V3 authority provisioning; never enables execution")
    parser.add_argument("operation", choices=["provision", "identity"])
    args = parser.parse_args()
    print(provision_authority() if args.operation == "provision" else authority_id(load_authority()))
