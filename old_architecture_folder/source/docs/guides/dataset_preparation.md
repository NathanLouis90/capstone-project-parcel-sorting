# Prepare recordings for training

Use this guide after recording with [Policy A](policy_a.md) or [Policy B](policy_b.md). Run `bash` blocks in a Bash terminal from the repository root with `Xtrainer` activated. Replace example values, then run assignments and commands in order in that same terminal; repeat assignments in a new terminal. No robot connection is needed.

A project contains episodes, where one episode is one demonstration. Choose any number of episodes per project. Optional names are `<set_id>_<medium>_A` and `<set_id>_<medium>_B_bin_<bin>`; set IDs label collections, not a required size.

## 1. Register the project

Edit [scripts/scripts_config.py](../../scripts/scripts_config.py) to add the exact recording folder name under `PREPARE_ACT_DATASETS["projects"]`. This is a file edit, not a terminal command. The policy guides show the task-specific values. Do this before running preparation or training.

| Field | Meaning |
| --- | --- |
| `policy_stage` | `A` or `B`, matching the recorded task |
| `medium` | `poly_mailer`, `carton` or `envelope` |
| `bin_index` | `None` for A; the recorded destination, `0` or `1`, for B |
| `episode_len` | Maximum steps allowed for a recording and a model run; choose enough for the longest accepted demonstration |
| `train_ratio` | Training fraction for Dobot ACT, such as `0.8`; the rest is used to check the model |
| `camera_names` | Normally `top`, `left_wrist` and `right_wrist` |
| `control_period_ms` | Nominal recording period for curation compatibility, normally `40`; legacy metadata uses the shared configured period with a warning |

`episode_len` is the number of steps in one episode, not the number of demonstrations. At 25 steps per second, 400 steps allow about 16 seconds. Longer envelope demonstrations may need a larger limit. Restart tools after changing configuration.

## 2. Check and review

Replace `your_recording_folder` and `your_episode_folder` below, then paste and run the entire block in your Bash terminal. These lines set `PROJECT` and `EPISODE_ID` for this and later commands:

```bash
PROJECT="your_recording_folder"
EPISODE_ID="your_episode_folder"
python3 scripts/count_episodes.py
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT"
python3 -m barcode_scanning.recording \
  --inspect-episode "datasets/$PROJECT/collect_data/$EPISODE_ID"
```

The counter's **Complete** means recording stopped with at least one frame; it does not mean the parcel task succeeded. Preparation checks that images and joint frames match, episode details agree with the project, and lengths fit the configured limit.

Preparation also reports warnings for review:

| Warning | What to inspect |
| --- | --- |
| Start/end differs from home | Both arms should begin and finish at the agreed home pose |
| Idle arm moves or opens its gripper | The unused arm should stay home with its gripper closed |
| Measured recording rate differs from 25 Hz | Playback speed may differ from the demonstration |
| Joint angle exceeds a limit | A recorded angle would be refused when running the model; check the third and fourth joints of each arm |

Joint limits are in `RUN_INFERENCE` in `experiments/experiments_config.py`. For example, the right arm's fourth joint must stay below `0.6` radians. Do not widen limits solely to suppress a warning; inspect the demonstrated motion and clearance.

### Review all episodes with one command

Run this Bash command after setting `PROJECT` above. It plays the three raw camera views for each unreviewed episode:

```bash
python3 scripts/review_episodes.py --project "datasets/$PROJECT"
```

Click the video window so it receives your key presses. Use **a** to accept, **r** to reject, **s** to skip, **p** to replay, **space** to pause/resume, or **q** to quit. At the end, the last frame stays visible until you choose. Decisions are saved immediately; running the command again resumes with unreviewed episodes. Add `--include-reviewed` to revisit earlier choices.

The tool saves the decision in the raw episode and any matching HDF5 files. Before accepting an existing conversion, it verifies episode details, joint/action data and camera data against the raw recording. It changes review fields only; camera and action datasets are not rewritten. If data or conversion settings differ, it refuses synchronization and asks you to rebuild that conversion. Playback size and speed are in `REVIEW_EPISODES` in `scripts/scripts_config.py`.

No project registration is needed just to review a folder. Preparation and Dobot training still need the registration described above. With no graphical display, use `--terminal-only` after watching the existing videos elsewhere; it asks for decisions in the terminal.

### What happens to rejected recordings

Rejecting an episode marks its review status as `rejected` in the raw episode and matching converted HDF5 files. It does not delete or move recordings, images, videos or converted files. Preparation does not convert rejected raw episodes, and robomimic conversion skips rejected episodes when building a new dataset.

The review command normally shows only unreviewed episodes. To review only rejected recordings, run this in the same terminal:

```bash
python3 scripts/review_episodes.py --project "datasets/$PROJECT" --only-rejected
```

Press **a** to accept a recording after confirming it meets the task criteria, **r** to keep it rejected, or **s** to leave its status unchanged. Accepted and unreviewed recordings are excluded from this queue. Running the command again shows only recordings still marked rejected. To review one specific episode, use `--episodes EPISODE_ID`; to revisit all decisions, use `--include-reviewed` instead of `--only-rejected`.

Changing a decision does not update an existing robomimic dataset, its train/validation split or a trained checkpoint. Create a new dataset and split from the current accepted recordings, then retrain to apply the change to a model.

The Dobot ACT trainer reads every HDF5 file in its training folder and does not filter by review status. If you reject an already-converted episode, prepare a fresh training project containing only accepted recordings before retraining with Dobot ACT. Keep the original project for reviewing or reconsidering its recordings.

To remove rejected recordings from active folders while retaining an undo path, use [dataset curation](dataset_curation.md):

```bash
python3 scripts/curate_datasets.py quarantine --project "$PROJECT" --dry-run
python3 scripts/curate_datasets.py quarantine --project "$PROJECT"
```

Quarantine moves rejected raw episodes and matching HDF5/videos into `rejected_data/`, which count, review, preparation and conversion tools exclude. Restore returns them without changing review status. Curation can also move accepted preliminary/set02 episodes into set01. It preserves episode metadata, logs file hashes and paths, and marks affected training folders stale. Neither preparation nor training can reuse those old conversions.

After reaching the chosen accepted count, copy and reconvert into a fresh registered project. For example, once `set01_poly_mailer_A` has 50 accepted episodes:

```bash
python3 scripts/prepare_act_datasets.py \
  --dataset-name set01_poly_mailer_A \
  --rebuild-to train50_poly_mailer_A --convert
```

The destination must be unused and registered. Only accepted raw episodes are copied; old HDF5 files, rejections and unreviewed episodes stay behind. All raw validation runs before copying. Conversion failures leave an incomplete-build marker that blocks training. The source and its stale marker remain unchanged. Use the guide's equivalent 100-demonstration snapshot when enough data is ready. Names do not enforce counts: check `curate_datasets.py status` first.

### Batch decisions for recordings you already reviewed

If you have already watched the selected recordings and confirmed they all succeeded, you can save their decisions together:

```bash
python3 scripts/review_episodes.py --project "datasets/$PROJECT" --set-status accepted
```

This explicitly marks the selected unreviewed episodes accepted; it does not judge physical success automatically. Prior accepted/rejected decisions are left alone by default. Use `--episodes EPISODE_ID_1 EPISODE_ID_2` to select particular episode folder names. Add `--dry-run` to check the operation without changing files. For a batch operation, all selected files are checked before any decision is written.

If raw episodes already contain your decisions but the HDF5 files still say unreviewed, synchronize them without choosing new statuses:

```bash
python3 scripts/review_episodes.py --project "datasets/$PROJECT" --sync-review-status
```

The individual command remains available and now also updates matching HDF5 review fields:

```bash
python3 scripts/prepare_act_datasets.py \
  --review-episode "datasets/$PROJECT/collect_data/$EPISODE_ID" \
  --review-status accepted
```

Use `rejected` for failed episodes. Review decisions are yours; file checks do not prove successful grasping or placement. In particular, reject wrong-bin placement, interrupted motion and searching/wiggling at the scanner.

## 3. Convert accepted recordings

If matching HDF5 files already exist and the review tool synchronized them, skip this step and continue to training or robomimic conversion. For recordings that have not been converted yet, run:

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT" --convert
```

Only accepted episodes are converted. Outputs are HDF5 files in `train_data/`, videos in `output_videos/` and logs in `conversion_logs/`. Review the videos before training.

Episodes with `source: "rollout"` are excluded by default. Intentional inclusion requires `--allow-rollouts` and a registered project name containing a separate `rollout` or `rollouts` word. Robomimic conversion requires the same opt-in and an output dataset name that identifies rollouts. Automatic rollout capture is outside this curation change.

Finish collecting the project before conversion. The conversion helper refuses existing output files rather than replacing them. For another collection, use another project folder. For review-status changes alone, use the review tool to synchronize existing conversions; rebuilding images is unnecessary when its data checks pass. If the raw recording itself changed, rebuild in a fresh output project. If you already created a robomimic dataset/split, create a new one after changing review decisions.

Robomimic conversion excludes rejected episodes. The Dobot ACT trainer reads all files in its training folder, so rebuild an accepted-only training project before retraining with that software if existing converted files include rejected episodes.

Without `--dataset-name`, the tool selects registered projects whose `collect_data/` folders exist under the chosen root. Historical aliases and future snapshot names without recordings are skipped. A `--root PATH` override affects preparation only; update the configured root too if training from that location.

Next: [Dobot ACT training](act_training.md) for robot tests, or [ACT/DP training](act_dp_training.md) for the algorithm comparison.
