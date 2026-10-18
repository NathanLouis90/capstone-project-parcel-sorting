# Setup and dataset tools

Run from the repository root in Python 3.8 `Xtrainer`.
See [terminal commands](../docs/terminal_commands.md) for activation and syntax.

## Local hardware settings

```bash
cp -n scripts/dobot_config/dobot_settings.example.ini scripts/dobot_config/dobot_settings.ini
```

`cp` copies the first path (the example) to the second path (your local settings).
`-n` preserves an existing destination file, so rerunning this command does not
replace working calibration. Open the local file in your editor afterward.

Fill in camera serials, ports and calibration for this hardware. Preserve working
offsets. Keep credentials only in the ignored local INI. `1_find_port.py` detects
ports, `2_get_offset.py` calibrates, `3_just_buttonA.py` positions leaders, and
`5_camera_read.py` previews cameras. Follow the hardware manuals; stop helper
programs before recording.

Run a helper with `PYTHONPATH=. python3 scripts/1_find_port.py`, replacing the
filename with the helper you need. `PYTHONPATH=.` makes repository imports work;
these examples take no additional arguments. The leader button helper only
locks/unlocks leaders; use `run_control.py` to make followers track them.

## Data workflow

Fresh projects default to `envelope`, `poly_mailer`, and `carton`. Register custom
names under `PREPARE_ACT_DATASETS["projects"]` in `scripts_config.py`, including
schema 3, medium, episode length, training fraction, cameras and control period.
Each episode ends with a held scan pose; release and home are outside the demo.

| Tool | Purpose |
| --- | --- |
| `count_episodes.py` | Count complete, interrupted, and unknown recordings |
| `review_episodes.py` | Review raw episodes and synchronize converted statuses |
| `prepare_act_datasets.py` | Validate and convert accepted fresh recordings |
| `curate_datasets.py` | Quarantine, restore, transfer, merge and audit |
| `convert_to_robomimic.py` | Build one medium dataset with a frozen split |
| `configure_robomimic.py` | Generate matched ACT and DP training configs |

See [recording](../docs/guides/recording/README.md),
[preparation](../docs/guides/datasets/preparation.md), and
[training](../docs/guides/training/act_dp.md) for commands and argument explanations.
Use [curation](../docs/guides/datasets/curation.md) for file operations.
Converted images become RGB for
robomimic; vendor ACT retains its BGR preprocessing. `script_collect2train.py`
is the individual converter called by preparation.

Raw files, training files, videos and logs live under `datasets/<project>/`.
Rejected files stay on disk. Review decisions and curation do not change trained
checkpoints. Stale folders require fresh conversion before training.
