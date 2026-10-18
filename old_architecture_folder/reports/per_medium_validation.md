# Per-medium implementation validation

## Scope and preserved work

The nine implementation steps are recorded on `per-medium-redesign`, beginning
from baseline `7b5c290`. `AGENTS.md` remains uncommitted at the user's request.
The original source, operating guides and tests are preserved in
`old_architecture_folder/source/`; the complete baseline hit inventory and
final dispositions are in the archive's migration report.

Existing local artifacts were moved using same-filesystem directory renames.
Post-migration file counts and byte totals match the manifest:

| Artifact | Files | Bytes |
| --- | ---: | ---: |
| Datasets | 245,657 | 20,707,210,402 |
| Checkpoints | 38 | 14,465,934,207 |
| Session recaps | 3 | 59,679 |

These artifacts remain ignored locally. GitHub receives source, guides, fixtures
and example labels, not the large recordings/checkpoints. No raw episode
payloads were rewritten. Old metadata was loaded successfully from an original
archived episode and from a compatibility fixture, including `metadata.json`.

## Checks performed

- `PYTHONPATH=.:robomimic-r2d2 python3 -m pytest tests/ -q`: **172 passed** in
  the Python 3.8 `Xtrainer` environment. Scanner parsing, review synchronization,
  curation rollback/hash checks, conversion provenance, checkpoint loading,
  handoff settling, motion validation, recovery, retries and fault stops are covered.
- `python3 experiments/run_control.py --medium envelope --label-face bottom
  --dry-run --save-data-path /tmp/rse-final-recording`: new metadata written
  without opening hardware; explicitly not a usable training episode.
- `python3 experiments/scripted_motion.py --dry-run`: 33 interpolated commands
  passed validation. Motion tests check pacing, cable limits, feedback divergence,
  and keeping the released gripper open during retreat.
- Simulated cycles passed for all three media. Carton scans stop after the first
  mapped read; no-read sweeps exhaust three rotations, return to receiving and
  produce linked rows for at most one retry. Unknown tokens never choose a bin.
- `python3 scripts/smoke_training.py --output /tmp/rse-final-model-smoke`:
  trained tiny ACT and DP models, reloaded their saved normalization statistics,
  and requested three actions from each adapter. Results and logs are in that
  directory. No predictions were sent to a robot. Smoke checkpoints are refused
  by the live supervisor.
- Full-stock and carton label PDFs were rendered and visually checked. The
  Code 128 module/bar dimensions remain unchanged.
- Python 3.8 compilation, active Markdown file links and `git diff --check` pass.
- Current first-party source/guides contain no retired task fields outside the
  compatibility reader. Unrelated vendor latent-model one-hot operations remain.
  Only the explicitly named robomimic recipe generator changed in vendor trees.

## Hardware work still required

No live robot motion was performed during this migration. Teach the two scan
poses, four arm/bin targets, two receiving-return targets and any clearance via
points on the revised layout. Set verified joint/cable limits and sweep direction,
then commission the local waypoint file. Verify fixture and parcel clearance,
release height, stationary scanner reads, wrist travel, emergency stopping and
actual control-loop timing before production trials. Existing manual calibration
and explicit recovery/homing utilities retain their control paths.

Collect 50 fresh accepted demonstrations per medium, including the flat-media
carry flips, then train production checkpoints. The smoke models establish
software compatibility only. Operator keys determine physical outcomes; driver
gripper/velocity placeholders do not establish grasp success. Medium recognition
remains manual; the image classifier is deferred as specified.
