# Spike 2 results — SMB sharing-violation bursts vs production staleness margin

**Verdict: CONFIRMED** (2026-07-17). Bursts stay bounded far inside the production
margin; the hardened retrying renewal never approached staleness.

## Setup

- Target: `\\DISKSTATION\homes\Al\plantool_spike2` (Synology, real SMB); control:
  local NTFS (`%TEMP%\spike2_local`). Probe: `probe2.py`, results in
  `results2_smb.json` / `results2_local.json`.
- Production protocol at real cadence: writer renews `main.lock` every **30 s** via
  tmp-write + `os.replace`, retrying sharing violations with backoff (50 ms × attempts,
  capped 1 s; give-up 120 s). Staleness threshold **600 s**.
- Load: 3 hardened readers (open/read/close every 20 ms, never dwell) for the whole
  24-minute run; **phase B (final 12 min) adds a dweller** holding each file open
  250 ms per cycle — the exact pattern that starved spike 1's naive heartbeat.
- Second channel: 10 Hz unretried replace sampler on a sacrificial file for
  burst-length statistics.

## Observations (SMB)

- 48/48 renewals succeeded; **zero give-ups**.
- Phase A (hardened readers only): worst renewal 4 attempts / 0.48 s; max lease
  age 30.48 s (renewal interval + 0.48 s).
- Phase B (dweller): worst renewal **17 attempts / 7.94 s**; **max lease age
  37.94 s = 6.3 % of the 600 s staleness threshold** (hypothesis bound was < 120 s).
- Sampler: 142 violation streaks, max streak 0.44 s. Note: SMB replace latency under
  load degraded the sampler to ~2 s/cycle (696 samples, not the nominal 14 400), so
  the renewal channel is the authoritative burst measure — its worst continuous
  violation window is the 7.9 s retried renewal.
- Reader-side: 0.33 % transient read errors (306/91 334) — reads must tolerate
  transient failure, consistent with the hardened-reader requirement.

## Observations (local NTFS control)

- Phase A perfectly clean (every renewal 1 attempt, ≤ 16 ms). Phase B: worst
  4 attempts / 0.31 s. Bursts are contention-driven; SMB amplifies duration
  (~8 s worst vs 0.31 s local) but remains bounded.

## Consequence

decisions:58's extrapolation holds at production cadence: with retry-on-sharing-
violation and a 30 s renewal interval, worst-case lease age stays ~16× under the
600 s staleness threshold even with an adversarial file-dwelling process. The
assumed(world) claim decisions:59 upgrades to verified. Caveats: single client
machine, 24-minute compressed run (within the 2 h budget), one dweller process.
