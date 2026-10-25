# Setup and dataset tools

Run from the repository root in Python 3.8 `Xtrainer`.
Follow [terminal preparation](../docs/terminal_commands.md) for activation;
read the [terminal reference](../docs/README.md#terminal-syntax) for syntax.

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

Fresh projects default to `<medium>_<label_face>`, such as `poly_mailer_bottom`.
After reviewing episodes, run `python3 scripts/train_models.py` to manage datasets
and train ACT, DP, or both. The menu discovers raw collections automatically,
creates move destinations, saves settings, and generates training files.
Custom names need no registration in this workflow. The older vendor preparation
tools still require registration under `PREPARE_ACT_DATASETS["projects"]`.
Each episode ends with a held scan pose; release and home are outside the demo.

| Tool | Purpose |
| --- | --- |
| `count_episodes.py` | Count complete, interrupted, and unknown recordings |
| `review_episodes.py` | Review raw episodes and synchronize converted statuses |
| `train_models.py` | Menu: delete rejected recordings, move, combine, split, configure, name, train ACT/DP, inspect reports, and reuse frozen model data |
| `prepare_act_datasets.py` | Validate and convert accepted fresh recordings |
| `curate_datasets.py` | Quarantine, restore, transfer, merge and audit |
| `convert_to_robomimic.py` | Build one medium dataset with a frozen split |
| `configure_robomimic.py` | Generate matched ACT and DP training configs |

See [recording](../docs/guides/recording/protocol.md),
[preparation](../docs/guides/datasets/preparation.md), and
[training menu](../docs/guides/training/menu.md) for procedures.
Use the [topic READMEs](../docs/guides/README.md) for explanations and command options.
Use [curation](../docs/guides/datasets/curation.md) for file operations.
Converted images become RGB for
robomimic; vendor ACT retains its BGR preprocessing. `script_collect2train.py`
is the individual converter called by preparation.

Raw files live under `datasets/<project>/`. Review decisions alone leave rejected
files on disk; menu option 2 permanently deletes them after confirmation.
The menu reads accepted raw episodes directly and prepares immutable training
data in `datasets/.training_cache/`, bypassing stale legacy conversions.
Models and readable settings live under `ckpt/<model_name>/`. Existing checkpoints
and their frozen data are preserved. The older vendor conversion workflow still
requires rebuilding stale training folders.
