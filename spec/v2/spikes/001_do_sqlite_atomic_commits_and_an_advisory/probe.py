"""Spike 001 probe (spikes:1): SQLite atomic commits + the d44 advisory
writer-lock protocol on a network-mounted filesystem vs local disk.

Registered question: do SQLite atomic commits and an advisory writer-lock
heartbeat file behave correctly when the workspace sits on an SMB share, or
must the tool document local-disk-only support?

Battery (run once per target; local disk is the control, not the result):
  1. kill-injection atomic-commit test, journal_mode=DELETE and WAL — a
     writer commits [20 data rows + 1 marker row] per transaction and is
     hard-killed at a random moment; after each kill the DB must pass
     PRAGMA integrity_check with zero orphan batches (rows without marker)
     and zero short batches (marker without all rows).
  2. two concurrent writers on one DB — no corruption, both make progress,
     busy contention degrades gracefully.
  3. d44 lock protocol scaled down (heartbeat 1s, stale after 6s; production
     is 10 min): O_EXCL claim race (exactly one winner), heartbeat via
     atomic rename, stale-claim only after silence — a stealer that claims
     while the holder is alive and heartbeating is a silent double-claim.

Usage:
  python probe.py run <target_dir> <label>   ->  results_<label>.json (here)
Child roles launched by `run`: writer, claim, hold, steal.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

BATCH_N = 20
KILL_ROUNDS = 12
CONCURRENT_SECS = 8
RACE_ROUNDS = 20
HEARTBEAT = 1.0
STALE_AFTER = 6.0
LOCK = "writer.lock"


# --- child: transactional writer ---------------------------------------------

def writer(db_path: str, mode: str, wid: int, duration: float) -> None:
    conn = sqlite3.connect(db_path, timeout=30)
    actual = conn.execute(f"PRAGMA journal_mode={mode}").fetchone()[0]
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("CREATE TABLE IF NOT EXISTS rows(batch INTEGER, seq INTEGER, payload TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS markers(batch INTEGER PRIMARY KEY, n INTEGER)")
    conn.commit()
    print(f"MODE {actual}", flush=True)
    committed = busy = 0
    latencies: list[float] = []
    t_end = time.monotonic() + duration
    b = 0
    while time.monotonic() < t_end:
        b += 1
        batch = wid * 10_000_000 + b
        t0 = time.monotonic()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for i in range(BATCH_N):
                conn.execute("INSERT INTO rows VALUES (?,?,?)", (batch, i, "x" * 100))
            conn.execute("INSERT INTO markers VALUES (?,?)", (batch, BATCH_N))
            conn.commit()
        except sqlite3.OperationalError:
            busy += 1
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            continue
        latencies.append(time.monotonic() - t0)
        committed += 1
        if committed == 1:
            print("READY", flush=True)
    lat = sorted(latencies)
    stats = (f" p50={lat[len(lat) // 2]:.4f} max={lat[-1]:.4f}" if lat else "")
    print(f"DONE committed={committed} busy={busy}{stats}", flush=True)


def verify_db(db_path: Path) -> dict:
    last = "?"
    for _ in range(10):  # the killed writer's handle may linger briefly over SMB
        try:
            conn = sqlite3.connect(db_path, timeout=30)
            out = {
                "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
                "orphan_batches": conn.execute(
                    "SELECT count(DISTINCT batch) FROM rows "
                    "WHERE batch NOT IN (SELECT batch FROM markers)").fetchone()[0],
                "short_batches": conn.execute(
                    "SELECT count(*) FROM markers m WHERE m.n <> "
                    "(SELECT count(*) FROM rows r WHERE r.batch = m.batch)").fetchone()[0],
                "committed_batches": conn.execute(
                    "SELECT count(*) FROM markers").fetchone()[0],
            }
            conn.close()
            return out
        except sqlite3.Error as exc:
            last = repr(exc)
            time.sleep(0.5)
    return {"error": last}


# --- child: d44 lock protocol --------------------------------------------------

def lock_path(d: str) -> Path:
    return Path(d) / LOCK


def claim(d: str, sid: str) -> bool:
    try:
        fd = os.open(lock_path(d), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, f"{sid} {time.time()}".encode())
    os.close(fd)
    return True


def heartbeat(d: str, sid: str) -> None:
    tmp = Path(d) / f"hb_{sid}.tmp"
    tmp.write_text(f"{sid} {time.time()}", encoding="ascii")
    os.replace(tmp, lock_path(d))


def read_hb(d: str) -> float | None:
    try:
        _sid, ts = lock_path(d).read_text(encoding="ascii").split()
        return float(ts)
    except (OSError, ValueError):
        return None


def hold(d: str, sid: str) -> None:
    if not claim(d, sid):
        print("FAILED", flush=True)
        return
    print("CLAIMED", flush=True)
    while True:
        time.sleep(HEARTBEAT)
        try:
            heartbeat(d, sid)
        except OSError as exc:  # a failed heartbeat is a finding, not a crash
            print(f"HBERR {exc!r}", flush=True)


def steal(d: str, sid: str) -> None:
    max_age = 0.0
    readerrs = 0
    while True:
        time.sleep(0.25)
        ts = read_hb(d)
        if ts is None:
            readerrs += 1
            print(f"READERR {readerrs}", flush=True)
            continue
        age = time.time() - ts
        if age > max_age + 0.5:
            max_age = age
            print(f"MAXAGE {max_age:.2f} {time.time():.3f}", flush=True)
        if age > STALE_AFTER:
            heartbeat(d, sid)
            print(f"CLAIMED {time.time():.3f} age={age:.2f}", flush=True)
            return


# --- orchestrator --------------------------------------------------------------

def spawn(*args: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(HERE / "probe.py"), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)


def _wipe(db: Path) -> None:
    for f in db.parent.glob(db.name + "*"):
        f.unlink()


def kill_test(target: Path, mode: str) -> dict:
    db = target / f"kill_{mode}.db"
    _wipe(db)
    rounds, actual_mode = [], None
    for rnd in range(KILL_ROUNDS):
        p = spawn("writer", str(db), mode, str(100 + rnd), "3600")
        mode_line = p.stdout.readline().strip()
        actual_mode = mode_line.split()[-1] if mode_line.startswith("MODE") else None
        ready = p.stdout.readline()
        if not ready.startswith("READY"):
            err = p.stderr.read()
            p.kill()
            p.wait()
            return {"fatal": f"writer died before first commit: {mode_line!r} "
                             f"{ready!r} stderr: ...{err[-400:]}",
                    "actual_mode": actual_mode, "rounds": rounds}
        time.sleep(random.uniform(0.2, 1.0))
        p.kill()
        p.wait()
        rounds.append(verify_db(db))
    bad = [r for r in rounds
           if r.get("integrity") != "ok" or r.get("orphan_batches") or
           r.get("short_batches") or "error" in r]
    return {"actual_mode": actual_mode, "kills": len(rounds),
            "violations": bad, "final": rounds[-1] if rounds else None}


def _parse_done(out: str) -> dict:
    for line in reversed(out.splitlines()):
        if line.startswith("DONE"):
            return dict(kv.split("=") for kv in line.split()[1:])
    return {"missing_done": out[-200:]}


def concurrent_test(target: Path, mode: str) -> dict:
    db = target / f"conc_{mode}.db"
    _wipe(db)
    a = spawn("writer", str(db), mode, "1", str(CONCURRENT_SECS))
    b = spawn("writer", str(db), mode, "2", str(CONCURRENT_SECS))
    out_a = a.communicate(timeout=CONCURRENT_SECS + 120)[0]
    out_b = b.communicate(timeout=CONCURRENT_SECS + 120)[0]
    return {"writer1": _parse_done(out_a), "writer2": _parse_done(out_b),
            "db": verify_db(db)}


def lock_race_test(target: Path) -> dict:
    d = target / "racetest"
    double = none = 0
    for _ in range(RACE_ROUNDS):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir()
        procs = [spawn("claim", str(d), sid) for sid in ("P1", "P2")]
        outs = [p.communicate(timeout=60)[0].strip() for p in procs]
        wins = sum(o.endswith("WON") for o in outs)
        double += wins == 2
        none += wins == 0
    return {"rounds": RACE_ROUNDS, "double_claims": double, "no_winner": none}


def lock_steal_test(target: Path) -> dict:
    d = target / "stealtest"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir()
    holder = spawn("hold", str(d), "A")
    if holder.stdout.readline().strip() != "CLAIMED":
        holder.kill()
        return {"fatal": "holder failed to claim a fresh lock"}
    stealer = spawn("steal", str(d), "B")
    time.sleep(10)  # holder alive and heartbeating: stealer must not claim
    claimed_while_alive = stealer.poll() is not None
    holder_exit_before_kill = holder.poll()
    t_kill = time.time()
    holder.kill()
    holder_out = holder.communicate()[0]
    hb_errors = [ln for ln in holder_out.splitlines() if ln.startswith("HBERR")]
    try:
        out = stealer.communicate(timeout=STALE_AFTER * 5)[0]
    except subprocess.TimeoutExpired:
        stealer.kill()
        return {"claimed_while_holder_alive": claimed_while_alive,
                "fatal": "stealer never claimed after holder death"}
    claimed_at = max_age_alive = None
    readerrs = 0
    for line in out.splitlines():
        if line.startswith("CLAIMED"):
            claimed_at = float(line.split()[1])
        elif line.startswith("MAXAGE"):
            _, age_s, at_s = line.split()
            if float(at_s) < t_kill:  # only observations while the holder lived
                max_age_alive = float(age_s)
        elif line.startswith("READERR"):
            readerrs = int(line.split()[1])
    return {"claimed_while_holder_alive": claimed_while_alive,
            "holder_exit_before_kill": holder_exit_before_kill,
            "holder_heartbeat_errors": hb_errors[:5],
            "holder_heartbeat_error_count": len(hb_errors),
            "max_heartbeat_age_seen_while_alive": max_age_alive,
            "claim_delay_after_kill": round(claimed_at - t_kill, 2) if claimed_at else None,
            "stale_after": STALE_AFTER, "read_errors": readerrs}


def run(target_dir: str, label: str) -> None:
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    results = {"label": label, "target": str(target),
               "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "kill": {}, "concurrent": {}, "lock": {}}
    for mode in ("delete", "wal"):
        results["kill"][mode] = kill_test(target, mode)
        results["concurrent"][mode] = concurrent_test(target, mode)
    results["lock"]["race"] = lock_race_test(target)
    results["lock"]["steal"] = lock_steal_test(target)
    results["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = HERE / f"results_{label}.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results, indent=1))


def main(argv: list[str]) -> None:
    cmd = argv[0]
    if cmd == "writer":
        writer(argv[1], argv[2], int(argv[3]), float(argv[4]))
    elif cmd == "claim":
        print("WON" if claim(argv[1], argv[2]) else "LOST", flush=True)
    elif cmd == "hold":
        hold(argv[1], argv[2])
    elif cmd == "steal":
        steal(argv[1], argv[2])
    elif cmd == "run":
        run(argv[1], argv[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
