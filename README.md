## Problem and motivation

Last-mile parcel sorting is a repetitive, labour-intensive process: a worker
picks up each parcel, finds and scans its barcode, and places it into the
correct delivery bin. This project automates the task with a dual-arm Dobot
X-Trainer. Parcels are assumed to be singulated upstream, arriving one at a
time, but the remaining problem is still far from a fixed pick-and-place. The
robot must handle three different media, namely deformable poly mailer bags,
thin DL envelopes and rigid carton boxes, each needing its own grasp. Parcels
arrive at arbitrary positions and orientations in the receiving area, and the
barcode may be on either face of a mailer or envelope, or on any of four
faces of a carton, so the robot must reorient each parcel until the scanner
can read it.

The robot uses a parallel gripper rather than a suction end effector. In a
full depot workflow, the robot will eventually need to load sorted trays onto
the shelves of a delivery robot, which suction cannot do without a tool
change.

Embodied AI is applied where perception and contact make the task difficult
to script. Per-medium policies trained by imitation learning from human
demonstrations, recorded as camera images and robot joint states, grasp each
parcel from an arbitrary pose and bring it to the scanner. For mailers and
envelopes, the policy also learns to flip a top-facing label down: envelopes
use a carry flip, while mailers use left-arm flipping on an elevated platform
followed by right-arm corner pickup. The left arm returns home before the
right-arm scan handoff. A scripted supervisor handles the deterministic
steps: rotating the wrist above the scanner until the barcode is read, then
placing the parcel in the bin selected by the barcode. The project compares
two imitation learning approaches for these policies: Action Chunking with
Transformers (ACT) and Diffusion Policy (DP).

## Hardware and media

See [hardware reference](docs/guides/hardware/README.md#parcel-dimensions-and-label-faces) for dimensions, label faces, purchase
references and scanner checks. Receiving is beneath the top camera. Keep one
parcel in the receiving zone, with fixed bubble-wrap contents for poly mailers.
Use the [measured workspace layout](docs/guides/hardware/README.md#workspace-layout-and-coordinate-frame)
for the EVA board, bin, scanner, and receiving-area centres and the shared
coordinate-frame definition.

## Software setup

For a new PC, follow sections 3–4 of the included [Dobot X-Trainer (Lightweight Base) User Guide V1.1](docs/provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf). See the [Operation Guide and FAQ](docs/provided_dobot/Dobot%20X-Trainer%20Operation%20Guide%20and%20FAQ.pdf) for troubleshooting.

1. **Install the base software.** Use the guide's Ubuntu 20.04 baseline and install [Anaconda](https://www.anaconda.com/download). For training, install an NVIDIA driver compatible with the GPU, CUDA 11.8 and matching cuDNN following the guide. Use the environment below because parts of the Dobot training software require Python 3.8.
2. **Clone the repository and install dependencies.** Install Git and build tools, then clone the public repository:

   ```bash
   sudo apt update
   sudo apt install git build-essential linux-libc-dev libxcb-cursor0
   git clone https://github.com/NathanLouis90/capstone-project-parcel-sorting.git
   cd capstone-project-parcel-sorting
   conda create -n Xtrainer python=3.8.10
   conda activate Xtrainer
   python3 -m pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
   python3 -m pip install -r requirements.txt
   python3 -m pip install -e third_party/DynamixelSDK/python
   python3 -m pip install -e ModelTrain/detr
   python3 -m pip install -r requirements-robomimic.txt
   python3 -m pip install --no-deps -e robomimic-r2d2
   python3 -c "import torch; print('CUDA available:', torch.cuda.is_available())"
   ```

   Confirm `CUDA available: True` before training. `requirements.txt` alone does not install the complete training stack.

   | Command part | What it does |
   | --- | --- |
   | `sudo apt update` / `sudo apt install ...` | Refresh Ubuntu's package list, then install the listed Git, build, and GUI dependencies with administrator privileges. |
   | `git clone URL` / `cd capstone-project-parcel-sorting` | Download this repository into a new folder, then enter it. Use your existing checkout instead if already installed. |
   | `conda create -n Xtrainer python=3.8.10` | Create an environment named `Xtrainer` with Python 3.8.10. `-n` sets its name. |
   | `conda activate Xtrainer` | Select that environment in the current terminal. Repeat activation in every new terminal. |
   | `python3 -m pip install ...` | Run the selected Python interpreter's package installer. `==` pins an exact package version. |
   | `--index-url .../cu118` | Download the PyTorch packages from the CUDA 11.8 wheel index. |
   | `-r requirements.txt` / `-r requirements-robomimic.txt` | Install the dependencies listed in that file. Both files are needed. |
   | `-e PATH` | Install a local package in editable mode so imports use the source in that directory. |
   | `--no-deps -e robomimic-r2d2` | Install bundled robomimic without replacing the dependencies installed above. |
   | `python3 -c "..."` | Execute the quoted Python code; here it reports whether PyTorch can use CUDA. |

3. **Configure the robot network.** Using DobotStudio Pro, configure the left and right followers as `192.168.5.1` and `192.168.5.2`, set their initial poses and payload as described in the guide, and enable TCP/IP secondary development mode. Give the PC's robot-facing Ethernet connection an unused address on `192.168.5.xxx` with subnet mask `255.255.255.0`. Match these addresses and the shared server port in [experiments/experiments_config.py](experiments/experiments_config.py).
4. **Configure cameras, USB ports and calibration.** On the fresh checkout, copy `scripts/dobot_config/dobot_settings.example.ini` to `scripts/dobot_config/dobot_settings.ini`, fill in the three camera serial numbers and local device settings, and configure USB device access following the guide. Run `PYTHONPATH=. python3 scripts/1_find_port.py` to detect leader/gripper ports. Position and lock the leaders with `scripts/3_just_buttonA.py`, stop that helper, then run `PYTHONPATH=. python3 scripts/2_get_offset.py` for first-time calibration. Check camera images with `PYTHONPATH=. python3 scripts/5_camera_read.py` and stop the preview before recording. Keep the actual INI local and preserve working calibration on subsequent setups.

`PYTHONPATH=.` makes this checkout importable for one helper invocation; the
numbered helpers above take no arguments in these examples. See the
[scripts README](scripts/README.md) for device settings and helper details, then
follow the recording and cycle guides below.


## Architecture and workflow

1. Select `envelope`, `poly_mailer` or `carton` manually.
2. A learned policy grasps the parcel and carries it to its holding arm's scan pose.
3. A shared handoff check requires the holding arm at that pose, closed gripper
   commands, the other arm home, and at least 0.5 seconds of settled joints.
4. The supervisor checks the scanner, then rolls J6 only as needed: up to one
   180° rotation for flat media or three 90° rotations for cartons.
5. The first valid token selects a taught bin path. No-read parcels return to
   receiving and are released at a taught height a few centimetres above it.
6. The robot returns home. The operator records the physical outcome.

All learned and scripted cycle commands use `validate_action` and the paced
25 Hz `env.step` loop. Scanner tokens and label-face metadata never enter policy
observations. The current driver does not measure grasp success; pose checks
cannot replace operator evaluation.

## Where to start

[Documentation index](docs/README.md) pairs step-by-step guides with separate
explanation READMEs for each workflow.

1. [Teach waypoints](docs/guides/hardware/waypoints.md), then follow the
   [recording protocol](docs/guides/recording/protocol.md) and
   [instructions by medium](docs/guides/recording/media.md).
2. [Review and prepare data](docs/guides/datasets/preparation.md), then
   [train matched ACT/DP models](docs/guides/training/act_dp.md) or
   use the optional [vendor ACT route](docs/guides/training/vendor_act.md).
3. [Run and evaluate cycles](docs/guides/runtime/evaluation.md).
   Use [curation](docs/guides/datasets/curation.md) and
   [robot recovery](docs/guides/hardware/homing.md) when needed.

Run Bash commands from this repository's root in the `Xtrainer` environment.
Replace example paths. Variable assignments and commands using them belong in
the same terminal. Python configuration changes belong in the named file.
Follow the [terminal preparation guide](docs/terminal_commands.md) for terminal
roles; read the [terminal reference](docs/README.md#terminal-syntax) for syntax.

## Robot checks

Follow the [robot check instructions](tests/README.md) to start the server in
Terminal 1 and run a check in Terminal 2. Configure waypoint defaults in
[tests/waypoint_config.py](tests/waypoint_config.py), then run
`python3 tests/check_waypoint.py`. This real-robot menu moves the selected arm
after you type `MOVE`. The wrist check
rotates from the taught scan pose; the full cycle performs pickup, scanning,
and bin placement. To preview the scripts without hardware:

```bash
python3 tests/check_wrist_rotation.py --dry-run --fake-read-at 180
python3 tests/check_full_cycle.py --medium poly_mailer --dry-run \
  --fake-token DEST-A-S138683 --csv /tmp/parcel-cycle.csv
```

| Command part | Meaning and result |
| --- | --- |
| `check_wrist_rotation.py --dry-run --fake-read-at 180` | Check all four wrist positions with a simulated read at 180 degrees. |
| `--medium poly_mailer --dry-run` | Simulate one poly mailer cycle instead of using the robot. |
| `--fake-token DEST-A-S138683` | Supply a simulated valid barcode for bin 0, Dover. |
| `--csv /tmp/parcel-cycle.csv` | Append the simulated cycle result to this CSV file. |

See [runtime and evaluation](docs/guides/runtime/evaluation.md) for expected
outcomes, no-read checks, and checkpoint arguments.

A simulated run tests software behavior and never establishes hardware safety.
Live runs require fresh trained checkpoints and commissioned local waypoints.
The medium classifier is deferred; the policy-step interface also allows a
future VLA adapter.

## References

- Zhao et al. (2023), [Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware](https://arxiv.org/abs/2304.13705).
- Chi et al. (2023), [Diffusion Policy](https://arxiv.org/abs/2303.04137).
