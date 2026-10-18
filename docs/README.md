# Documentation

Start with the repository [README](../README.md) for environment and device setup.
Run terminal examples from the repository root in the Python 3.8 `Xtrainer`
environment. Each workflow below has one primary guide.

Read [terminal commands](terminal_commands.md) for environment activation,
arguments, shell variables, example paths, terminal roles, and dry-run effects.
Each guide explains its own command values beside the example.

## Workflow

| Step | Guide |
| --- | --- |
| Set up parcels, labels and scanner | [Hardware and media](guides/hardware/media.md), [barcodes](guides/hardware/barcodes.md) |
| Teach scan, bin and recovery poses | [Joint waypoints](guides/hardware/waypoints.md) |
| Record demonstrations | [Recording protocol](guides/recording/README.md), [instructions by medium](guides/recording/media.md) |
| Review and convert accepted episodes | [Dataset preparation](guides/datasets/preparation.md) |
| Quarantine or combine collections | [Dataset curation](guides/datasets/curation.md) |
| Train comparison models | [Matched ACT and DP](guides/training/act_dp.md) |
| Train with the optional Dobot stack | [Vendor ACT](guides/training/vendor_act.md) |
| Run cycles and record outcomes | [Runtime and evaluation](guides/runtime/evaluation.md) |
| Inspect or recover the robot | [Homing and recovery](guides/hardware/homing.md) |

## Development and reference

- [Architecture](development/architecture.md): policy-step interface and supervisor responsibilities.
- [Scripts](../scripts/README.md) and [experiments](../experiments/README.md): active entrypoints and configuration.
- [Dobot user guide](provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf)
  and [FAQ](provided_dobot/Dobot%20X-Trainer%20Operation%20Guide%20and%20FAQ.pdf): manufacturer setup and operation.
