"""The MCP stdio transport for `mcp-surface` (`components:15`).

`engine/mcp.py` had no test at all, which is how it shipped a `tools/list` that crashes:
M7's revision tools added two argument kinds (`change_request`, `owner_decision`) to the
surface registry and its `DECODERS`, but nobody extended this module's parallel `SCHEMA_OF`
map. `tool_list()` — called by every MCP client at startup — then raised `KeyError` on the
first revision tool, and because `serve()` does not guard `handle()`, the whole server died
before a single tool could be called.

The first two tests are the *mechanism* against a repeat: `SCHEMA_OF` (the advertisement)
and `DECODERS` (the check) are two hand-kept maps keyed by the same argument-kind
vocabulary, and they must cover the same kinds or the advertisement can fall behind the
thing that actually validates — exactly the drift that happened here.
"""

from __future__ import annotations

import io
import json

from engine.mcp import SCHEMA_OF, Server, tool_list
from engine.storage import Storage
from engine.surface import DECODERS, REGISTRY, Surface


def test_schema_and_decoders_cover_the_same_kinds():
    """The advertise side must not fall behind the decode side.

    `DECODERS` is authoritative — it is what refuses a bad call — so any kind it knows must
    also be advertised by `SCHEMA_OF`. Asserting set equality catches drift in either
    direction: a new kind added to one map and forgotten in the other fails here, loudly,
    naming the kind, before it can reach a client as a `KeyError`.
    """
    assert set(SCHEMA_OF) == set(DECODERS), (
        "SCHEMA_OF (mcp.py) and DECODERS (surface.py) have drifted: "
        f"{sorted(set(DECODERS) ^ set(SCHEMA_OF))}"
    )


def test_every_registry_kind_is_advertised():
    """Every argument kind any tool actually uses must have a JSON-schema advertisement."""
    used = {p.kind for tool in REGISTRY.values() for p in tool.params}
    missing = sorted(used - set(SCHEMA_OF))
    assert not missing, f"registry uses kinds with no SCHEMA_OF entry: {missing}"


def test_tool_list_builds_for_the_whole_registry():
    """The direct reproduction: listing the toolset must not raise, and must be complete.

    Before the fix this raised `KeyError: 'change_request'` on the first revision tool.
    """
    tools = tool_list()
    assert len(tools) == len(REGISTRY)
    for entry in tools:
        assert entry["inputSchema"]["type"] == "object"


def test_tools_list_over_the_wire_survives_the_handshake(tmp_path):
    """End-to-end through the real stdio server: initialize then tools/list, as any client
    does at startup. This is the exact path that killed the server on first contact."""
    requests = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        + "\n"
    )
    storage = Storage(str(tmp_path))
    try:
        stdout = io.StringIO()
        Server(Surface(storage), io.StringIO(requests), stdout).serve()
    finally:
        storage.close()

    replies = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    by_id = {r["id"]: r for r in replies}
    assert by_id[1]["result"]["serverInfo"]["name"] == "plantool"
    assert "error" not in by_id[2]
    assert len(by_id[2]["result"]["tools"]) == len(REGISTRY)
