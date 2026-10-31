# Commands

This page covers how the terminals are prepared, which program runs in which terminal, the shell syntax used in the procedures, and what `--dry-run` does in each program.

## Terminal preparation

Use Bash on the robot PC. Run these two lines in every new terminal:

```bash
conda activate Xtrainer
cd ~/dobot_xtrainer
```

Every command in the procedures starts from the repository root. The repository is installed once with `pip install -e .` ([install](../procedures/01_install.md)), so `parcel_sorting` and `config` import from any program without further setup. Do not repeat the installation for each session.

## Terminal roles

| Task | Terminal 1 | Terminal 2 | Terminal 3 | Procedure |
| --- | --- | --- | --- | --- |
| Record demonstrations | `robot/launch_nodes.py` | `recording/run_control.py` | | [Record episodes](../procedures/07_record_episodes.md) |
| Teach waypoints | `robot/launch_nodes.py` | `recording/run_control.py` (leader control; following disabled on both arms before saving) | `setup/teach_waypoints.py` | [Teach waypoints](../procedures/05_teach_waypoints.md) |
| Check waypoints and wrist rotation | `robot/launch_nodes.py` | `setup/check_waypoints.py` or `setup/check_wrist_rotation.py --live` | | [Check waypoints](../procedures/06_check_waypoints.md) |
| Run a live cycle | `robot/launch_nodes.py` | `evaluation/run_cycle.py --live` | | [Run parcel cycles](../procedures/10_run_cycles.md) |
| Home, inspect, or recover the robot | `robot/robot_home.py`, with the server and all other robot clients stopped | | | [Home and recover](../procedures/home_and_recover.md) |
| Review episodes, train, curate, check checkpoints, dry runs | any one program; no server needed | | | [Review](../procedures/08_review_episodes.md), [train](../procedures/09_train_models.md), [curate](../procedures/curate_datasets.md) |
| Hardware setup helpers (`setup/1_` to `setup/4_`) | as described in the procedure | | | [Hardware setup](../procedures/02_hardware_setup.md) |

Rules that apply to every task:

- **One server.** Run one `robot/launch_nodes.py` at a time, and only one motion client against it (recorder, waypoint check, or cycle).
- **Startup moves hardware.** Server startup cycles the grippers, and recorder startup homes both followers. Start them with empty grippers and clear paths.
- **Homing needs the robot to itself.** `robot/robot_home.py` connects to the controllers directly. It refuses to run while `launch_nodes.py`, `run_control.py`, `run_cycle.py`, `teach_waypoints.py`, `check_waypoints.py`, `check_wrist_rotation.py` or `3_leader_buttons.py` is running.
- **One scanner reader.** A live cycle and the live wrist check open their own scanner reader. Keep `setup/check_scanner.py` stopped while they run.
- **Stop recording before training.**

## Shell syntax

| Example | Meaning |
| --- | --- |
| `python3 evaluation/run_cycle.py` | Runs the named Python program. Its options follow the filename. |
| `--medium poly_mailer` | An option followed by its value. Here it selects the poly-mailer workflow. |
| `--show-img` | A switch with no value. Including it turns the feature on. |
| `status` in `tools/curate_datasets.py status` | A subcommand. It chooses the operation and comes before that operation's options. |
| `label_face=top` | Saves a shell variable in the current terminal. There are no spaces around `=`. |
| `"$label_face"` | Substitutes the variable's value. The quotes keep a value that contains spaces together. |
| `"ckpt/${MEDIUM}_configs"` | Braces separate the variable name from text that follows it. |
| `\` at the end of a line | Continues the same command on the next line. Copy the whole block, with no spaces after `\`. |
| `MODEL_NAME`, `EPISODE_ID` | A placeholder in capitals. Replace it with a real value before running. |
| `/tmp/poly-mailer-cycle.csv` | An output path in temporary storage. Use a path under the repository for results you want to keep. |
| `echo "exit status $?"` | Prints the exit status of the previous command. `0` means success. |

- **Variables stay in their terminal.** A variable set in one terminal does not exist in another. Keep each assignment in the same terminal as the commands that use it.
- **`--help` is safe on most programs.** Programs in `robot/`, `recording/`, `setup/`, `training/`, `evaluation/` and `tools/` print their options with `--help` and exit without opening hardware. The exceptions are `setup/1_find_ports.py`, `setup/2_get_offsets.py` and `setup/4_check_cameras.py`: they take no options and start talking to hardware immediately, even with `--help`. Run them only as [hardware setup](../procedures/02_hardware_setup.md) describes.
- **Ctrl+C is not an emergency stop.** It asks a foreground program to stop. During robot motion, use the physical emergency stop when needed.

## Dry-run effects

A dry run opens no robot, camera, leader, gripper, or scanner. Several programs still write files.

| Program | Effect of `--dry-run` | Writes |
| --- | --- | --- |
| `recording/run_control.py` | Records one metadata-only episode named `dry_<timestamp>`. It has no usable training frames. | `datasets/<medium>_<label_face>/collect_data/dry_<timestamp>/` (or under `--save-data-path` and `--project-name`) |
| `setup/teach_waypoints.py` | Writes synthetic poses marked `simulation_only: true` and `commissioned: false`. Live programs refuse them. It refuses an existing file unless `--overwrite` is given. | `--output` (default `config/waypoints.local.yaml`; always pass a different path) |
| `evaluation/run_cycle.py` | Simulates the robot, clock, scanner, and operator outcome. Without `--checkpoint` it also simulates the policy; with one, it loads the real model. It uses `config/waypoints.local.yaml` if present, otherwise synthetic poses. | Appends one row per attempt to `--csv` (default `cycle_logs/cycles.csv`, with `dry_run` set to `True`) |
| `evaluation/check_checkpoint.py` | Has no `--dry-run` flag. It is always hardware-free: it loads the model on the CPU and prints predictions for home joints and black images. | Nothing |
| `tools/simulate_motion.py` | `--dry-run` is required. Streams a scripted scan, drop, and home sequence for the left arm through the validated motion loop with synthetic poses. Prints each command and `Validated N simulated commands`. | Nothing |
| `recording/review_episodes.py` | Checks a `--set-status` or `--sync-review-status` batch and prints `Would mark ...` without changing files. | Nothing |
| `tools/curate_datasets.py` | Available on `quarantine`, `restore`, `transfer`, `top-up` and `merge`. Prints the planned file operations without applying them. `status` never changes files. | Nothing |
| `setup/check_wrist_rotation.py` | Runs the wrist sweep on a virtual robot with a fake scanner (read at 90° by default; `--fake-read-at`, `--fake-no-read`). It uses `config/waypoints.local.yaml` if present, which then needs a `rotation_direction` for the selected arm, otherwise synthetic poses. | Appends a report line only when `--report` is given |

`setup/check_waypoints.py --list` lists saved poses without opening devices. It has no `--dry-run`.

None of these programs establish physical clearance. Synthetic poses and simulated rows are never live assets or evaluation data.
