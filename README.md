## Problem and motivation

Last-mile parcel sorting is a repetitive and labor-intensive process in which workers scan parcels and manually place them into the correct delivery bins. This project explores robotic automation of this task using imitation learning (behavior cloning). Human demonstrations consisting of images and robot joint states are recorded to train policies that replicate expert actions. The project currently evaluates and compares two imitation learning approaches: Action Chunking with Transformers (ACT) and Diffusion Policy (DP).

## Hardware setup

Arrange the receiving area, barcode reading station, staging area and destination bins within the robot's working area. The following items support demonstration recording and parcel pick-and-place tasks.

| Item | Use | Specifications and purchasing details |
| --- | --- | --- |
| Dobot X-Trainer | Records human demonstrations through the leader arms and performs parcel pick-and-place with the follower arms, grippers and cameras | Model, hardware revision and supplier: to add |
| DL envelopes | Thin parcels used to demonstrate and evaluate envelope pickup, staging and sorting | Dimensions, material and Shopee/Lazada link: to add |
| Poly mailer bags | Flexible parcels used to demonstrate and evaluate pickup, staging and sorting of compliant packaging | Dimensions, material and Shopee/Lazada link: to add |
| Carton boxes | Rigid parcels used to demonstrate and evaluate box pickup, staging and sorting | Dimensions, material and Shopee/Lazada link: to add |
| Storage bins (elevated platforms) | Provide raised receiving and staging surfaces: parcels start at the receiving area and rest at staging between Policy A and Policy B | Quantity, dimensions, height, placement and Shopee/Lazada link: to add |
| Rectangular basins | Receive sorted parcels as destination bins 0 and 1 | Quantity, dimensions, placement and Shopee/Lazada link: to add |
| Barcode scanner | Reads parcel labels at the reading station to identify the destination bin | Model, interface, mounting and Shopee/Lazada link: to add |

## Software setup

For a new PC, follow sections 3–4 of the **Dobot X-Trainer (Lightweight Base) User Guide V1.1**. Download it and the **Operation Guide and FAQ** from the [Dobot Portal](https://portal.dobot-robots.com/home) after signing in.

1. **Install the base software.** Use the guide's Ubuntu 20.04 baseline and install [Anaconda](https://www.anaconda.com/download). For training, install an NVIDIA driver compatible with the GPU, CUDA 11.8 and matching cuDNN following the guide. Use the environment below because required vendor modules are supplied as Python 3.8 bytecode.
2. **Clone the repository and install dependencies.** Install Git and build tools, authenticate with a GitHub account that has access to this repository, then run:

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
   python3 -m pip install -e robomimic-r2d2
   python3 -c "import torch; print('CUDA available:', torch.cuda.is_available())"
   ```

   Confirm `CUDA available: True` before training. `requirements.txt` alone does not install the complete training stack.
3. **Configure the robot network.** Using DobotStudio Pro, configure the left and right followers as `192.168.5.1` and `192.168.5.2`, set their initial poses and payload as described in the guide, and enable TCP/IP secondary development mode. Give the PC's robot-facing Ethernet connection an unused address on `192.168.5.xxx` with subnet mask `255.255.255.0`. Match these addresses and the shared server port in [experiments/experiments_config.py](experiments/experiments_config.py).
4. **Configure cameras, USB ports and calibration.** On the fresh checkout, copy `scripts/dobot_config/dobot_settings.example.ini` to `scripts/dobot_config/dobot_settings.ini`, fill in the three camera serial numbers and local device settings, and configure USB device access following the guide. Run `PYTHONPATH=. python3 scripts/1_find_port.py` to detect leader/gripper ports. Position and lock the leaders with `scripts/3_just_buttonA.py`, stop that helper, then run `PYTHONPATH=. python3 scripts/2_get_offset.py` for first-time calibration. Check camera images with `PYTHONPATH=. python3 scripts/5_camera_read.py` and stop the preview before recording. Keep the actual INI local and preserve working calibration on subsequent setups.

See the [scripts README](scripts/README.md) for device settings and helper details, then follow **Quick startup** below.

## System architecture
**Policy A** acquires an item, presents it at the reading station, stages it, and retracts. **Policy B** reacquires it and places it in the destination bin.
**To be filled**

## File structure and ownership

| Path | Purpose and provenance |
| --- | --- |
| [experiments/](experiments/README.md) | Adapted Dobot server, recorder and inference entry points; custom configuration and terminal homing |
| [scripts/](scripts/README.md) | Adapted Dobot setup/conversion helpers; custom counting, validation and configuration |
| `barcode_scanning/` | Capstone additions: labels, HID reader, A/B metadata and destination preservation |
| `dobot_control/`, `ModelTrain/` | Dobot-supplied hardware interfaces and ACT integration; task registration adapted locally |
| `robomimic-r2d2/`, `third_party/` | Bundled upstream libraries and device SDKs |
| `docs/guides/`, `tests/` | Capstone operating guides and hardware-free checks |

## Quick startup

Create an account on the [Dobot Portal](https://portal.dobot-robots.com/home), sign in, and download the **Dobot X-Trainer (Lightweight Base) User Guide** and **Dobot X-Trainer Operation Guide and FAQ** for full setup, operation and troubleshooting instructions.

Run from the repository root in the **Python 3.8 Xtrainer environment**:

```bash
conda activate Xtrainer
cd /path/to/capstone-project-parcel-sorting
```

1. **Connect and power on.** Check cables, follow the manual's power-on sequence, and clear both follower-arm paths.
2. **Find ports.** Run `PYTHONPATH=. python3 scripts/1_find_port.py` and wait for it to finish. Repeat after a host restart or USB reconnection.
3. **Position the leaders.** Run `PYTHONPATH=. python3 scripts/3_just_buttonA.py`. Support each handle, short-press yellow **A** to unlock, move to the calibrated initial posture, then short-press again to lock. Stop the helper with **Ctrl+C**.
4. **Calibrate if needed.** For first setup or incorrect/lost calibration, follow the manual and run `PYTHONPATH=. python3 scripts/2_get_offset.py`. Keep working offsets for routine startup.
5. **Start the server.** In terminal 1, run `python3 experiments/launch_nodes.py` and leave it running.
6. **Start the recorder.** In terminal 2, activate the same environment, enter the repository root, and run `python3 experiments/run_control.py --show-img` with your chosen recording arguments. See the [recording guide](docs/guides/recording_guide.md) for configuration, Policy A/B commands and button steps.

Startup cycles the grippers and moves both followers, even for a one-arm demonstration. Keep their paths clear. See the [barcode scanning guide](docs/guides/barcode_scanning_guide.md) for optional scanner setup and capture.

## Dataset preparation and training

Register the recording folders and their medium, policy stage and destination in [scripts/scripts_config.py](scripts/scripts_config.py). Validate completed episodes with `scripts/prepare_act_datasets.py`, then add `--convert` to create HDF5 training files and review videos. Review the demonstrations before training; existing HDF5 files are not overwritten.

Train each registered task with `ModelTrain/model_train.py` in the Python 3.8 `Xtrainer` environment with CUDA available. Keep A, B bin 0 and B bin 1 separate, use a fresh checkpoint folder for each run, and retain its configuration and dataset statistics with the model.

Read the [scripts README](scripts/README.md) for preparation details and the [ACT training guide](docs/guides/act_training.md) for training arguments and examples.

## Version history

| Component | Version Number | Release Date
| --- | --- | --- |
| Lightweight base user guide | 1.1 | 31 Jul 2024 |
| Operation guide and FAQ | 1.0.0 | N/A |
| Dobot SDK (Codebase) | 1.0.0 | 11 Dec 2024 |

## Citations

[1] Zhao, T. Z., Kumar, V., Levine, S., and Finn, C. (2023). **Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware** (ACT). [Paper](https://arxiv.org/abs/2304.13705) · [Code](https://github.com/tonyzhaozh/act).

[2] Chi, C., et al. (2023; revised 2024). **Diffusion Policy: Visuomotor Policy Learning via Action Diffusion**. [Paper](https://arxiv.org/abs/2303.04137) · [Code](https://github.com/real-stanford/diffusion_policy).
