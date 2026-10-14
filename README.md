## Problem and motivation

Last-mile parcel sorting is a repetitive and labor-intensive process in which workers scan parcels and manually place them into the correct delivery bins. This project explores robotic automation of this task using imitation learning (behavior cloning). Human demonstrations consisting of images and robot joint states are recorded to train policies that replicate expert actions. The project currently evaluates and compares two imitation learning approaches: Action Chunking with Transformers (ACT) and Diffusion Policy (DP).

## Hardware setup

Arrange the receiving area, barcode reading station, staging area and destination bins within the robot's working area. The following items support demonstration recording and parcel pick-and-place tasks.

| Item | Use | Specifications and purchasing details |
| --- | --- | --- |
| Dobot X-Trainer | Records human demonstrations through the leader arms and performs parcel pick-and-place with the follower arms, grippers and cameras | Model, hardware revision and supplier: to add |
| DL envelopes | Thin parcels used to demonstrate and evaluate envelope pickup, staging and sorting | Dimensions, material and Shopee/Lazada link: to add |
| Poly mailer bags | Used to record and test pickup, staging and sorting of poly mailer bags | Dimensions, material and Shopee/Lazada link: to add |
| Carton boxes | Rigid parcels used to demonstrate and evaluate box pickup, staging and sorting | Dimensions, material and Shopee/Lazada link: to add |
| Storage bins (elevated platforms) | Provide raised receiving and staging surfaces: parcels start at the receiving area and rest at staging between Policy A and Policy B | Quantity, dimensions, height, placement and Shopee/Lazada link: to add |
| Rectangular basins | Receive sorted parcels as destination bins 0 and 1 | Quantity, dimensions, placement and Shopee/Lazada link: to add |
| Barcode scanner | Reads parcel labels at the reading station to identify the destination bin | Model, interface, mounting and Shopee/Lazada link: to add |

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
3. **Configure the robot network.** Using DobotStudio Pro, configure the left and right followers as `192.168.5.1` and `192.168.5.2`, set their initial poses and payload as described in the guide, and enable TCP/IP secondary development mode. Give the PC's robot-facing Ethernet connection an unused address on `192.168.5.xxx` with subnet mask `255.255.255.0`. Match these addresses and the shared server port in [experiments/experiments_config.py](experiments/experiments_config.py).
4. **Configure cameras, USB ports and calibration.** On the fresh checkout, copy `scripts/dobot_config/dobot_settings.example.ini` to `scripts/dobot_config/dobot_settings.ini`, fill in the three camera serial numbers and local device settings, and configure USB device access following the guide. Run `PYTHONPATH=. python3 scripts/1_find_port.py` to detect leader/gripper ports. Position and lock the leaders with `scripts/3_just_buttonA.py`, stop that helper, then run `PYTHONPATH=. python3 scripts/2_get_offset.py` for first-time calibration. Check camera images with `PYTHONPATH=. python3 scripts/5_camera_read.py` and stop the preview before recording. Keep the actual INI local and preserve working calibration on subsequent setups.

See the [scripts README](scripts/README.md) for device settings and helper details, then follow **Quick startup** below.

## How the task works

**Policy A moves a parcel from receiving to the scanner, then to staging.** Poly mailer bags and carton boxes use only the left arm. Envelopes use both arms: the left slides the envelope and returns home; the right then grabs it, presents the label and places it at staging with an edge overhanging.

**Policy B moves the staged parcel into bin 0 or bin 1 using only the right arm.** It is given the chosen bin at every step. Any unused arm stays home with its gripper closed. Both policies start and finish at home.

The intended final models handle all three parcel types. Current early tests use poly mailer bags; carton and envelope demonstrations have not yet been added to Policy A. Recording 25 demonstrations at a time is one way to compare performance at 25, 50, 75 and 100 recordings; you can choose any collection size.

## Where to find things

| Folder | What it does |
| --- | --- |
| [experiments/](experiments/README.md) | Starts the robot server, records demonstrations, runs a trained model on the robot, and checks or restores the home pose |
| [scripts/](scripts/README.md) | Finds device ports, calibrates leaders, previews cameras, counts recordings, and converts recordings into training files |
| `barcode_scanning/` | Generates parcel labels and reads the barcode scanner to identify the destination bin |
| `dobot_control/` | Connects to the robot arms, grippers, leaders and cameras |
| `ModelTrain/` | Trains ACT models with the Dobot training software |
| `robomimic-r2d2/` | Trains ACT and Diffusion Policy models using the same data-reading tools |
| `third_party/` | Contains the motor communication software and ACT model code needed by other folders |
| `docs/guides/` | Step-by-step operating guides |
| `tests/` | Checks software behavior without moving the robot |

## How to use command examples

Run `bash` code blocks in a Bash terminal from the repository root, with `Xtrainer` activated. Replace example names and paths before pasting. Lines such as `PROJECT="your_folder"` set terminal variables; run them before commands that use `$PROJECT`, in the same terminal. If you open another terminal, set those variables again.

Python configuration blocks are edits to the file named in the instructions. They do not go in the terminal. Variables only make commands easier to reuse; you can also put actual names and paths directly in a command.

## Quick startup

Use the included [Lightweight Base User Guide](docs/provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf) and [Operation Guide and FAQ](docs/provided_dobot/Dobot%20X-Trainer%20Operation%20Guide%20and%20FAQ.pdf) for full setup, operation and troubleshooting instructions.

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
6. **Start the recorder.** In terminal 2, activate the same environment, enter the repository root, and run `python3 experiments/run_control.py --show-img` with your chosen recording arguments. Choose the recorder command from the [Policy A](docs/guides/policy_a.md) or [Policy B](docs/guides/policy_b.md) guide; the [recording guide](docs/guides/recording_guide.md) explains button operation.

Startup cycles the grippers and moves both followers, even for a one-arm demonstration. Keep their paths clear. See the [barcode scanning guide](docs/guides/barcode_scanning_guide.md) for optional scanner setup and capture.

## Record, prepare and train

Follow the [Policy A guide](docs/guides/policy_a.md) or [Policy B guide](docs/guides/policy_b.md) from recording through evaluation. Each guide explains which arm to use, how to name recording folders, and which training route to choose.

Before training, [review recordings](docs/guides/dataset_preparation.md#review-all-episodes-with-one-command) and accept successful demonstrations. Rejected recordings stay on disk but are excluded from future preparation and robomimic conversion. Existing datasets and checkpoints do not change when you reject a recording. The [rejection guide](docs/guides/dataset_preparation.md#what-happens-to-rejected-recordings) explains how to update training data, including the extra step needed for Dobot ACT.

For early tests that run a model on the robot, use [Dobot ACT training](docs/guides/act_training.md). For the ACT versus Diffusion Policy comparison, use the [ACT and DP training guide](docs/guides/act_dp_training.md). That comparison uses the same recordings, the same scaling of joint values, and the same recordings held aside for checking both models.

## Run a model and measure success

The [inference and evaluation guide](docs/guides/inference_evaluation.md) explains how to select a checkpoint, run it on the robot and record whether the task succeeded. Stay at the robot during these tests, with access to the emergency stop.

The robot runner currently supports Dobot ACT checkpoints. Models trained through robomimic can be checked using recorded data, but cannot yet run the robot. Automatic switching from Policy A to Policy B is also not implemented.

## Version history

| Component | Version Number | Release Date
| --- | --- | --- |
| Lightweight base user guide | 1.1 | 31 Jul 2024 |
| Operation guide and FAQ | 1.0.0 | N/A |
| Dobot SDK (Codebase) | 1.0.0 | 11 Dec 2024 |

## Citations

[1] Zhao, T. Z., Kumar, V., Levine, S., and Finn, C. (2023). **Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware** (ACT). [Paper](https://arxiv.org/abs/2304.13705) · [Code](https://github.com/tonyzhaozh/act).

[2] Chi, C., et al. (2023; revised 2024). **Diffusion Policy: Visuomotor Policy Learning via Action Diffusion**. [Paper](https://arxiv.org/abs/2303.04137) · [Code](https://github.com/real-stanford/diffusion_policy).
