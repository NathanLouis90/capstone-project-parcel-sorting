# Parcel Sorting with a Dual-Arm Dobot X-Trainer

A dual-arm Dobot X-Trainer picks one parcel from a receiving area, presents its
barcode to a scanner, and drops it into the bin selected by the barcode. Learned
policies (ACT and Diffusion Policy, trained with robomimic from human
demonstrations) do the pick; a scripted supervisor does the scan, wrist
rotation and bin placement.

## Problem and motivation

Last-mile parcel sorting is repetitive work: a worker picks up each parcel,
finds and scans its barcode, and places it into the correct delivery bin.
Parcels arrive one at a time, but at arbitrary positions and orientations, and
in three media that need different grasps: deformable poly mailers, thin DL
envelopes and rigid cartons. The barcode can be on either face of a mailer or
envelope, or on any of four faces of a carton, so the robot must reorient the
parcel until the scanner can read it. A parallel gripper is used instead of
suction because the sorted trays will later be loaded onto a delivery robot's
shelves.

Imitation learning handles the parts that are hard to script: grasping from an
arbitrary pose and carrying the parcel to the scanner. Envelopes use both arms
and a carry flip; poly mailers are picked by the right arm alone; cartons by the
left arm. The project compares ACT and Diffusion Policy on the same recordings
and splits.

## How a cycle works

1. The operator selects the medium: `envelope`, `poly_mailer` or `carton`.
2. The learned policy grasps the parcel and carries it to the holding arm's scan pose.
3. A handoff check requires the holding arm at the scan pose, closed gripper
   commands, the other arm at home, and at least 0.5 s of settled joints.
4. The supervisor reads the scanner and rolls the wrist (J6) only as needed: up
   to one 180° turn for flat media, or three 90° turns for cartons.
5. The first valid barcode selects a taught bin path. A parcel that cannot be
   read goes back to receiving.
6. The robot returns home and the operator records the outcome.

Every learned and scripted command passes the same validation and the paced
25 Hz control loop. Barcodes never enter the policy's inputs. See the
[architecture reference](docs/reference/architecture.md).

## Repository layout

Programs you run are grouped by workflow stage. Library code lives in
`parcel_sorting/`, and every editable setting lives in `config/settings.py`.

```
setup/         one-time and commissioning: ports, leaders, offsets, cameras,
               labels, scanner, teach and check waypoints
robot/         launch_nodes.py (robot server), robot_home.py (status, recover, home)
recording/     run_control.py (teleoperate and record), review_episodes.py
training/      train_models.py (dataset and training menu)
evaluation/    run_cycle.py (pick, scan, place), check_checkpoint.py
tools/         count, curate and audit datasets; simulate motion
config/        settings.py, plus local dobot_settings.ini and waypoints.local.yaml
parcel_sorting/  library: hardware, runtime, policies, scanning, data, training
tests/         hardware-free regression tests (python3 -m pytest)
docs/          procedures (what to do) and reference (how it works)
```

Bundled dependencies are in `third_party/` (ACT model, Dynamixel and Feetech
SDKs) and `robomimic-r2d2/` (robomimic with the parcel-sorting ACT/DP configs).
Recordings (`datasets/`), models (`ckpt/`) and cycle logs (`cycle_logs/`) are
local and not committed.

## Workflow

Follow the procedures in order. Each one lists what must be running first.

| Step | Procedure | Main command |
| --- | --- | --- |
| 1 | [Install the software](docs/procedures/01_install.md) | `python3 -m pip install --no-deps -e .` |
| 2 | [Set up the hardware](docs/procedures/02_hardware_setup.md) | `python3 setup/1_find_ports.py` |
| 3 | [Print labels and check the scanner](docs/procedures/03_labels_and_scanner.md) | `python3 setup/make_labels.py` |
| 4 | [Prepare the workspace and parcels](docs/procedures/04_workspace.md) | — |
| 5 | [Teach waypoints](docs/procedures/05_teach_waypoints.md) | `python3 setup/teach_waypoints.py` |
| 6 | [Check waypoints and wrist rotation](docs/procedures/06_check_waypoints.md) | `python3 setup/check_waypoints.py` |
| 7 | [Record demonstrations](docs/procedures/07_record_episodes.md) | `python3 recording/run_control.py` |
| 8 | [Review episodes](docs/procedures/08_review_episodes.md) | `python3 recording/review_episodes.py` |
| 9 | [Train ACT and DP](docs/procedures/09_train_models.md) | `python3 training/train_models.py` |
| 10 | [Run sorting cycles](docs/procedures/10_run_cycles.md) | `python3 evaluation/run_cycle.py` |
| 11 | [Evaluate poly mailers](docs/procedures/11_evaluate_poly_mailer.md) | `python3 evaluation/run_cycle.py --live` |

When the robot needs attention, use [home and recover](docs/procedures/home_and_recover.md).
For dataset maintenance, use [curate datasets](docs/procedures/curate_datasets.md).
The [documentation index](docs/README.md) lists every procedure and reference page.

## Try it without hardware

After [installing](docs/procedures/01_install.md):

```bash
python3 -m pytest
python3 evaluation/run_cycle.py --medium poly_mailer --dry-run \
  --fake-token DEST-A-S138683 --csv /tmp/poly-mailer-cycle.csv
```

A simulated run checks software behaviour only. It never establishes that the
robot's paths are physically safe.

## Safety

Starting the robot server cycles both grippers, and starting the recorder homes
both followers. Keep the arm paths clear and the emergency stop within reach
whenever a program can move the robot. Ctrl+C is not an emergency stop.

## References

- Zhao et al. (2023), [Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware](https://arxiv.org/abs/2304.13705).
- Chi et al. (2023), [Diffusion Policy](https://arxiv.org/abs/2303.04137).
- Dobot X-Trainer [user guide](docs/provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf)
  and [operation guide and FAQ](docs/provided_dobot/Dobot%20X-Trainer%20Operation%20Guide%20and%20FAQ.pdf).
