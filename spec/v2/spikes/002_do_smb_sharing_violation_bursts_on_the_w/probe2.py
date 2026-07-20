"""Spike 002 probe (spikes:2): do SMB sharing-violation bursts on the
writer-lock file stay bounded well within the production staleness margin
(30 s renewal vs 600 s staleness) under sustained reader contention?

Two channels run concurrently against the same directory:
  * lock channel  — the hardened production protocol at real cadence: a writer
    renews main.lock every 30 s via tmp-write + os.replace, retrying sharing
    violations with backoff. Observable: renewal attempts, renewal duration,
    and the gap between successful renewals (= worst-case lease age).
  * sampler channel — burst statistics at 10 Hz on a sacrificial sample.lock:
    one unretried replace attempt every 0.1 s; consecutive failures form a
    streak whose duration approximates the sharing-violation burst length.

Load: 3 hardened readers (open/read/close, never dwell) hammer both files the
whole run; halfway through, a dweller (holds each file open 250 ms per cycle,
simulating an external scanner — the exact pattern that starved spike 1's
heartbeat) joins. Phase A = hardened-only, phase B = adversarial.

Usage:  python probe2.py run <target_dir> <label> [phase_secs]
Child roles: writer, sampler, reader, dweller.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

RENEW = 30.0          # production renewal cadence (decisions:58 ~30 s)
STALENESS = 600.0     # production staleness threshold
SAMPLE_EVERY = 0.1
RETRY_CAP = 1.0
RETRY_GIVEUP = 120.0
MAIN = "main.lock"
SAMPLE = "sample.lock"


def _replace_once(d: Path, name: str, tag: str) -> None:
    tmp = d / f"tmp_{tag}_{os.getpid()}"
    tmp.write_text(f"{tag} {time.time()}", encoding="ascii")
    os.replace(tmp, d / name)


def writer(d: str, duration: float) -> None:
    dp = Path(d)
    _replace_once(dp, MAIN, "w")
    last_ok = time.monotonic()
    t_end = time.monotonic() + duration
    i = 0
    while time.monotonic() < t_end:
        time.sleep(RENEW)
        i += 1
        t0 = time.monotonic()
        attempts = 0
        while True:
            attempts += 1
            try:
                _replace_once(dp, MAIN, "w")
                break
            except (PermissionError, OSError) as exc:
                if time.monotonic() - t0 > RETRY_GIVEUP:
                    print(f"GIVEUP {i} {exc!r}", flush=True)
                    break
                time.sleep(min(0.05 * attempts, RETRY_CAP))
        now = time.monotonic()
        print(f"RENEW {i} t={now - t_end + duration:.1f} attempts={attempts} "
              f"dur={now - t0:.3f} gap={now - last_ok:.3f}", flush=True)
        last_ok = now


def sampler(d: str, duration: float) -> None:
    dp = Path(d)
    t_start = time.monotonic()
    t_end = t_start + duration
    streak_start = None
    streak_n = 0
    ok = fail = 0
    while time.monotonic() < t_end:
        time.sleep(SAMPLE_EVERY)
        try:
            _replace_once(dp, SAMPLE, "s")
            ok += 1
            if streak_start is not None:
                print(f"STREAK t={streak_start - t_start:.1f} "
                      f"dur={time.monotonic() - streak_start:.3f} n={streak_n}",
                      flush=True)
                streak_start, streak_n = None, 0
        except (PermissionError, OSError):
            fail += 1
            if streak_start is None:
                streak_start = time.monotonic()
            streak_n += 1
    if streak_start is not None:
        print(f"STREAK t={streak_start - t_start:.1f} "
              f"dur={time.monotonic() - streak_start:.3f} n={streak_n}", flush=True)
    print(f"SAMPLES ok={ok} fail={fail}", flush=True)


def reader(d: str, duration: float) -> None:
    dp = Path(d)
    t_end = time.monotonic() + duration
    reads = errs = 0
    while time.monotonic() < t_end:
        for name in (MAIN, SAMPLE):
            try:
                (dp / name).read_text(encoding="ascii")
                reads += 1
            except OSError:
                errs += 1
        time.sleep(0.02)
    print(f"READER reads={reads} errs={errs}", flush=True)


def dweller(d: str, duration: float) -> None:
    dp = Path(d)
    t_end = time.monotonic() + duration
    holds = errs = 0
    while time.monotonic() < t_end:
        for name in (MAIN, SAMPLE):
            try:
                with open(dp / name, "r", encoding="ascii"):
                    time.sleep(0.25)
                holds += 1
            except OSError:
                errs += 1
        time.sleep(0.05)
    print(f"DWELLER holds={holds} errs={errs}", flush=True)


def spawn(*args: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(HERE / "probe2.py"), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _parse(out: str, phase_secs: float) -> dict:
    renews, giveups, streaks, samples = [], [], [], None
    for line in out.splitlines():
        parts = line.split()
        if line.startswith("RENEW"):
            kv = dict(p.split("=") for p in parts[2:])
            renews.append({"i": int(parts[1]), "t": float(kv["t"]),
                           "attempts": int(kv["attempts"]),
                           "dur": float(kv["dur"]), "gap": float(kv["gap"])})
        elif line.startswith("GIVEUP"):
            giveups.append(line)
        elif line.startswith("STREAK"):
            kv = dict(p.split("=") for p in parts[1:])
            streaks.append({"t": float(kv["t"]), "dur": float(kv["dur"]),
                            "n": int(kv["n"])})
        elif line.startswith("SAMPLES"):
            samples = dict(p.split("=") for p in parts[1:])
    def phase(items, lo, hi):
        return [x for x in items if lo <= x["t"] < hi]
    def summ_renews(rs):
        if not rs:
            return {"n": 0}
        return {"n": len(rs),
                "max_gap": max(r["gap"] for r in rs),
                "max_dur": max(r["dur"] for r in rs),
                "max_attempts": max(r["attempts"] for r in rs),
                "retried": sum(1 for r in rs if r["attempts"] > 1)}
    def summ_streaks(ss):
        if not ss:
            return {"n": 0}
        durs = sorted(s["dur"] for s in ss)
        return {"n": len(ss), "max_dur": durs[-1],
                "p50_dur": durs[len(durs) // 2],
                "total_fail_samples": sum(s["n"] for s in ss)}
    return {
        "renewals": {"all": summ_renews(renews),
                     "phaseA_hardened": summ_renews(phase(renews, 0, phase_secs)),
                     "phaseB_dweller": summ_renews(phase(renews, phase_secs, 1e9))},
        "renew_giveups": giveups,
        "streaks": {"all": summ_streaks(streaks),
                    "phaseA_hardened": summ_streaks(phase(streaks, 0, phase_secs)),
                    "phaseB_dweller": summ_streaks(phase(streaks, phase_secs, 1e9))},
        "sampler_totals": samples,
        "worst_renewals": sorted(renews, key=lambda r: -r["gap"])[:5],
        "worst_streaks": sorted(streaks, key=lambda s: -s["dur"])[:5],
    }


def run(target_dir: str, label: str, phase_secs: float = 720.0) -> None:
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    for f in target.glob("*"):
        f.unlink()
    duration = phase_secs * 2
    w = spawn("writer", str(target), str(duration))
    s = spawn("sampler", str(target), str(duration))
    readers = [spawn("reader", str(target), str(duration)) for _ in range(3)]
    time.sleep(phase_secs)
    dw = spawn("dweller", str(target), str(phase_secs))
    procs = [w, s, dw, *readers]
    outs = []
    for p in procs:
        try:
            outs.append(p.communicate(timeout=phase_secs * 2 + 180)[0])
        except subprocess.TimeoutExpired:
            p.kill()
            outs.append(p.communicate()[0])
    results = {
        "label": label, "target": str(target),
        "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": {"renew_s": RENEW, "staleness_s": STALENESS,
                   "phase_secs": phase_secs, "sample_every_s": SAMPLE_EVERY,
                   "readers": 3, "dweller_phaseB": True},
        **_parse(outs[0] + "\n" + outs[1], phase_secs),
        "reader_lines": [o.strip().splitlines()[-1] for o in outs[3:] if o.strip()],
        "dweller_line": outs[2].strip().splitlines()[-1] if outs[2].strip() else None,
    }
    results["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = HERE / f"results2_{label}.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results, indent=1))


def main(argv: list[str]) -> None:
    cmd = argv[0]
    if cmd == "writer":
        writer(argv[1], float(argv[2]))
    elif cmd == "sampler":
        sampler(argv[1], float(argv[2]))
    elif cmd == "reader":
        reader(argv[1], float(argv[2]))
    elif cmd == "dweller":
        dweller(argv[1], float(argv[2]))
    elif cmd == "run":
        run(argv[1], argv[2], float(argv[3]) if len(argv) > 3 else 720.0)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
