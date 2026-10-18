# Review and prepare datasets

## Review every episode

```bash
PROJECT=poly_mailer
python3 scripts/count_episodes.py --details
python3 scripts/review_episodes.py --project "datasets/$PROJECT"
```

Focus the video window. Press `a` to accept, `r` to reject, `s` to skip, `p` to
replay, space to pause, or `q` to quit. Decisions are saved immediately and
synchronized with matching HDF5 files. `--include-reviewed` revisits all decisions;
`--only-rejected` selects rejections. Physical success remains an operator decision.

Check a home start, a prompt start of motion, a successful grasp, and a held scan
pose at the end. The holding arm must meet FK position/orientation tolerances,
both gripper commands must be closed, the other arm must be home, and joints
must settle for at least 0.5 seconds. Missing local scan poses produce a warning;
teach them before collecting real data. The driver reports placeholder velocities,
so settling uses differences between joint observations.

## Validate and convert

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT"
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT" --convert
```

Only accepted, complete, fresh schema-3 episodes enter new training files.
Camera/observation frame identifiers must match. Output includes `train_data/`,
`output_videos/`, and `conversion_logs/`. Originals remain untouched.

Conversion refuses overwrites. Register another project of the same medium and
use `--rebuild-to NEW_PROJECT --convert` to rebuild accepted-only data there.
A rejection does not erase raw recordings or alter trained checkpoints. Existing
Dobot training folders must be rebuilt before retraining because its loader reads
all HDF5 files. Curation marks affected conversions stale; stale/incomplete
folders are refused by training and downstream conversion.

Old recordings remain readable through the compatibility reader in the local
archive. Do not reuse or truncate them for the new 50-demonstration collections.
