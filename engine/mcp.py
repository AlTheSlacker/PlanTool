"""The MCP stdio transport for `mcp-surface` (`components:15`).

`contracts:50` is declared `api` and consumed externally by the planning agent and the code
engine, so something has to speak the wire protocol. This is that something and nothing
more: JSON-RPC 2.0 over stdin/stdout, newline-delimited, translating three MCP methods into
`Surface.dispatch` calls.

**It is kept separate from `engine/surface.py` on purpose.** The surface is the toolset —
validation, the registry, the door — and it knows nothing about MCP. This module knows
about MCP and nothing about planning. That seam is what `decisions:4`'s "strictly
protocol-clean, no engine-specific calls or configuration" buys, and it is also what lets
the GUI at M8 be a second adapter on the same surface rather than a second copy of it. If
anything in here starts making decisions about plans, the seam has been crossed.

**No transport-level authentication, sessions or state.** The tool is a passive, durable
callee (`dep_failure_modes:12`): it executes when a call arrives and holds nothing between
calls. Every scrap of state is in the workspace, which is what makes a planner's context
disposable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, IO

from engine.storage import Storage
from engine.surface import REGISTRY, Surface, ToolCall

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "plantool"

#: JSON Schema for each argument kind the registry uses. The surface validates properly on
#: the way in — this is the advertisement, not the check. Two places that both had to be
#: right would drift; here only one of them can refuse a call, so a schema that is merely
#: loose costs a clearer error, never a wrong write.
SCHEMA_OF: dict[str, dict[str, Any]] = {
    "str": {"type": "string"},
    "int": {"type": "integer"},
    "bool": {"type": "boolean"},
    "ref": {"type": "string", "description": "an address like 'requirements:61'"},
    "refs": {"type": "array", "items": {"type": "string"}},
    "ints": {"type": "array", "items": {"type": "integer"}},
    "rows": {"type": "array", "items": {"type": "object"}},
    "row": {"type": "object"},
    "selector": {"type": "object"},
    "spike": {"type": "object"},
    "selection": {"type": "object"},
    "split": {"type": "array", "items": {"type": "object"}},
    "evidence": {"type": "object", "additionalProperties": {"type": "string"}},
    "change_request": {"type": "object"},
    "owner_decision": {"type": "object"},
}


def input_schema(tool) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            p.name: dict(SCHEMA_OF[p.kind], description=p.note) for p in tool.params
        },
        "required": [p.name for p in tool.params if p.required],
        "additionalProperties": False,
    }


def tool_list() -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.summary,
            "inputSchema": input_schema(tool),
        }
        for tool in REGISTRY.values()
    ]


class Server:
    """One workspace, served over stdio until the stream closes."""

    def __init__(self, surface: Surface, stdin: IO[str], stdout: IO[str]):
        self.surface = surface
        self.stdin = stdin
        self.stdout = stdout

    def serve(self) -> None:
        for line in self.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                self._send(self._error(None, -32700, f"not JSON: {exc}"))
                continue
            reply = self.handle(message)
            if reply is not None:
                self._send(reply)

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """One JSON-RPC message in, at most one out.

        Notifications get no reply, which is the protocol's rule and also the reason this
        returns `None` rather than an empty result: an empty result on the wire is a reply,
        and a reply to a notification is a protocol error the client has to forgive.
        """
        method = message.get("method")
        request_id = message.get("id")
        if method == "initialize":
            return self._ok(request_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": "2"},
            })
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return self._ok(request_id, {"tools": tool_list()})
        if method == "tools/call":
            params = message.get("params") or {}
            result = self.surface.dispatch(
                ToolCall(
                    name=params.get("name", ""),
                    arguments=params.get("arguments") or {},
                )
            )
            body = result.as_content()
            return self._ok(request_id, {
                "content": [
                    {"type": "text", "text": json.dumps(body, indent=2, default=str)}
                ],
                "isError": not result.ok,
            })
        if request_id is None:
            return None
        return self._error(request_id, -32601, f"no method {method!r}")

    # --- wire ---

    def _send(self, message: dict[str, Any]) -> None:
        self.stdout.write(json.dumps(message, default=str) + "\n")
        self.stdout.flush()

    @staticmethod
    def _ok(request_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }


def main(argv: list[str] | None = None) -> int:
    """`python -m engine.mcp <workspace>` — the whole entry point.

    A tool failure is a `ToolResult`, not an exit code: the client is on the other end of
    the same pipe and needs to be told which call failed and why. Only a missing workspace
    ends the process, because there is nothing to serve — and note that an *empty* one is
    fine. `init_plan` is a tool, so a fresh workspace is served before it holds a plan;
    refusing to start without one would leave no way to call the tool that makes one.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    workspace = args[0] if args else "."
    if not Path(workspace).is_dir():
        sys.stderr.write(
            f"no workspace at {workspace}; the tool never creates one "
            f"(requirements:8)\n"
        )
        return 2
    storage = Storage(workspace)
    try:
        Server(Surface(storage), sys.stdin, sys.stdout).serve()
    finally:
        storage.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
