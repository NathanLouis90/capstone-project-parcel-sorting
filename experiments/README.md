# Robot operation

These programs start the robot server, record demonstrations and run trained models. Run from the repository root in the Python 3.8 `Xtrainer` environment.

Start with the main README's [software setup](../README.md#software-setup) and [quick startup](../README.md#quick-startup). Use the [Policy A guide](../docs/guides/policy_a.md) or [Policy B guide](../docs/guides/policy_b.md) for task-specific commands.

## Choose a program

| File | What it does |
| --- | --- |
| `launch_nodes.py` | Starts the robot server so other programs can communicate with both follower arms and grippers |
| `run_control.py` | Uses the leader handles to move the followers and record three camera views, joint states and demonstrated actions |
| `run_inference.py` | Loads a Dobot ACT checkpoint and runs one task on the robot |
| `robot_home.py` | Reads controller status, checks poses, and performs homing or recovery when explicitly requested |
| `experiments_config.py` | Holds robot addresses, recording settings, camera settings and motion limits |

## Configure settings

Edit [experiments_config.py](experiments_config.py), then restart the affected program. Command-line arguments override the settings that support them.

| Section | What to configure |
| --- | --- |
| `LAUNCH_NODES` | Robot IP addresses and the server host/port |
| `RUN_CONTROL` | Recording location, display, camera flips, button timing and allowed working area |
| `RUN_INFERENCE` | Checkpoint filename, camera settings, initial gripper values and allowed robot movement |
| `CONTROL` | Time between recording/model steps; default 40 ms, or 25 steps per second |
| `ROBOT_HOME` | Home poses, selected arm, speed and timeouts |

Camera serials, USB ports and calibration come from your local `scripts/dobot_config/dobot_settings.ini`. See [device settings](../scripts/README.md#device-settings). Scanner settings are in `barcode_scanning/barcode_scanning_config.py`.

## Record demonstrations

Start the server in terminal 1:

```bash
python3 experiments/launch_nodes.py
```

In terminal 2, run the recorder command from your policy guide. Choose a project name for each collection; it does not need to contain a set number or episode count.

The yellow **A** and green **B** buttons are hardware controls, not policy names:

1. Support a leader handle. A short yellow press toggles its lock.
2. A long yellow press enables or disables follower synchronization. Wait for alignment before moving the leader.
3. A green press/release starts recording; the next press/release stops it.
4. Stop recording and disable synchronization before exiting or resetting the parcel by hand.

See the [recording guide](../docs/guides/recording_guide.md) for exact button timing. Both followers can move during startup, including an arm you will not use in the demonstration. Keep both paths clear. Use the physical emergency stop when needed.

## Run a model or return home

`run_inference.py` requires a registered `--task-name` and an explicit `--checkpoint-dir`. It uses that task's arm configuration and refuses a run longer than its configured training length. It checks proposed joint angles and gripper positions before sending each action to the robot.

Follow the [inference and evaluation guide](../docs/guides/inference_evaluation.md). The runner accepts Dobot ACT checkpoints; robomimic model deployment and automatic A/B switching are not available yet.

`robot_home.py` reads status without movement when run without motion flags. Use its [homing and recovery guide](../docs/guides/robot_home_guide.md) before requesting movement. Help does not start either program:

```bash
python3 experiments/run_inference.py --help
python3 experiments/robot_home.py --help
```
