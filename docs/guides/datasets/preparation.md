# Review and prepare datasets

Prepare [one terminal](../../terminal_commands.md) in the repository root with
`Xtrainer` activated. Stop recording before preparing data. No robot server is
needed. Read the [dataset README](README.md) for file formats, playback, options,
and conversion rules.

## 1. Count and review episodes

Choose the collection and keep this terminal open for the remaining steps:

```bash
PROJECT=poly_mailer_bottom
python3 scripts/count_episodes.py --details
python3 scripts/review_episodes.py --project "datasets/$PROJECT"
```

Replace `poly_mailer_bottom` with another registered medium/face or custom
project. Review each collection you intend to train on.

1. Focus the video window.
2. Check a home start, prompt motion, successful grasp, correct label face, and
   a stationary held scan pose at the end. Check the assisting/unused arm is home.
3. Press `a` to accept, `r` to reject, `s` to skip, `p` to replay, space to pause,
   or `q` to quit. Inspect physical success yourself.
4. Read any scan-pose or rate warnings before accepting. Teach missing scan poses
   before collecting further data. Do not force a tighter grip to silence the
   [current gripper check](../recording/README.md#gripper-width-and-handoff).
5. Add `--include-reviewed` to revisit decisions, or `--only-rejected` to revisit
   rejections. Do not combine those two options.
6. Use `--episodes EPISODE_ID_1 EPISODE_ID_2` for specific episode folder names.
   Use `--terminal-only` only after inspecting the recordings elsewhere.

Never load untrusted observation pickles.

### Apply decisions already made

Replace `EPISODE_ID` with an actual folder name. Preview each operation separately:

```bash
python3 scripts/review_episodes.py --project "datasets/$PROJECT" \
  --episodes EPISODE_ID --set-status rejected --dry-run
python3 scripts/review_episodes.py --project "datasets/$PROJECT" \
  --sync-review-status --include-reviewed --dry-run
```

Inspect the proposed operation, then rerun that command without `--dry-run` to
apply it. Do not combine `--set-status` with `--sync-review-status`. Use batch
`--dry-run` only with one of those two modes.

## 2. Validate, then convert accepted episodes

Keep using the terminal where `PROJECT` is set. Validate first:

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT"
```

Resolve errors and inspect warnings. Then convert:

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT" --convert
```

Check `train_data/`, `output_videos/`, and `conversion_logs/` beneath the project.
For conversion failures, inspect the printed log path. Do not overwrite existing
conversions; follow the rebuild procedure below. Keep rollout inclusion disabled
for demonstration collections.

## 3. Rebuild after decisions change

1. Register a new project such as `poly_mailer_v2` in
   `PREPARE_ACT_DATASETS["projects"]` in `scripts/scripts_config.py`. Use the same
   medium and compatible camera, rate, horizon, and any label-face settings.
2. Choose a destination folder that does not exist.
3. Rebuild accepted episodes from the source project:

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT" \
  --rebuild-to poly_mailer_v2 --convert
```

4. Inspect the new conversions and videos.
5. Select the new project for [ACT/DP training](../training/act_dp.md) or
   [vendor ACT](../training/vendor_act.md). Create fresh downstream dataset,
   split, configuration, and checkpoint outputs as needed.

Rebuild before retraining after rejecting converted episodes. Do not train from
stale or incomplete folders. Record fresh schema-3 demonstrations rather than
trying to migrate unsupported archived recordings.
