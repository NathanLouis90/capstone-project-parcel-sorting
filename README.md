## Problem and motivation

Last-mile parcel sorting is a repetitive and labor-intensive process in which workers scan parcels and manually place them into the correct delivery bins. This project explores robotic automation of this task using imitation learning (behavior cloning). Human demonstrations consisting of images and robot joint states are recorded to train policies that replicate expert actions. The project currently evaluates and compares two imitation learning approaches: Action Chunking with Transformers (ACT) and Diffusion Policy (DP).

## Setup
**To be filled**

## Hardware

| Item | Use | Specifications and purchasing details |
| --- | --- | --- |
| Dobot X-Trainer | Two leader arms, two follower arms, supplied parallel-jaw grippers, and top/left-wrist/right-wrist cameras | Model, hardware revision and supplier: to add |
| DL envelopes | Thin mail medium | Dimensions, material and Shopee/Lazada link: to add |
| Poly mailer bags | Compliant parcel medium | Dimensions, material and Shopee/Lazada link: to add |
| Carton boxes | Rigid parcel medium | Dimensions, material and Shopee/Lazada link: to add |
| Rectangular basins | Destination bins 0 and 1 | Quantity, dimensions, placement and Shopee/Lazada link: to add |
| Barcode scanner | Reads destination labels at the reading station | Model, interface, mounting and Shopee/Lazada link: to add |

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

This is a short checklist. Refer to the supplied **Dobot X-Trainer (Lightweight Base) User Guide**, and **Dobot X-Trainer Operation Guide and FAQ** to learn how to startup the robot, operate the robot safely, and debugging common issues. 

Use the existing **Python 3.8 Xtrainer environment**. Vendor training modules are distributed as Python 3.8 bytecode; `requirements.txt` is not a complete environment lockfile. On a fresh checkout, copy `scripts/dobot_config/dobot_settings.example.ini` to the local `dobot_settings.ini` only if absent, then configure devices and calibrate. The example is a schema, not working calibration.

```bash
conda activate Xtrainer
cd /path/to/capstone-project-parcel-sorting
```

1. **Connect and power on.** Secure the arm, gripper and camera cables; power on in the order specified by the user guide. Clear both follower-arm paths and keep the cameras, reading station and bins in their demonstration positions.
2. **Find ports.** Run `PYTHONPATH=. python3 scripts/1_find_port.py` and wait for it to finish. Repeat after a host restart or USB reconnection; it updates the local hardware settings.
3. **Position the leaders.** Run `PYTHONPATH=. python3 scripts/3_just_buttonA.py`. Support each leader handle, short-press yellow **A** (below 0.5 seconds) to unlock, manually move it to the calibrated initial posture, then short-press again to lock. Stop the helper with **Ctrl+C** before continuing. This helper controls leader locking; synchronization happens in the recorder.
4. **Calibrate only when needed.** For first setup or lost/incorrect calibration, follow the user guide's posture-setting procedure and run `PYTHONPATH=. python3 scripts/2_get_offset.py`. Keep existing working offsets for routine startup.
5. **Start the server.** In terminal 1, run `python3 experiments/launch_nodes.py` and leave it running. In terminal 2, activate the same environment, enter the repository root, and start the recorder below.

Server startup enables hardware and cycles grippers; recorder startup moves both followers, even when the demonstration uses only one arm. Keep startup paths clear. 

## Record demonstrations

```bash
python3 experiments/run_control.py --show-img \
  --project-name second_set_poly_mailer_A \
  --policy-stage A --medium poly_mailer --no-capture-barcode
```

For B, use its own project name, `--policy-stage B`, and `--demonstrated-bin 0` or `1`.

1. With the leader locked in its initial posture, hold yellow **A** for more than 2 seconds and release to enable synchronization; wait for alignment. The current code accepts holds above 1 second; the vendor guide specifies above 2 seconds.
2. Support the leader and short-press yellow **A** to unlock for teleoperation. Synchronize only the arm needed for that policy; leave the unused arm unsynchronized. At least one arm must be synchronized to record.
3. Press and release green **B** to start recording. Move the leader to demonstrate the task; squeeze/release its trigger to close/open the follower gripper.
4. Press and release green **B** again to stop and save. Wait for saving to finish before the next episode. Finish recording and disable synchronization with another long yellow **A** press before exiting.

The button names **A/B** are separate from the policy names **A/B**. Episodes save in `datasets/<project>/collect_data/<timestamp>/`. See the [recording guide](docs/guides/barcode_recording_guide.md) for more detail.

## Prepare and train ACT

Add actual project names to `PREPARE_ACT_DATASETS["projects"]` in [scripts/scripts_config.py](scripts/scripts_config.py). The defaults register three first-set projects. Copy those entries for a second set, preserving A/None, B/0 and B/1. `ModelTrain/constants.py` registers the configured names as training tasks automatically.

```bash
python3 scripts/count_episodes.py
python3 scripts/prepare_act_datasets.py --dataset-name second_set_poly_mailer_A # checks and verifies datasets is ready for conversion  
python3 scripts/prepare_act_datasets.py --dataset-name second_set_poly_mailer_A --convert # creates ACT training files and review videos

python3 -c "import torch; print(torch.cuda.is_available())"
# Train when CUDA reports True; use a fresh checkpoint folder.
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name second_set_poly_mailer_A \
  --ckpt_dir ./ckpt/act_second_set_poly_mailer_A \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

Repeat with each B task and a separate output folder. Review demonstration videos before training. `--dataset-name` is optional: without it all configured projects are selected. Conversion refuses existing HDF5 outputs; already converted projects need validation only. Defaults are a 400-step horizon, an 80/20 episode split, and three cameras.

`--ckpt_dir` determines where models go. Keep `config.pkl` and `dataset_stats.pkl` with the checkpoints. See the [ACT guide](docs/guides/act_poly_mailer_training.md) and [scripts README](scripts/README.md), including how to train both collection sets together.

## Version history

| Component | Version Number | Release Date
| --- | --- | --- |
| Lightweight base user guide | 1.1 | 31 Jul 2024 |
| Operation guide and FAQ | 1.0.0 | N/A |
| Dobot SDK (Codebase) | 1.0.0 | 11 Dec 2024 |

## Citations

[1] Zhao, T. Z., Kumar, V., Levine, S., and Finn, C. (2023). **Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware** (ACT). [Paper](https://arxiv.org/abs/2304.13705) · [Code](https://github.com/tonyzhaozh/act).

[2] Chi, C., et al. (2023; revised 2024). **Diffusion Policy: Visuomotor Policy Learning via Action Diffusion**. [Paper](https://arxiv.org/abs/2303.04137) · [Code](https://github.com/real-stanford/diffusion_policy).
