# Read and run terminal commands

The guides use Bash on the robot PC. Run commands from the repository root,
which contains `experiments/`, `scripts/`, and `README.md`.

## Prepare each terminal

```bash
conda activate Xtrainer
cd /home/adiel/dobot_xtrainer
```

`conda activate Xtrainer` selects this project's Python environment. `cd` changes
the working directory. Replace `/home/adiel/dobot_xtrainer` if your checkout is
elsewhere. Repeat both commands in each new terminal. The installation commands
in the main README are for initial setup, not every session.

## Understand the syntax

| Example | Meaning |
| --- | --- |
| `python3 experiments/run_cycle.py` | Run the named Python script. Its arguments follow the filename. |
| `--medium poly_mailer` | An option followed by its value. Here, select the poly mailer workflow. |
| `--show-img` | A switch with no following value. Including it enables the image preview. |
| `status` in `curate_datasets.py status` | A subcommand: choose the operation before giving its options. |
| `PROJECT=poly_mailer` | Save a shell variable in the current terminal. Do not add spaces around `=`. |
| `"datasets/$PROJECT"` | Substitute the variable, giving `datasets/poly_mailer`. Quotes keep a path containing spaces together. |
| `"ckpt/${MEDIUM}_configs"` | Braces separate the variable name from the suffix, giving `ckpt/poly_mailer_configs`. |
| `PYTHONPATH=.:robomimic-r2d2` before `python3` | Make the repository (`.`) and bundled robomimic package importable for that command. `:` separates directories on Linux. |
| `\` at the end of a line | Continue the same command on the next line. Copy the whole block; leave no spaces after `\`. |
| `/path/to/model.pth` or `EPISODE_ID` | A placeholder. Replace it with an actual checkpoint path or episode folder name before running. |
| `/tmp/carton-cycle.csv` | An example output path in temporary storage. Choose a persistent path for results you need to keep. |

`--help` prints an entrypoint's options and exits. Use it on the documented
recording, dataset, training, scanner, waypoint, and cycle entrypoints when you
need the full option list. Numbered calibration helpers are hardware programs;
follow their setup instructions rather than assuming they accept `--help`.

## Know what stays running

| Task | Terminals and programs |
| --- | --- |
| Record demonstrations | Terminal 1: keep `launch_nodes.py` running. Terminal 2: run `run_control.py`. |
| Teach poses with leaders | Keep those two running; use Terminal 3 for `teach_waypoints.py` after disabling following on both arms. See the [walkthrough](guides/hardware/waypoints.md#use-three-terminals). |
| Run a live cycle | Terminal 1: robot server. Terminal 2: `run_cycle.py`. Stop the recorder first. |
| Review, convert, train, or simulate | One terminal; these commands do not need a robot server. Stop recording before training. |
| Inspect, recover, or home directly | Use `robot_home.py` as described in [homing](guides/hardware/homing.md). Stop command clients before recovery or motion. |

Keep shell variables and commands that use them in the same terminal. `Ctrl+C`
requests that the foreground program stop; during hardware motion it does not
replace the physical emergency stop.

## Check what a dry run writes

`--dry-run` means different things in different tools. Read the explanation next
to the example before running it.

| Tool | Effect of `--dry-run` |
| --- | --- |
| `run_control.py` | Opens no hardware; writes a metadata-only episode, with no usable training frames. |
| `teach_waypoints.py` | Opens no hardware; writes uncommissioned example poses to `--output`. |
| `run_cycle.py` | Simulates motion/scanner behavior and appends cycle rows to `--csv`. |
| `robomimic_runner.py` | Loads a checkpoint and prints predictions on synthetic observations; sends no robot commands. |
| `scripted_motion.py` | Exercises the simulated joint stream without moving hardware. |
| `review_episodes.py` | Checks a batch status/synchronization operation without changing files. |
| `curate_datasets.py` | Prints a proposed file operation plan without applying it. |
