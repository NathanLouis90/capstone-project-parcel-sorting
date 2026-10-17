# Setup and dataset tools

Use these tools to configure devices, check recordings and create training files. Run commands from the repository root in the Python 3.8 `Xtrainer` environment.

Run the `bash` blocks in a Bash terminal, after replacing example values. A line such as `PROJECT="your_folder"` sets a variable for later commands in that same terminal. If an instruction names a Python configuration file, edit that file instead. See [command examples](../README.md#how-to-use-command-examples).

For complete task workflows, use the [Policy A guide](../docs/guides/policy_a.md) or [Policy B guide](../docs/guides/policy_b.md).

## Device settings

The repository includes [dobot_settings.example.ini](dobot_config/dobot_settings.example.ini) with example values and a blank password. On a new checkout, create your local settings file:

```bash
cp -n scripts/dobot_config/dobot_settings.example.ini scripts/dobot_config/dobot_settings.ini
```

`cp -n` keeps an existing settings file. Edit the local copy to set camera serial numbers, USB ports, motor IDs and calibration values for your hardware. The comments identify fields that need checking. Zero offsets are placeholders, not a calibrated robot configuration.

The local `dobot_settings.ini` is excluded from Git. The port and calibration tools update this local file; they do not update the shared template. Some device-permission tools use `[COMPUTER] passcode` for local sudo access. If needed, enter it only in your local file.

Use the [Dobot setup manual](../docs/provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf) for calibration. Stop the leader-button helper and camera preview before starting the recorder.

## Choose a tool

| File | What it does |
| --- | --- |
| `1_find_port.py` | Finds leader and gripper USB ports and saves them in the local settings file |
| `2_get_offset.py` | Measures leader joint and gripper offsets and saves calibration values |
| `3_just_buttonA.py` | Lets you unlock, position and lock the leader handles before recording |
| `5_camera_read.py` | Shows the three camera views so you can check their position and orientation |
| `count_episodes.py` | Counts recorded demonstrations in each project and reports complete or interrupted recordings |
| `prepare_act_datasets.py` | Checks a recording project, saves review decisions, and converts accepted recordings to HDF5 training files and videos |
| `review_episodes.py` | Plays recordings for one-key review, supports batch decisions, and synchronizes review status with existing HDF5 files |
| `curate_datasets.py` | Reports review counts, quarantines/restores rejections, transfers accepted episodes, tops up collections and merges projects with file-hash audit logs |
| `convert_to_robomimic.py` | Combines converted projects into one dataset for ACT or Diffusion Policy |
| `configure_robomimic.py` | Creates ACT and DP training configurations from that dataset |
| `check_destination_swap.py` | Checks whether changing the requested bin changes a trained model's predictions, using recorded data |
| `scripts_config.py` | Holds dataset locations, registered projects and settings for these tools |

`4_collect2train_data.py` and `6_dataset_count.py` are older helpers. Use `prepare_act_datasets.py` and `count_episodes.py` for the workflow above. `script_collect2train.py` converts an individual recording; the preparation tool calls it after checking review status. Other Python files support recording, timing, safety checks and conversion.

## Configure a recording project

A **project** is a named folder containing demonstrations of one task. An **episode** is one recorded attempt. Project names are your choice; no naming pattern or number of episodes is enforced.

Register each project's exact folder name under `PREPARE_ACT_DATASETS["projects"]` in [scripts_config.py](scripts_config.py) before preparation or training. The policy guides show the values to enter.

| Setting | What it controls |
| --- | --- |
| `root_dir` | Parent folder containing recording projects; normally the repository's `datasets/` folder |
| Project name | Folder to prepare; also the task name used by Dobot ACT training |
| `policy_stage`, `medium`, `bin_index` | Task, parcel type and destination recorded in the episode details |
| `episode_len` | Maximum recording length and maximum robot-run steps for that task |
| `train_ratio` | Fraction used for training a single project; the rest is reserved for validation |
| `camera_names` | Camera inputs used by the model |
| `control_period_ms` | Nominal recording period checked by curation; legacy metadata uses the configured shared period with a warning |

Edit other sections of `scripts_config.py` for camera/video conversion and helper settings. Restart programs after editing.

## Count and prepare

Replace `your_recording_folder` with an actual registered folder name, then run the whole block in a Bash terminal. The first line sets `PROJECT`; the following commands use it:

```bash
PROJECT="your_recording_folder"
python3 scripts/count_episodes.py
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT"
```

Then [review the recordings and convert accepted episodes](../docs/guides/dataset_preparation.md). Checking and conversion do not require the robot server or scanner. Without `--dataset-name`, preparation selects existing registered recording projects; selecting one explicitly is easier when projects are at different stages.

To review every unreviewed recording, run this in the same terminal after setting `PROJECT` above:

```bash
python3 scripts/review_episodes.py --project "datasets/$PROJECT"
```

Click the video window, then press **a** to accept or **r** to reject. Decisions are saved immediately. Rejected recordings and existing converted files remain on disk; preparation and robomimic conversion exclude them from new outputs. Existing datasets and checkpoints remain unchanged. Dobot ACT reads every HDF5 file in its training folder, so follow the [rejection guide](../docs/guides/dataset_preparation.md#what-happens-to-rejected-recordings) before retraining if rejected files were already converted. Add `--only-rejected` to review only rejected recordings, or `--include-reviewed` to revisit all previous decisions.

```text
datasets/<project>/
├── collect_data/<episode_id>/  # Camera images, joint data and episode details
├── train_data/                # Converted HDF5 training files
├── output_videos/             # Videos created during conversion
└── conversion_logs/           # Conversion messages and errors
```

To combine recordings or train at different demonstration counts, see [Dobot ACT training](../docs/guides/act_training.md) and [ACT/DP training](../docs/guides/act_dp_training.md).

The current experiment milestones are 50 and 100 accepted demonstrations. Use [dataset curation](../docs/guides/dataset_curation.md) after review to quarantine rejections, reuse preliminary recordings, move accepted set02 episodes into set01, and rebuild fresh `train50_...` / `train100_...` projects. Curation never rewrites episode metadata or moves HDF5 files between training projects. Stale/incomplete conversion markers block preparation, robomimic source conversion and the Dobot training launcher until a fresh project is built.
