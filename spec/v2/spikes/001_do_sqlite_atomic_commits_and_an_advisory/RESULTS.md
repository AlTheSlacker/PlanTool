# Spike 001 results — SQLite + advisory lock on SMB (spikes:1)

Run 2026-07-17 with `probe.py`. Control: local NTFS (`local_run/`, `results_local.json`).
Real target: `\\DISKSTATION\homes\Al\plantool_spike\probe` — a Synology NAS SMB share
mounted from this Windows 11 machine (`results_smb.json`). Both targets ran the identical
battery; two processes on one client machine (the single-user scope of decisions:35/44).

## What was tested

1. **Atomic commits under kill-injection** — a writer commits [20 rows + 1 marker] per
   transaction with `synchronous=FULL` and is hard-killed at a random moment; 12 rounds
   per journal mode (DELETE, WAL) per target. Pass = `integrity_check` ok, no orphan
   batches (rows without their marker), no short batches (marker without all rows).
2. **Two concurrent writers**, 8 s, per journal mode per target.
3. **d44 lock protocol, scaled** (heartbeat 1 s, stale-claimable after 6 s; production
   is 10 min): O_EXCL claim race (20 rounds, exactly one winner required), heartbeat via
   tmp-file + atomic rename, stale-claim only after heartbeat silence.

## Results

| test | local (control) | SMB |
|---|---|---|
| kill-injection, DELETE | 12/12 clean | 12/12 clean |
| kill-injection, WAL | 12/12 clean | 12/12 clean |
| concurrent writers | clean, both modes | clean, both modes |
| claim race | 20 rounds, 0 double-claims | 20 rounds, 0 double-claims |
| heartbeat + stale-claim | correct (claim 5.2 s after kill) | **FAILED** (see below) |

## The SMB lock failure

In the first SMB run the stealer claimed the lock **while the holder was still live**
(`claimed_while_holder_alive: true`, observed heartbeat age 6.24 s > 6 s, claim 0.44 s
*before* the holder was killed). Instrumented re-runs (3x, holder stderr captured)
attributed it: the holder's heartbeat rename — `os.replace(tmp, writer.lock)` — fails
intermittently over SMB with `PermissionError(13, 'Access is denied')` (sharing
violation) whenever the polling reader has the lock file open. In the uninstrumented
run that exception killed the heartbeat loop silently; the "live" holder stopped
heartbeating and was legitimately stolen from — the silent double-claim class d44 exists
to prevent. With retry-on-error added, no steal-while-alive occurred in 3 runs, but
observed heartbeat age still reached **5.45 s of the 6 s threshold** under a 0.25 s
reader poll; consecutive failures can plausibly cross any threshold whose margin over
the heartbeat interval is small. Local NTFS never produced a single heartbeat error.

## Caveats measured but not concluded on

- SMB WAL commits showed p50 ≈ 0 ms — the SMB client (or NAS write cache) is absorbing
  `synchronous=FULL`. Atomicity vs *process* death is what this probe demonstrates;
  durability vs machine crash / network drop on SMB was NOT tested and should be assumed
  weaker than local disk.
- WAL's shared-memory index worked here because both processes sit on one SMB client.
  Two different client machines were not tested (out of single-user scope, d35).

## Verdict: refuted (the d55 assumption as stated is false on SMB)

Atomic commits held under every process-kill we threw at either journal mode, but "lock
claims are not silently corrupted" is false for the naive rename-heartbeat protocol on
SMB. Design consequence (per the spike's registered hypothesis): local-disk workspaces
are fully supported; network-mounted workspaces need a hardened lock protocol — heartbeat
retry-on-sharing-violation, reader access patterns that don't hold the lock file open,
staleness threshold ≫ heartbeat interval (the production 10 min vs ~30 s satisfies this),
plus a resume-time warning that network workspaces carry a machine-crash durability
caveat.
