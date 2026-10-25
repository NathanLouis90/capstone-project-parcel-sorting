# Manage recordings and train from one menu

Keep reviewing episodes with `review_episodes.py` as before. After review, stop
recording, activate `Xtrainer`, and run this command from the repository root:

```bash
python3 scripts/train_models.py
```

No robot server is needed. The menu discovers recording folders automatically:

```text
1. Show datasets and review counts
2. Delete rejected recordings permanently
3. Move recordings (destination folders are automatic)
4. Train ACT / DP / both
5. Edit hyperparameter defaults
6. Models, reports and saved settings
7. Train using an existing model's frozen dataset and split
q. Quit
```

Enter `b` at a prompt to return to the main menu, or `q` to quit. Training runs
in the foreground; use Ctrl+C to interrupt it. Completed outputs are preserved.

## Delete rejected recordings

Choose **2**, then select datasets by number. Enter several numbers, such as
`1,3`, a range such as `1-3`, or `all`. Check the counts and type `DELETE`.

This permanently removes explicitly rejected recordings and their attributable
old conversions, videos, and conversion logs. There is no quarantine. Accepted
and unreviewed recordings remain. Review alone still records a decision; deletion
occurs only when you confirm this menu operation. Existing trained models and
their frozen training snapshots remain unchanged.

## Move recordings

Choose **3**, then one source dataset. Choose one of these selection methods:

- Keep the earliest N accepted recordings and move the overflow. Enter `50` to
  keep the earliest 50 accepted recordings.
- Move N newest accepted recordings.
- Select individual recordings by number.

Select an existing destination by number, or type a new dataset name, such as
`poly_mailer_bottom_extra`. The menu creates the folders. Type `MOVE` to apply.
You do not need `mkdir` or a registration in `scripts_config.py`. Recording IDs
and review decisions are preserved. Collisions and incompatible media, schemas,
cameras, or recording rates are refused before the move.

## Train one model or a matched pair

1. Choose **4**, then the dataset numbers to include. For your poly mailers,
   select `poly_mailer_bottom_v1` and `poly_mailer_top_v1`. Leave the extra
   collections unselected unless you want their recordings included.
2. Choose ACT, Diffusion Policy, or both. Only accepted, complete demonstrations
   are eligible. Select datasets of one medium and recording rate. Duplicate
   copies of a recording are refused.
3. Enter model names, such as `act_poly_mailer_v2` and `dp_poly_mailer_v2`.
   Existing model names cannot be overwritten. Suggested names use the next
   available version for each algorithm.
4. Read the dataset list, actual training/validation counts, model names, and
   training settings. Enter `e` to edit settings, or type `TRAIN` to start.

The default validation share is 20%. With 100 independent recordings, this gives
80 training recordings and 20 validation recordings. Episodes from the same
parcel cycle stay together, so linked recordings can change those counts.
Changing the random seed changes the allocation. ACT and DP use the same frozen
recordings and split when you choose both.

The menu prepares training data directly from raw recordings. There is no manual
conversion, snapshot-folder registration, split filename, or JSON editing.
Changed recordings or split settings create new prepared data automatically.
Compatible unchanged data is reused after checking its integrity.

Both models train sequentially: ACT first, then DP. Progress shows epochs,
training/validation loss, and an estimated remaining time after two epochs.
The estimate covers the current model. Full output is saved automatically.
If ACT fails or is interrupted, DP remains prepared; choose **6** and select the
ready DP model to start it later. A failed or interrupted run requires a new
model name to train again; this menu does not resume optimizer state.

## Train DP on the same data as an existing ACT run

Choose **7**, select the existing ACT model, choose **DP**, and enter a new model
name, such as `dp_poly_mailer_v1.0`. Inspect the settings and type `TRAIN`.
Use `e` to edit hyperparameter defaults before starting.

This reuses the exact frozen images, actions, and train/validation allocation
from the source model. It does not rebuild raw recordings or depend on an old
`*_configs` folder. The original dataset, split seed, and image size remain fixed;
epochs, batch size, learning rate, and algorithm settings come from DP defaults.
Keep the original frozen dataset and its split file. The menu records the parcel
medium in new checkpoints, including when their source is an older dataset.

Option **4** remains the route for a new selection of accepted raw datasets.

## Change hyperparameters and inspect results

For a concrete `1.0` / `1.1` / `1.2` experiment plan, see
[ACT hyperparameter tuning](tuning.md).

Choose **5. Edit hyperparameter defaults**, or enter `e` before confirming training.
The editor first asks which algorithm to configure:

```text
1. ACT
2. DP
```

Each algorithm has its own saved epochs, batch size, learning rate, training and
validation batches per epoch, image size, checkpoint interval, and CPU/GPU choice.
The training confirmation shows the actual settings for each selected model.

In the ACT editor, setting **6** is **ACT chunk length**: how many action steps
ACT predicts together. Its default is 16. Advanced ACT settings include KL weight,
latent dimension, transformer dimensions/layers/heads, and the pretrained backbone.

In the DP editor, setting **6** is **DP prediction horizon**, also defaulting to
16 action steps. Advanced DP settings include observation history, executed action
horizon (default 8), U-Net dimensions, and training/inference diffusion steps.
Changing ACT chunk length does not change DP prediction horizon. The editor
checks that DP horizons fit and that network widths and diffusion steps are valid.

Validation percentage and random seed remain shared, and the editor labels them
as shared split settings. Editing either updates both profiles so paired training
uses the same recording allocation. If image sizes differ, the menu prepares
separate image datasets with identical source recordings and splits.

Edits are saved automatically for future menu sessions. Existing single-profile
preferences carry over to both algorithms, and subsequent edits are independent.
Edits do not alter runs that were already prepared or started.

An epoch runs the configured number of training batches. Epochs are not episode
counts. Reduce batch size if GPU memory is insufficient. CUDA is the default;
the menu checks availability before preparing a new training run.

Choose **6** to inspect a model's saved settings, sources, training/validation counts,
latest epoch, and available validation loss. Your existing models also
appear, with their original saved settings.

## Read training reports and graphs

New menu runs save every completed training and validation epoch automatically.
The report updates after epoch 1, every 25 epochs, and on completion or interruption.
Choose **6**, then a model, to refresh its report and display the report path.
Open `ckpt/MODEL_NAME/training_report.html` in a browser, or read
`training_report.md` in an editor. The HTML contains its graphs and needs no server
or internet connection.

Reports include training/validation loss, their gap, learning rate, timing,
ACT reconstruction/KL curves or DP gradient/data-loading metrics, dataset counts,
actual saved hyperparameters, best-checkpoint scores, and improvement experiments
to consider. `loss_curves.png` is an exportable graph; `metrics.csv` contains full
scalar metrics. You do not need to edit any of these files. Raw epoch records are
retained immediately in `metrics.jsonl`, with full console output in `training.log`.

A falling training curve with sustained rising validation loss is consistent with
overfitting. Loss alone cannot prove its cause. Reports label hypotheses, discuss
sampling noise and data diversity, and suggest changing one factor at a time.
ACT's reconstruction-plus-KL loss and DP's denoising loss have different meanings;
compare physical grasp/scan success and cycle time to rank the algorithms.

Older runs that did not retain epoch logs cannot recover full loss curves. Their
reports show available saved best-checkpoint scores as individual points and mark
the missing history explicitly. User-provided terminal observations are labeled
separately. The report does not invent missing training losses.

`ckpt` means **checkpoint**: saved learned model weights. A training configuration
records the choices used to learn those weights, such as learning rate and batch
size. The menu writes both automatically; you do not need to edit either.

Each new menu-trained model provides short checkpoint paths automatically:

```text
ckpt/MODEL_NAME/best.pth
ckpt/MODEL_NAME/latest.pth
```

`best.pth` selects the saved checkpoint with the lowest validation loss.
`latest.pth` selects the most recently saved epoch; it may differ from the best
checkpoint or the final training epoch. The menu prints these paths after training
and under **6. Models and saved settings**. For example, use
`--checkpoint ckpt/act_poly_mailer_v2/best.pth` for rollout.

These are relative symbolic links to the original checkpoint files. Historical
checkpoints retain their detailed names for comparison, without duplicating model
weights. Keep the entire model folder together when moving it.

For reference, each new model lives under `ckpt/MODEL_NAME/`. Its readable
`training_summary.txt` records settings, `training.log` contains full output,
and its `runs/` directory contains timestamped checkpoints. Generated trainer
files are hidden in `.training/`; prepared data and preferences are hidden in
`datasets/.training_cache/`. Keep these files to reproduce existing runs.

Use a saved `.pth` checkpoint with the existing
[runtime and evaluation procedure](../runtime/evaluation.md). Custom model names
are supported because new checkpoints record their parcel medium separately.
