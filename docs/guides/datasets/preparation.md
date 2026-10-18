# Review and prepare datasets

Run from the repository root with `Xtrainer` activated. Review and conversion
need no robot server. See [terminal setup](../../terminal_commands.md).

## 1. Count and review episodes

```bash
PROJECT=poly_mailer
python3 scripts/count_episodes.py --details
python3 scripts/review_episodes.py --project "datasets/$PROJECT"
```

`PROJECT=poly_mailer` selects the example collection in this terminal. Use
`envelope`, `carton`, or a custom registered project name for another collection.

| Argument | Meaning |
| --- | --- |
| `count_episodes.py --details` | Print totals plus each episode's medium, label face, and review status. |
| `count_episodes.py --project poly_mailer` | Optional: count only that exact project folder instead of every project. |
| `count_episodes.py --root datasets` | Optional: set the parent dataset directory; `datasets/` is the default. |
| `review_episodes.py --project "datasets/$PROJECT"` | Open recordings from this project folder; here the path is `datasets/poly_mailer`. Unlike the count tool, this option takes a folder path. |

Focus the video window. Press `a` to accept, `r` to reject, `s` to skip, `p` to
replay, space to pause, or `q` to quit. Decisions are saved immediately and
synchronized with matching HDF5 files. Physical success remains an operator decision.

The default review queue contains unreviewed episodes. Add options after the
project path to select a different queue:

| Review option | Meaning |
| --- | --- |
| `--include-reviewed` | Revisit accepted and rejected episodes as well as unreviewed ones. |
| `--only-rejected` | Review only current rejections. Do not combine with `--include-reviewed`. |
| `--episodes EPISODE_ID_1 EPISODE_ID_2` | Select exact folder names under `collect_data/`; replace the example IDs. |
| `--terminal-only` | Ask for decisions in the terminal without opening video. Inspect the videos separately first. |

For decisions already made, batch updates are available:

```bash
python3 scripts/review_episodes.py --project "datasets/$PROJECT" \
  --episodes EPISODE_ID --set-status rejected --dry-run
python3 scripts/review_episodes.py --project "datasets/$PROJECT" \
  --sync-review-status --include-reviewed --dry-run
```

Replace `EPISODE_ID` with the actual episode folder name. `--set-status rejected`
plans that review decision; other values are `accepted` and `unreviewed`.
`--sync-review-status` copies existing raw decisions into matching HDF5 files
without choosing a new decision. These modes are mutually exclusive.
`--dry-run` checks the batch operation without writing; remove it to apply the
same operation. It is only supported with one of these two batch modes.

Check a home start, a prompt start of motion, a successful grasp, and a held scan
pose at the end. The holding arm must meet FK position/orientation tolerances,
both gripper commands must be closed, the other arm must be home, and joints
must settle for at least 0.5 seconds. Missing local scan poses produce a warning;
teach them before collecting real data. The driver reports placeholder velocities,
so settling uses differences between joint observations.

## 2. Validate, then convert accepted episodes

Keep using the terminal where you set `PROJECT`. First check the project,
then run conversion if the check succeeds:

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT"
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT" --convert
```

| Argument | Meaning |
| --- | --- |
| `--dataset-name "$PROJECT"` | Select a name registered in `PREPARE_ACT_DATASETS["projects"]` in `scripts/scripts_config.py`. This is a name, not a folder path. |
| `--convert` | Write the accepted episodes' HDF5 files, review videos, and conversion logs. Without this switch, the command validates and reports only. |
| `--root datasets` | Optional: use another parent dataset directory. Keep the training configuration pointed at the same root. |
| `--allow-rollouts` | Optional: include rollout sources only in explicitly named `rollout`/`rollouts` projects. Leave it off for demonstration collections. |

Only accepted, complete, fresh schema-3 episodes enter new training files.
Camera/observation frame identifiers must match. Output includes `train_data/`,
`output_videos/`, and `conversion_logs/`. Originals remain untouched.

## 3. Rebuild after decisions change

Conversion refuses overwrites. Register `poly_mailer_v2` as another project of
the same medium in `scripts/scripts_config.py`, then use a destination folder
that does not exist yet:

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT" \
  --rebuild-to poly_mailer_v2 --convert
```

`--dataset-name` selects the source collection. `--rebuild-to poly_mailer_v2`
copies its accepted raw episodes into `datasets/poly_mailer_v2/` and converts
them there. `--convert` is required with `--rebuild-to`. Choose a fresh registered
name for each rebuild; the source recordings are preserved.

A rejection does not erase raw recordings or alter trained checkpoints. Existing
Dobot training folders must be rebuilt before retraining because its loader reads
all HDF5 files. Curation marks affected conversions stale; stale/incomplete
folders are refused by training and downstream conversion.

Legacy recordings remain readable through the compatibility reader. Do not reuse
or truncate them for the new 50-demonstration collections.
