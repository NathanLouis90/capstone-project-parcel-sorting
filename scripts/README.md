# Setup utilities and dataset preparation

Run from the repository root in the Python 3.8 `Xtrainer` environment. Counting and preparation are offline; device setup and calibration access hardware.

## Files and provenance

| File | Purpose | Origin |
| --- | --- | --- |
| `1_find_port.py` | Finds leader/gripper serial ports and rewrites hardware settings | Dobot, adapted for configuration |
| `2_get_offset.py` | Calibrates leader joint/gripper offsets and rewrites hardware settings | Dobot, adapted for configuration |
| `3_just_buttonA.py` | Standalone leader/button and torque-lock utility | Dobot, adapted for configuration |
| `4_collect2train_data.py` | Older single-project batch conversion wrapper | Dobot, adapted for configuration and interpreter/path handling |
| `5_camera_read.py` | Camera preview | Dobot, adapted for configurable flips |
| `6_dataset_count.py` | Reports maximum observation frames per episode; creates expected folders | Dobot, adapted for paths; does not count episodes |
| `script_collect2train.py` | Converts one episode to compressed HDF5 and a review video | Dobot, adapted to preserve metadata, reject mismatches without deleting raw files, and refuse HDF5 overwrites |
| `format_obs.py` | Writes state/action pickle files | Dobot |
| `function_util.py` | Logging, timing, videos and device-permission helpers | Dobot, adapted for configuration/path handling |
| `manipulate_utils.py` | Startup poses, alignment, motion checks and hardware INI loading | Dobot, adapted for configuration |
| `count_episodes.py` | Counts episode folders and metadata status without changing files | Capstone addition |
| `prepare_act_datasets.py` | Validates configured A/B projects and optionally converts them | Capstone addition |
| `scripts_config.py` | Helper defaults and shared ACT dataset/task settings | Capstone addition |
| `__init__.py` | Python package marker | Dobot |
| `dobot_config/dobot_settings.example.ini` | Blank hardware-settings schema | Capstone template based on the Dobot schema |

Capstone additions/adaptations are work developed for Adiel Firqin's project. Base helpers, interfaces, and learning algorithms retain their upstream authorship.

## Configure hardware and helpers

Actual `dobot_config/dobot_settings.ini` stays local. It contains camera identities, ports, calibration, gripper settings and a workstation passcode used by legacy Dobot permission helpers. The example contains no password or calibrated device values. Copy it only if the actual file is absent, configure devices, and calibrate; do not overwrite working calibration.

Port finding and offset calibration are setup operations, not routine steps when changing datasets. Stop the standalone button utility and camera preview before recording to avoid sharing devices between programs.

Edit `scripts_config.py`, then restart the affected program. `SCRIPT_1_FIND_PORT` through `SCRIPT_6_DATASET_COUNT`, `FUNCTION_UTIL`, `MANIPULATE_UTILS`, and `SCRIPT_COLLECT2TRAIN` control the matching helpers. `COUNT_EPISODES["root_dir"]` controls the counter's root.

## Configure dataset projects

`PREPARE_ACT_DATASETS` supplies both preparation settings and ACT task registration:

| Setting | Meaning |
| --- | --- |
| `root_dir` | Parent of the project folders |
| Key under `projects` | Exact folder name and ACT `--task_name` |
| `policy_stage`, `medium`, `bin_index` | Expected metadata; A uses `bin_index=None` |
| `episode_len` | Maximum accepted recording frames and task rollout horizon; not completion detection |
| `train_ratio` | Training fraction for a single-folder task |
| `camera_names` | ACT camera inputs |

For a second set, copy the first-set entries and rename the copies to `second_set_poly_mailer_A`, `second_set_poly_mailer_B_bin_0`, and `second_set_poly_mailer_B_bin_1`. Retain A/None, B/0 and B/1 respectively. Carton projects use `medium="carton"`. Keep both sets registered to train them individually, or list only the projects you currently want to prepare. Removing a configuration entry does not delete data.

## Count, validate and convert

```bash
python3 scripts/count_episodes.py
python3 scripts/prepare_act_datasets.py --dataset-name second_set_poly_mailer_A
python3 scripts/prepare_act_datasets.py --dataset-name second_set_poly_mailer_A --convert
```

`--dataset-name` is optional: without it every configured project is selected. If only the three second-set projects are listed, `python3 scripts/prepare_act_datasets.py --convert` converts all three. If already-converted first-set projects remain listed, select a new project explicitly; existing HDF5 files are refused, not overwritten or skipped.

The counter's "Complete" means recording ended with a nonzero metadata frame count, not verified physical success. Preparation checks recording metadata, matching frame identifiers/counts, expected stage/medium/bin and length. Review videos for successful demonstrations before training.

```text
datasets/<project>/
├── collect_data/<timestamp>/  # raw frames and metadata
├── train_data/               # episode_init_<index>.hdf5
├── output_videos/            # review videos
└── conversion_logs/         # conversion logs
```

Finish collecting a set before conversion. The helper enumerates episodes from index 0 and cannot append to an already-converted project. Use a separate project for a later set. A CLI `--root` override affects that invocation only; update the configured root before training elsewhere. See the [ACT guide](../docs/guides/act_poly_mailer_training.md) for commands.

## Train both sets together

Preparation currently registers one folder per task. Add combined tasks after the generated project loop in `ModelTrain/constants.py`, before the fixed constants:

```python
for suffix in ("A", "B_bin_0", "B_bin_1"):
    TASK_CONFIGS[f"combined_poly_mailer_{suffix}"] = {
        "dataset_dir": [
            str(DATASETS_ROOT / f"first_set_poly_mailer_{suffix}" / "train_data"),
            str(DATASETS_ROOT / f"second_set_poly_mailer_{suffix}" / "train_data"),
        ],
        "episode_len": 400,
        "train_ratio": 0.8,
        "camera_names": ["top", "left_wrist", "right_wrist"],
    }
```

This is a recipe, not configuration already installed by the helper. Convert both sets first. No file merging/renaming is needed. Select `--task_name combined_poly_mailer_A` and a fresh `--ckpt_dir ./ckpt/act_combined_poly_mailer_A`; repeat for both B tasks.

The vendor multi-folder loader holds out validation only from the first folder. With 25 episodes in each and `train_ratio=0.8`, this gives 45 training and 5 validation episodes, not 40/10. Holding out examples from both sets requires another layout or loader change. Keep A, B bin 0 and B bin 1 separate for this baseline because ACT destination conditioning is not implemented.
