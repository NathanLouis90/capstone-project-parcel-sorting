# Prepare recordings for training

Use this guide after recording with [Policy A](policy_a.md) or [Policy B](policy_b.md). All commands run from the repository root in `Xtrainer`; no robot connection is needed.

A project contains episodes, where one episode is one demonstration. Choose any number of episodes per project. Optional names are `<set_id>_<medium>_A` and `<set_id>_<medium>_B_bin_<bin>`; set IDs label collections, not a required size.

## 1. Register the project

Add the exact recording folder name to `PREPARE_ACT_DATASETS["projects"]` in [scripts/scripts_config.py](../../scripts/scripts_config.py). The policy guides show the task-specific values. Do this before running preparation or training.

| Field | Meaning |
| --- | --- |
| `policy_stage` | `A` or `B`, matching the recorded task |
| `medium` | `poly_mailer`, `carton` or `envelope` |
| `bin_index` | `None` for A; the recorded destination, `0` or `1`, for B |
| `episode_len` | Maximum steps allowed for a recording and a model run; choose enough for the longest accepted demonstration |
| `train_ratio` | Training fraction for Dobot ACT, such as `0.8`; the rest is used to check the model |
| `camera_names` | Normally `top`, `left_wrist` and `right_wrist` |

`episode_len` is the number of steps in one episode, not the number of demonstrations. At 25 steps per second, 400 steps allow about 16 seconds. Longer envelope demonstrations may need a larger limit. Restart tools after changing configuration.

## 2. Check and review

Replace both values below with names from your recordings:

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

Review the raw camera images in frame order, or an existing review video. Reject failed grasping, wrong-bin placement, interrupted motion and searching/wiggling at the scanner. Save your decision for each episode:

```bash
python3 scripts/prepare_act_datasets.py \
  --review-episode "datasets/$PROJECT/collect_data/$EPISODE_ID" \
  --review-status accepted
```

Use `rejected` instead of `accepted` for a failed episode. Repeat for each episode; this command marks only the selected one.

## 3. Convert accepted recordings

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT" --convert
```

Only accepted episodes are converted. Outputs are HDF5 files in `train_data/`, videos in `output_videos/` and logs in `conversion_logs/`. Review the videos before training.

Finish collecting the project before conversion. The helper refuses existing output files rather than replacing them. For another collection, use another project folder. If review decisions change after conversion, rebuild in a fresh output project; changing a raw review status does not update an existing HDF5 file.

Without `--dataset-name`, the tool selects every registered project. A `--root PATH` override affects preparation only; update the configured root too if training from that location.

Next: [Dobot ACT training](act_training.md) for robot tests, or [ACT/DP training](act_dp_training.md) for the algorithm comparison.
