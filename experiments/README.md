# Experiment entry points

Run from the repository root in the Python 3.8 `Xtrainer` environment. These entry points connect to real hardware unless explicitly described as offline.

Complete platform setup using the included [Lightweight Base User Guide](../docs/provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf). Refer to the [Operation Guide and FAQ](../docs/provided_dobot/Dobot%20X-Trainer%20Operation%20Guide%20and%20FAQ.pdf) for operating details and troubleshooting.

## Files and provenance

| File | Purpose | Origin |
| --- | --- | --- |
| `launch_nodes.py` | Enables both followers/grippers and serves the bimanual robot through ZMQ | Dobot entry point, adapted for folder configuration |
| `run_control.py` | Leader teleoperation, three-camera/state/action recording, optional A/B and barcode metadata | Dobot recorder, adapted for paths, buttons, metadata, scanner support and configuration |
| `run_inference.py` | Loads an ACT checkpoint and commands robot actions from camera/state observations | Dobot inference example, adapted for configuration |
| `robot_home.py` | Terminal status, pose checks and explicitly requested recovery, homing or short base-Z withdrawal | Capstone addition using the Dobot V3 protocol |
| `experiments_config.py` | Editable defaults grouped by source file | Capstone addition |

Capstone additions and adaptations are work developed for Adiel Firqin's project. The underlying Dobot control stack and learning algorithms retain upstream authorship.

## Configure settings

Edit `experiments_config.py`, then restart the program. Supported CLI flags override defaults.

| Section | Settings |
| --- | --- |
| `LAUNCH_NODES` | Controller IPs, ZMQ host/port and robot configuration |
| `RUN_CONTROL` | Dataset root/project name, A/B stage, medium, scanner capture, demonstrated bin, optional source episode, display, camera flips, workspace limits and button thresholds |
| `RUN_INFERENCE` | Checkpoint directory/file, horizon, startup poses, camera settings and motion/workspace limits |
| `ROBOT_HOME` | Arm IPs/targets, selected arm, ports, speed, timeouts, polling and sample counts |

Camera serials, device ports and calibrated leader/gripper values come from the local `scripts/dobot_config/dobot_settings.ini`. Start with the example INI on a fresh checkout and complete calibration. Scanner identity, destination mapping and scan timing are in `barcode_scanning/barcode_scanning_config.py`.

`RUN_CONTROL["project_name"]` names a recording folder. It is separate from the scripts configuration used to prepare/train data. Recording a new project does not require registering it for training first. Use medium `poly_mailer`, `carton`, or `envelope`. A has no demonstrated bin; B needs bin 0/1 or a valid source episode.

## Record demonstrations

Terminal 1:

```bash
python3 experiments/launch_nodes.py
```

Terminal 2:

```bash
python3 experiments/run_control.py \
  --show-img --project-name second_set_poly_mailer_A \
  --policy-stage A --medium poly_mailer --no-capture-barcode
```

For B, change to stage B, its own project name, and add `--demonstrated-bin 0` or `1`. CLI overrides let you select each recording project without editing the defaults.

1. Support the leader; short yellow A presses below 0.5 seconds toggle its torque lock if needed.
2. Hold yellow A above 1 second and release to synchronize the required arm, then wait for alignment.
3. Press/release green B to start recording, demonstrate the task, then press/release it again to stop.
4. Finish recording, disable synchronization and confirm stationary followers before exiting or changing tasks.

Both followers move during startup. Both arms remain in the recorded data even when one is unsynchronized. At least one arm must be synchronized to start recording. Unsynchronized recording does not configure left-only inference. See the [recording guide](../docs/guides/recording_guide.md) for Policy A/B commands and button steps, and the [barcode scanning guide](../docs/guides/barcode_scanning_guide.md) for optional scanner capture and scan-paired episodes.

## Inference and recovery

Set `RUN_INFERENCE["checkpoint_dir"]` and `model_name` to the chosen model, keeping its configuration/statistics alongside it. Set `episode_len` no higher than its training horizon: at most 400 for a 400-step task. The default checkpoint path still points to the vendor cube example; training does not switch it automatically. Inference currently commands both arms and has no autonomous A/B handoff or destination-conditioned B input.

`python3 experiments/robot_home.py` reads controller status without movement. `--inspect-pose` adds pose checks. These commands connect to controllers. Recovery/motion requires explicit flags; read the [terminal robot guide](../docs/guides/robot_home_guide.md) first. Help is hardware-free:

```bash
python3 experiments/robot_home.py --help
```
