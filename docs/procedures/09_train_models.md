# Train models

The result is a named ACT and/or Diffusion Policy model under `ckpt/MODEL_NAME/` with `best.pth`, `latest.pth` and a training report.

## Before you start

- [Review the episodes](08_review_episodes.md) you want to train on. Only accepted, complete recordings are used.
- Stop the recorder. No robot server is needed.
- Training uses the GPU (CUDA) by default and runs in the foreground for hours. Use a terminal you can leave open:
  ```bash
  conda activate Xtrainer
  cd ~/dobot_xtrainer
  ```

## Open the menu

1. Start the menu.
   ```bash
   python3 training/train_models.py
   ```
   Expect: a numbered list from `1. Show datasets and review counts` to `7. Train using an existing model's frozen dataset and split`, and `q. Quit`.

At any prompt, `b` returns to the main menu and `q` quits. Number lists accept `1,3`, a range `1-3`, or `all`.

2. Choose **1** to check the datasets.
   Expect: one line per dataset with accepted, rejected, unreviewed, incomplete and invalid counts.

## Delete rejected recordings (optional)

3. Choose **2**, enter the dataset numbers, check the counts, and type `DELETE`.
   Expect: `Deleted N rejected recordings.` This is permanent; accepted and unreviewed recordings stay.

## Move overflow recordings (optional)

4. Choose **3** and one source dataset. Choose how to select recordings:
   `1` keep the earliest N accepted (default 50) and move the rest, `2` move the N newest, `3` pick by number.
5. Enter an existing destination number, or type a new name such as `poly_mailer_bottom_extra`. Type `MOVE`.
   Expect: `Moved N recordings. M accepted remain in SOURCE.` New destination folders are created automatically.

## Set hyperparameters (optional)

6. Choose **5**, then `1` (ACT) or `2` (DP).
7. Enter a setting number, then its value. Enter `a` for advanced settings. Press Enter to finish.
   Expect: the list reprints with the new value; it is saved for future sessions.
   Validation percentage and random seed are shared by ACT and DP. See [hyperparameters](../reference/hyperparameters.md).

## Train on selected datasets

8. Choose **4** and enter the dataset numbers, for example those of `poly_mailer_bottom_v1` and `poly_mailer_top_v1`.
9. Choose `1` ACT, `2` Diffusion Policy, or `3` both (default).
10. Enter a model name for each algorithm, or press Enter for the suggested `act_<medium>_vN` / `dp_<medium>_vN`.
    Expect: a summary with the datasets, `N accepted recordings: X training / Y validation`, the model names and each model's settings.
11. Type `e` to change settings, or `TRAIN` to start.
    Expect: `Reusing prepared data` or `Prepared N recordings`, then per-epoch lines such as `act_poly_mailer_v2: epoch 12/1000 | about 300 minutes remaining` and training/validation losses. With both algorithms, ACT trains first, then DP.
12. Wait for `training completed.`
    Expect: `Best checkpoint: .../ckpt/MODEL_NAME/best.pth` and `Training report: .../ckpt/MODEL_NAME/training_report.html`.

## Train on an existing model's frozen data

13. Choose **7** and select the source model, for example `act_poly_mailer_v1.1`.
14. Choose the algorithm (default: the other one), enter a new model name, and type `TRAIN`.
    Expect: `Frozen data from SOURCE: X training / Y validation recordings.` before training starts.

Use this to compare ACT and DP, or two ACT settings, on identical recordings and split. See [tuning](../reference/tuning.md).

## Inspect results

15. Choose **6** and select a model.
    Expect: its saved settings, status, latest epoch, validation loss, checkpoint paths, and the refreshed report path.
16. Open the report in a browser.
    ```bash
    xdg-open ckpt/act_poly_mailer_v1.1/training_report.html
    ```
    Expect: loss graphs, the saved settings and findings. See [training reports](../reference/training.md#training-reports).

Continue with [run cycles](10_run_cycles.md) using `--checkpoint ckpt/MODEL_NAME/best.pth`.

## If something goes wrong

- `Choose a new model name ...` -> the name exists already or has invalid characters; use letters, numbers, `.`, `_` and `-`.
- `Combine datasets of one parcel medium and one recording rate` -> select datasets of a single medium only.
- `At least two independent parcel cycles are needed` -> accept more recordings first.
- CUDA unavailable or out of memory -> lower the batch size in **5**, or set the training device to `cpu` (advanced).
- Training interrupted with Ctrl+C or failed -> completed outputs are kept; train again under a new model name. A prepared DP model that never started can be started from **6**.
- `Saved defaults could not be loaded` -> the menu keeps valid defaults; set your values again in **5**.
