r"""Spike 003 probe (spikes:3): forced SMB session drop while a SQLite commit
loop is in flight — is the DB consistent and recoverable after reconnect, and
does any acknowledged commit vanish?

Per round (per journal mode):
  1. fresh DB on the UNC target; child writer loops transactions
     (20 rows + marker, synchronous=FULL), printing "ACK <batch>" only AFTER
     commit() returns — the acknowledged set.
  2. orchestrator waits READY + random 0.5-2 s, then force-drops the share
     connection: `net use \\DISKSTATION\homes /delete /y`, escalating to the
     Y: mapping (same share) if the writer survives; deleted mappings are
     restored at the end.
  3. writer's handles die mid-commit (logged IOERR) — or SMB transparently
     recovers (logged as such; also an observation).
  4. reconnect by touching the UNC path again; verify integrity_check,
     orphan/short batches; compare surviving markers vs acknowledged ACKs:
     lost_acked = acked - present, unacked_present = present - acked.

Usage:  python probe3.py run   (writes results3.json here)
Child role: writer <db> <mode>.
"""
from __future__ import annotations

import json
import random
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path(r"\\DISKSTATION\homes\Al\plantool_spike2")
SHARE = r"\\DISKSTATION\homes"
BATCH_N = 20
ROUNDS = 4
READY_TIMEOUT = 45.0


def readline_timeout(pipe, secs: float) -> str | None:
    """Read one line with a deadline — None on timeout (SMB backoff can block
    the writer before it ever prints READY)."""
    box: list[str] = []
    t = threading.Thread(target=lambda: box.append(pipe.readline()), daemon=True)
    t.start()
    t.join(secs)
    return box[0].strip() if box else None


def share_ready(timeout: float = 90.0) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            list(TARGET.iterdir())
            return True
        except OSError:
            time.sleep(2)
    return False


def writer(db_path: str, mode: str) -> None:
    conn = sqlite3.connect(db_path, timeout=30)
    print(f"MODE {conn.execute(f'PRAGMA journal_mode={mode}').fetchone()[0]}", flush=True)
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("CREATE TABLE IF NOT EXISTS rows(batch INTEGER, seq INTEGER, payload TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS markers(batch INTEGER PRIMARY KEY, n INTEGER)")
    conn.commit()
    print("READY", flush=True)
    b = 0
    while True:
        b += 1
        try:
            conn.execute("BEGIN IMMEDIATE")
            for i in range(BATCH_N):
                conn.execute("INSERT INTO rows VALUES (?,?,?)", (b, i, "x" * 100))
            conn.execute("INSERT INTO markers VALUES (?,?)", (b, BATCH_N))
            conn.commit()
            print(f"ACK {b}", flush=True)
        except sqlite3.Error as exc:
            print(f"IOERR {b} {exc!r}", flush=True)
            return


def sh(*args: str) -> tuple[int, str]:
    p = subprocess.run(args, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def connections() -> str:
    return sh("net", "use")[1]


def disconnect(writer_proc: subprocess.Popen) -> dict:
    """Force-drop the tracked share connection established by one_round."""
    steps = []
    rc, out = sh("net", "use", SHARE, "/delete", "/y")
    steps.append({"cmd": f"net use {SHARE} /delete /y", "rc": rc, "out": out[-200:]})
    t0 = time.monotonic()
    while writer_proc.poll() is None and time.monotonic() - t0 < 8:
        time.sleep(0.25)
    return {"steps": steps, "writer_died": writer_proc.poll() is not None}


def reconnect() -> bool:
    for _ in range(20):
        try:
            list(TARGET.iterdir())
            return True
        except OSError:
            time.sleep(1)
    return False


def verify(db: Path, acked: set[int]) -> dict:
    last = "?"
    for _ in range(10):
        try:
            conn = sqlite3.connect(db, timeout=30)
            present = {r[0] for r in conn.execute("SELECT batch FROM markers")}
            out = {
                "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
                "orphan_batches": conn.execute(
                    "SELECT count(DISTINCT batch) FROM rows "
                    "WHERE batch NOT IN (SELECT batch FROM markers)").fetchone()[0],
                "short_batches": conn.execute(
                    "SELECT count(*) FROM markers m WHERE m.n <> "
                    "(SELECT count(*) FROM rows r WHERE r.batch = m.batch)").fetchone()[0],
                "acked": len(acked), "present_markers": len(present),
                "lost_acked": sorted(acked - present),
                "unacked_present": sorted(present - acked),
            }
            conn.close()
            return out
        except sqlite3.Error as exc:
            last = repr(exc)
            time.sleep(1)
    return {"error": last}


def one_round(mode: str, rnd: int) -> dict:
    if not share_ready():
        return {"fatal": "share not reachable within 90 s after previous drop"}
    # A device-less UNC access is not tracked by `net use`, so establish a
    # tracked connection first — the forced delete then has a real
    # connection (and its open handles) to sever.
    rc, out = sh("net", "use", SHARE)
    if rc != 0:
        return {"fatal": f"could not establish tracked connection: {out[-200:]}"}
    db = TARGET / f"drop_{mode}.db"
    for f in TARGET.glob(db.name + "*"):
        f.unlink()
    p = subprocess.Popen(
        [sys.executable, str(HERE / "probe3.py"), "writer", str(db), mode],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    mode_line = readline_timeout(p.stdout, READY_TIMEOUT)
    ready = readline_timeout(p.stdout, READY_TIMEOUT) if mode_line else None
    if ready != "READY":
        p.kill()
        p.communicate()
        return {"fatal": f"writer blocked or died before READY (mode_line="
                         f"{mode_line!r}, ready={ready!r}) — SMB backoff after "
                         "repeated drops is itself an observation"}
    time.sleep(random.uniform(0.5, 2.0))
    drop = disconnect(p)
    try:
        out, _err = p.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        p.kill()
        out, _err = p.communicate()
        drop["writer_hung_killed"] = True
    acked = {int(ln.split()[1]) for ln in out.splitlines() if ln.startswith("ACK")}
    ioerr = [ln for ln in out.splitlines() if ln.startswith("IOERR")]
    reconnected = reconnect()
    result = {"round": rnd, "mode_line": mode_line, "drop": drop,
              "ioerr": ioerr[:2], "survived_drop": not ioerr and not drop["writer_died"],
              "reconnected": reconnected}
    result.update(verify(db, acked) if reconnected else {"error": "no reconnect"})
    return result


def run() -> None:
    before = connections()
    results = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "target": str(TARGET), "net_use_before": before, "rounds": {}}
    jsonl = HERE / "results3_rounds.jsonl"
    for mode in ("delete", "wal"):
        results["rounds"][mode] = []
        for rnd in range(ROUNDS):
            r = one_round(mode, rnd)
            results["rounds"][mode].append(r)
            with jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"mode": mode, **r}, default=str) + "\n")
            print(f"[{mode} round {rnd}] {json.dumps(r, default=str)[:300]}", flush=True)
            time.sleep(2)
    results["net_use_after"] = connections()
    results["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (HERE / "results3.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results, indent=1))


def main(argv: list[str]) -> None:
    if argv[0] == "writer":
        writer(argv[1], argv[2])
    elif argv[0] == "run":
        run()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
