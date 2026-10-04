"""Loopback-only HTTP transport for optional local inference runtimes."""

import ipaddress
import json
import urllib.error
import urllib.request
from typing import Mapping, Protocol
from urllib.parse import urlsplit


class JsonTransport(Protocol):
    def request(self, method: str, path: str, payload: Mapping[str, object] | None = None) -> Mapping[str, object]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class LoopbackJsonTransport:
    """Network disabled until explicitly enabled; no proxies or redirects."""

    def __init__(self, base_url: str, *, network_enabled: bool = False, timeout_seconds: float = 10.0):
        parsed = urlsplit(base_url)
        try:
            host = ipaddress.ip_address(parsed.hostname or "")
            port = parsed.port
        except ValueError as exc:
            raise ValueError("local model URL must use a literal loopback IP and valid port") from exc
        if (
            parsed.scheme != "http"
            or not host.is_loopback
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or port is None
        ):
            raise ValueError("local model URL must be plain HTTP on a loopback IP and explicit port")
        if not isinstance(network_enabled, bool):
            raise TypeError("network_enabled must be boolean")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be in (0, 60]")
        self._base_url = base_url.rstrip("/")
        self._network_enabled = network_enabled
        self._timeout_seconds = timeout_seconds
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def request(self, method: str, path: str, payload: Mapping[str, object] | None = None) -> Mapping[str, object]:
        if not self._network_enabled:
            raise PermissionError("local model network access is disabled")
        if method not in ("GET", "POST") or not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path:
            raise ValueError("invalid local model request")
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._base_url + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with self._opener.open(request, timeout=self._timeout_seconds) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("local model response exceeds size limit")
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("local model response must be a JSON object")
        return decoded
