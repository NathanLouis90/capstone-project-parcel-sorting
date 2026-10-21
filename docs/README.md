# Documentation

Use the repository [README](../README.md) for initial environment and device setup.
Use [terminal preparation](terminal_commands.md) before following a procedure.
Commands run from the repository root in the Python 3.8 `Xtrainer` environment.

Guides contain prerequisites, ordered actions, commands, expected results, and
recovery steps. Each topic's separate `README.md` explains its terms, options,
file formats, and implementation behavior. Safety instructions remain next to
hardware actions. See the [guide layout](guides/README.md).

## Workflow

| Task | Step-by-step guide | Explanation and options |
| --- | --- | --- |
| Prepare parcels and workspace | [Hardware/media](guides/hardware/media.md) | [Workspace layout](guides/hardware/README.md#workspace-layout-and-coordinate-frame), [parcel dimensions](guides/hardware/README.md#parcel-dimensions-and-label-faces) |
| Print labels and check scanner | [Scanner/labels](guides/hardware/barcodes.md) | [Scanner and labels](guides/hardware/README.md#scanner-and-destination-mapping) |
| Teach scan, bin, and receiving poses | [Waypoints](guides/hardware/waypoints.md) | [Waypoint meanings](guides/hardware/README.md#waypoint-names-and-arm-selection) |
| Record demonstrations | [Recording protocol](guides/recording/protocol.md), [by medium](guides/recording/media.md) | [Recording README](guides/recording/README.md) |
| Review and convert accepted episodes | [Dataset preparation](guides/datasets/preparation.md) | [Dataset README](guides/datasets/README.md) |
| Quarantine or combine collections | [Dataset curation](guides/datasets/curation.md) | [Curation behavior](guides/datasets/README.md#curation-behavior) |
| Train comparison models | [Matched ACT/DP](guides/training/act_dp.md) | [Training README](guides/training/README.md) |
| Train with the optional Dobot stack | [Vendor ACT](guides/training/vendor_act.md) | [Vendor options](guides/training/README.md#vendor-act-task-selection-and-options) |
| Run cycles and record outcomes | [Runtime/evaluation](guides/runtime/evaluation.md) | [Runtime README](guides/runtime/README.md) |
| Inspect or recover the robot | [Homing/recovery](guides/hardware/homing.md) | [Controller behavior](guides/hardware/README.md#homing-and-controller-behavior) |

## Terminal syntax

Use [terminal preparation](terminal_commands.md) for actions to run in each
terminal. These examples explain the syntax used by all guides:

| Example | Meaning |
| --- | --- |
| `python3 experiments/run_cycle.py` | Run the named Python script. Its arguments follow the filename. |
| `--medium poly_mailer` | An option followed by its value. Here, select the poly mailer workflow. |
| `--show-img` | A switch with no following value. Including it enables the image preview. |
| `status` in `curate_datasets.py status` | A subcommand: choose the operation before giving its options. |
| `PROJECT=poly_mailer_bottom` | Save a shell variable in the current terminal. Do not add spaces around `=`. |
| `"datasets/$PROJECT"` | Substitute the variable, giving `datasets/poly_mailer_bottom`. Quotes keep a path containing spaces together. |
| `"ckpt/${MEDIUM}_configs"` | Braces separate the variable name from the suffix, giving `ckpt/poly_mailer_configs`. |
| `PYTHONPATH=.:robomimic-r2d2` before `python3` | Make the repository (`.`) and bundled robomimic package importable for that command. `:` separates directories on Linux. |
| `\` at the end of a line | Continue the same command on the next line. Copy the whole block; leave no spaces after `\`. |
| `/path/to/model.pth` or `EPISODE_ID` | A placeholder. Replace it with an actual checkpoint path or episode folder name before running. |
| `/tmp/carton-cycle.csv` | An example output path in temporary storage. Choose a persistent path for results you need to keep. |

Shell variables belong to their terminal. A variable set in one terminal is not
automatically available in another. `--help` on documented entrypoints prints
options and exits; numbered calibration helpers are hardware programs and have
their own setup procedures. Ctrl+C requests a foreground process to stop and is
not a substitute for the physical emergency stop during robot motion.

## Dry-run effects

A dry run does not have one universal meaning. Several tools create files or
append results even though they do not move a robot:

| Tool | Effect of `--dry-run` |
| --- | --- |
| `run_control.py` | Opens no hardware; writes a metadata-only episode, with no usable training frames. |
| `teach_waypoints.py` | Opens no hardware; writes uncommissioned example poses to `--output`. |
| `run_cycle.py` | Simulates motion/scanner behavior and appends cycle rows to `--csv`. |
| `robomimic_runner.py` | Loads a checkpoint and prints predictions on synthetic observations; sends no robot commands. |
| `scripted_motion.py` | Exercises the simulated joint stream without moving hardware. |
| `review_episodes.py` | Checks a batch status/synchronization operation without changing files. |
| `curate_datasets.py` | Prints a proposed file operation plan without applying it. |

## Development and reference

- [Architecture](development/architecture.md): policy-step interface and supervisor responsibilities.
- [Tests](../tests/README.md): hardware-free regression suite, focused commands, and coverage by file.
- [Scripts](../scripts/README.md) and [experiments](../experiments/README.md): entrypoints and configuration.
- [Dobot user guide](provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf)
  and [FAQ](provided_dobot/Dobot%20X-Trainer%20Operation%20Guide%20and%20FAQ.pdf): manufacturer setup and operation.
