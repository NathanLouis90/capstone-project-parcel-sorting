# Documentation

Two kinds of page:

- **Procedures** say what to do, in order, with commands you can paste from the
  repository root. They contain no background.
- **Reference** pages explain how things work: terms, options, file formats,
  safety logic and limitations. Procedures link to them where it helps.

Prepare every terminal the same way before running a procedure:

```bash
conda activate Xtrainer
cd ~/dobot_xtrainer
```

## Procedures

Follow these in order the first time. Later sessions usually start at step 7, 9 or 10.

| Step | Procedure | Reference |
| --- | --- | --- |
| 1 | [Install the software](procedures/01_install.md) | [Commands and terminals](reference/commands.md) |
| 2 | [Set up the hardware](procedures/02_hardware_setup.md) | [Hardware](reference/hardware.md) |
| 3 | [Print labels and check the scanner](procedures/03_labels_and_scanner.md) | [Hardware: scanner](reference/hardware.md) |
| 4 | [Prepare the workspace and parcels](procedures/04_workspace.md) | [Hardware: workspace](reference/hardware.md) |
| 5 | [Teach waypoints](procedures/05_teach_waypoints.md) | [Hardware: waypoints](reference/hardware.md) |
| 6 | [Check waypoints and wrist rotation](procedures/06_check_waypoints.md) | [Hardware: waypoints](reference/hardware.md) |
| 7 | [Record demonstrations](procedures/07_record_episodes.md) | [Recording](reference/recording.md) |
| 8 | [Review episodes](procedures/08_review_episodes.md) | [Datasets](reference/datasets.md) |
| 9 | [Train ACT and DP](procedures/09_train_models.md) | [Training](reference/training.md), [hyperparameters](reference/hyperparameters.md), [tuning](reference/tuning.md) |
| 10 | [Run sorting cycles](procedures/10_run_cycles.md) | [Runtime](reference/runtime.md), [ACT rollout](reference/act_rollout.md) |
| 11 | [Evaluate poly mailers](procedures/11_evaluate_poly_mailer.md) | [Runtime](reference/runtime.md) |

As needed:

| Procedure | Reference |
| --- | --- |
| [Home and recover the robot](procedures/home_and_recover.md) | [Hardware: homing](reference/hardware.md) |
| [Curate datasets](procedures/curate_datasets.md) | [Datasets](reference/datasets.md) |

## Reference

- [Architecture](reference/architecture.md): code layout, processes, policy-step contract, cycle flow.
- [Commands and terminals](reference/commands.md): shell syntax, terminal roles, what each dry run writes.
- [Tests](reference/tests.md): the hardware-free regression suite.
- Manufacturer manuals: [Dobot X-Trainer user guide](provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf)
  and [operation guide and FAQ](provided_dobot/Dobot%20X-Trainer%20Operation%20Guide%20and%20FAQ.pdf).
- Example labels: [docs/label_examples](label_examples/).

## Writing new pages

Put new instructions in `procedures/` and new explanations in `reference/`.
A procedure step is one action, one pasteable command block and one
`Expect:` line. Put background, option tables and design reasons in the
reference page and link to it.
