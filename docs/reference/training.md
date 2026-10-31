# Training reference

What the policies learn, how the training menu behaves, and what each model folder contains. For the steps, see [train models](../procedures/09_train_models.md). Parameter meanings are in [hyperparameters](hyperparameters.md); experiment planning is in [tuning](tuning.md).

## What the policies learn

The learned part picks up the parcel and carries it to the scan pose. The cycle supervisor does everything after that: the scanner window, backup wrist rotations, bin choice, release and homing (see [runtime](runtime.md)).

Both algorithms receive RGB images from the top, left-wrist and right-wrist cameras and 14 joint/gripper values. Scanner tokens, destination bins and label-face metadata are not observations. Actions are absolute joint and gripper targets for both arms, not deltas.

- **ACT** (Action Chunking with Transformers) predicts a chunk of future actions from one observation.
- **Diffusion Policy (DP)** denoises an action sequence from a short observation history.

Both are trained through the bundled robomimic stack (`robomimic-r2d2/`) with the same images, action normalization and frozen train/validation split. Train a separate model per medium. Validation loss measures prediction error on held-out recordings; it is not a physical success rate, and ACT's loss cannot be compared numerically with DP's.

## Menu behaviour

`python3 training/train_models.py` opens one menu that reads recording folders under `datasets/` directly. It never needs a robot server, conversion commands, registered copies or JSON editing.

| Option | Behaviour |
| --- | --- |
| 1. Show datasets and review counts | Lists each folder with `collect_data/` and its accepted, rejected, unreviewed, incomplete and invalid counts. |
| 2. Delete rejected recordings permanently | See [menu dataset operations](datasets.md#menu-dataset-operations). |
| 3. Move recordings | Keep the earliest N accepted (default 50) and move the overflow, move the N newest, or pick individually; destination folders are created. |
| 4. Train ACT / DP / both | Prepares data from the selected datasets and trains named models. |
| 5. Edit hyperparameter defaults | Separate ACT and DP profiles; saved immediately for future sessions. |
| 6. Models, reports and saved settings | Shows a model's settings, status, latest epoch, losses and checkpoint paths, and refreshes its report. Offers to start a model that was prepared but never started. |
| 7. Train using an existing model's frozen dataset and split | See [training on frozen data](#training-on-frozen-data). |

`b` returns to the main menu and `q` quits at any prompt. Training runs in the foreground; Ctrl+C stops it and keeps completed outputs. Edits made with **5** (or `e` at the confirmation) never change runs that were already prepared or started.

## Selecting datasets

Option **4** combines any selected datasets without copying or merging their folders. Only accepted, complete demonstration recordings are used; each must pass frame checks. The selection must contain a single medium and a single recording rate, the same recording cannot be selected twice (for example from a copy), and rollout recordings are refused. For the poly-mailer models, `poly_mailer_bottom_v1` and `poly_mailer_top_v1` are selected together; overflow `_extra` projects are included only if selected.

Model names may contain letters, numbers, `.`, `_` and `-`, must be new, and must differ between ACT and DP. The suggestion is `act_<medium>_vN` or `dp_<medium>_vN` with the next free N. Each checkpoint records its parcel medium, so any name works at runtime.

## Validation split

The default validation share is 20% and the default seed is 0. The split is made over whole parcel cycles (`cycle_id`), so recordings from the same cycle never land in both partitions. The number of validation cycles is the rounded share of all cycles, at least one, and at least one cycle stays in training; at least two independent cycles are required. With 100 independent recordings, 20% gives 80 training and 20 validation recordings; with linked recordings the counts can differ. Changing the seed changes the allocation.

Validation percentage and seed are shared settings: editing either in one profile updates both, so ACT and DP trained together always use the same recordings and split. If their image sizes differ, the menu prepares one dataset per size from identical recordings and checks that the splits match.

## Training runs and progress

When both algorithms are chosen, ACT trains first, then DP. Each run prints its epoch, training and validation loss, best validation loss and, after two epochs, an estimate of the remaining time for that model. The full output goes to `training.log`.

If ACT fails or is interrupted, DP stays prepared with status `ready`; start it from **6**. A failed or interrupted run cannot be resumed; train again under a new name. The menu checks that CUDA is available before preparing a CUDA run.

An epoch is a fixed number of training batches (`Training batches per epoch`), not a pass over every recording.

## Training on frozen data

Option **7** trains a new model on exactly the prepared dataset and split saved with an existing model. It reuses the same images, actions and train/validation allocation, so the comparison isolates the algorithm or its settings. The source model's split, seed and image size are kept; epochs, batch size, learning rate and algorithm settings come from the current defaults of the chosen algorithm. The default algorithm is the other one (DP for an ACT source). The source's prepared dataset and split file must still exist and match. Option **4** is the route for a new selection of raw recordings.

## Model folders

Each model lives in `ckpt/MODEL_NAME/`:

| Path | Content |
| --- | --- |
| `best.pth` | Relative link to the saved checkpoint with the lowest validation loss. |
| `latest.pth` | Relative link to the most recently saved checkpoint; it may differ from the best and from the final epoch. |
| `runs/` | Timestamped robomimic run with the real checkpoint files (`models/model_epoch_N[_best_validation_LOSS].pth`). |
| `training_summary.txt` | Readable settings, sources, counts and status. |
| `training_report.html`, `training_report.md` | Report with graphs; see [training reports](#training-reports). |
| `loss_curves.png`, `metrics.csv`, `metrics.jsonl` | Exportable graph, scalar metrics, and raw per-epoch records. |
| `full_configuration.csv` | Every saved configuration field, grouped and labelled. |
| `training.log` | Full trainer output. |
| `.training/` | Generated trainer configuration, split copy and job state. |

`ckpt` means checkpoint: saved learned model weights. A `.pth` file contains the model, its normalization statistics and its configuration, which runtime uses to restore the policy. Use `--checkpoint ckpt/MODEL_NAME/best.pth` for [cycles](../procedures/10_run_cycles.md). Keep the whole model folder together when moving it, and keep `datasets/.training_cache/` to reproduce runs (see [training cache](datasets.md#training-cache)). A model folder moved outside `ckpt/` no longer appears in the menu.

Checkpoints are saved every `Periodic checkpoint interval` epochs (default 50) and whenever validation loss reaches a new best.

## Training reports

New runs record every completed training and validation epoch. The report is regenerated after epoch 1, every 25 epochs, and when training completes or stops; choosing the model in **6** also refreshes it. `training_report.html` contains its graphs and opens in a browser without a server or internet connection.

Reports contain training and validation loss and their gap, learning rate, timing, ACT reconstruction and KL curves or DP gradient and data-loading metrics, dataset counts, the saved hyperparameters, best-checkpoint scores, and experiments to consider. The learning-rate graph appears only when the logged rate changes; a constant rate is stated in text.

The full configuration section, also in `full_configuration.csv`, distinguishes saved values, frozen-data facts, inferred rollout defaults for runs that lacked them, inactive fields, and current implementation constants. The report uses the run's saved settings, never the current menu defaults. Runs without per-epoch logs show available best-checkpoint scores as individual points and mark the missing history; the report never invents losses.

## Reading loss curves

A falling training loss with a sustained rise in validation loss is consistent with overfitting, but loss alone cannot prove the cause. Reports label hypotheses, discuss sampling noise and data diversity, and suggest changing one factor at a time. Validation loss also missed an ACT run that ignored its cameras (see [joint-input noise](hyperparameters.md#act-controls)). Rank models by physical grasp and scan success and cycle time on the same held-out placements, not by loss.
