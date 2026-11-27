"""What every family of endpoints shares: the refusal a handler raises, how it reads a field of the request, the publisher's scan, and the shape of a handler."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult

#: An endpoint's handler: the quilt, the endpoint's name and the decoded request; it answers what is served as JSON, or raises `ApiError`.
Handler = Callable[[Path, str, dict[str, Any]], dict[str, Any]]

#: A publisher's own scan, offered to its handlers by `offer_scan`: `loom serve` answers with the scan its last publication made while no scan input has changed since, and None otherwise.
_SCANS: dict[Path, Callable[[], ScanResult | None]] = {}


def offer_scan(root: Path, provider: Callable[[], ScanResult | None]) -> None:
    """Let the handlers for `root` read `provider`'s scan instead of scanning again; `loom serve` offers its own."""
    _SCANS[root.resolve()] = provider


def _scan(root: Path) -> ScanResult:
    """The quilt's scan: the publisher's own while it is current, else a fresh one."""
    from loom.cli._quilt import open_scan

    provider = _SCANS.get(root.resolve())
    kept = provider() if provider is not None else None
    return kept if kept is not None else open_scan(str(root))


class ApiError(Exception):
    """A request loom refused, with the code a viewer shows, the status it gets, and for a form the reason for each field it refused."""

    def __init__(self, code: str, message: str, status: int = 400, fields: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields or {}

    def answer(self) -> dict[str, Any]:
        """The JSON body a refusal is served as."""
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.fields:
            error["fields"] = self.fields
        return {"error": error}


def refusal(exc: Exception) -> ApiError:
    """A refusal of loom's as the write API answers it: `no-reviewer` (409) for a write that has no name to be recorded under (`NoNameError`), else `refused` (400)."""
    from loom.errors import NoNameError

    if isinstance(exc, NoNameError):
        return ApiError("no-reviewer", str(exc), status=409)
    return ApiError("refused", str(exc))


def _str(body: dict[str, Any], name: str, *, required: bool = False) -> str | None:
    value = body.get(name)
    if value is None or value == "":
        if required:
            raise ApiError("missing-field", f"{name} is required")
        return None
    if not isinstance(value, str):
        raise ApiError("bad-field", f"{name} must be a string")
    return value


def plain(serve: Callable[[Path, dict[str, Any]], dict[str, Any]]) -> Handler:
    """The handler of a function that serves one endpoint, and so takes no endpoint's name."""

    def handler(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        return serve(root, body)

    return handler


def said(serve: Callable[[Path, str, dict[str, Any]], str]) -> Handler:
    """The handler of a function that returns only what to say: the answer is `{"ok": True, "result": <that>}`."""

    def handler(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "result": serve(root, endpoint, body)}

    return handler
