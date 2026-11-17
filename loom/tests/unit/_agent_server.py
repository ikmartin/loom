"""`loom mcp` started as a process, as an agent's app starts it, and spoken to in raw JSON-RPC lines, so a test can signal it between requests and read what it left in the quilt."""

from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from tests.helpers import PATIENCE

#: What a client that sends no `initialize` puts in every request's `_meta`, as Claude Code 2.1 does.
CLIENT = {"name": "claude-code", "title": "Claude Code", "version": "2.1.312"}
META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": CLIENT,
    "io.modelcontextprotocol/clientCapabilities": {},
}


def _signals_as_an_app_leaves_them() -> None:
    """In the child, the signals the server ends on at their defaults, as an app's spawn leaves them (libuv, under Node, resets each): a suite started as a shell's background job has SIGINT ignored, and the server keeps a signal it inherits ignored."""
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, signal.SIG_DFL)


class AgentServer:
    """One `loom mcp --as NAME` process in quilt `q`, with `env` over the test's own environment, less the conversation an agent running the tests may be in."""

    def __init__(self, q: Path, name: str = "Test Agent", env: dict[str, str] | None = None) -> None:
        from loom.presence import CONVERSATION, ENTRYPOINT

        self.q = q
        base = {k: v for k, v in os.environ.items() if k not in (CONVERSATION, ENTRYPOINT)}
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "loom", "mcp", "--as", name],
            cwd=q,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**base, **(env or {})},
            preexec_fn=_signals_as_an_app_leaves_them,
        )
        self.next = 0

    @property
    def pid(self) -> int:
        return self.proc.pid

    @property
    def record(self) -> Path:
        from loom.presence import record_path

        return record_path(self.q, self.pid)

    def send(self, method: str, params: dict[str, Any] | None = None, *, meta: bool = True) -> None:
        """Send one request without waiting for its answer; `meta` stamps the envelope a client with no `initialize` sends."""
        self.next += 1
        body: dict[str, Any] = dict(params or {})
        if meta:
            body["_meta"] = {**META, **body.get("_meta", {})}
        line = json.dumps({"jsonrpc": "2.0", "id": self.next, "method": method, "params": body}) + "\n"
        assert self.proc.stdin is not None
        self.proc.stdin.write(line.encode("utf-8"))
        self.proc.stdin.flush()

    def request(self, method: str, params: dict[str, Any] | None = None, *, meta: bool = True) -> dict[str, Any]:
        """Send one request and wait for its answer."""
        self.send(method, params, meta=meta)
        assert self.proc.stdout is not None
        while True:
            ready, _, _ = select.select([self.proc.stdout], [], [], PATIENCE)
            assert ready, f"no answer to {method} in {PATIENCE} s"
            got = json.loads(self.proc.stdout.readline())
            if got.get("id") == self.next:
                return got

    def discover(self) -> dict[str, Any]:
        return self.request("server/discover")

    def initialize(self) -> dict[str, Any]:
        """The handshake of a client that sends one: who it is in `initialize`'s own fields, not in `_meta`."""
        got = self.request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "codex-mcp-client", "version": "0.9"},
            },
            meta=False,
        )
        assert self.proc.stdin is not None
        self.proc.stdin.write(b'{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
        self.proc.stdin.flush()
        return got

    def call(self, tool: str, arguments: dict[str, Any] | None = None, *, meta: bool = True) -> dict[str, Any]:
        """A tool call's result: its text, and whether it was an error."""
        got = self.request("tools/call", {"name": tool, "arguments": arguments or {}}, meta=meta)
        assert "result" in got, got
        return got["result"]

    def stop(self, sig: signal.Signals = signal.SIGTERM) -> int:
        """Send `sig` and wait for the process to end; its exit status."""
        self.proc.send_signal(sig)
        return self.wait()

    def wait(self) -> int:
        try:
            return self.proc.wait(timeout=PATIENCE)
        finally:
            self.close()

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=PATIENCE)
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if stream is not None:
                stream.close()

    def __enter__(self) -> AgentServer:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
