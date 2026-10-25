# Tune ACT with versioned experiments

Use model names such as `act_poly_mailer_v1.0`, `act_poly_mailer_v1.1`, and
`act_poly_mailer_v1.2` to identify separate training experiments. Choose the
hyperparameters in the menu before each run; the version label identifies the
saved run. Each run saves its own settings and report.

## Start with a learning-rate comparison

Keep the dataset, train/validation split, random seed, batch size, action chunk,
architecture, and training budget fixed. Change only learning rate:

| Model name | Learning rate | Epochs | Batch size | ACT chunk length |
| --- | --- | --- | --- | --- |
| `act_poly_mailer_v1.0` | `0.0001` | 1000 | 8 | 16 |
| `act_poly_mailer_v1.1` | `0.00003` | 1000 | 8 | 16 |
| `act_poly_mailer_v1.2` | `0.00001` | 1000 | 8 | 16 |

These are proposed controlled trials, not validated optimal settings. They retain
the existing baseline and test two lower learning rates. The original
[ACT training example](https://github.com/tonyzhaozh/act#simulated-experiments)
uses `0.00001`. Its dataset and epoch definition differ from this repository, so
do not copy its epoch count directly.

Use 100 training batches per epoch, 10 validation batches per epoch, a 20%
validation split, and seed 0 for this initial comparison. Leave advanced ACT
settings at the baseline values: hidden dimension 512, feedforward dimension
3200, 4 encoder layers, 7 decoder layers, 8 attention heads, latent dimension 32,
KL weight 20, pretrained image backbone enabled, and 128-pixel images.

## Set the next run's defaults

From the repository root with `Xtrainer` active:

```bash
python3 scripts/train_models.py
```

1. Choose **5. Edit hyperparameter defaults**.
2. Choose **1. ACT**.
3. Choose **3. Learning rate** and enter the value for this version.
4. Check **1. Epochs**, **2. Batch size**, and **6. ACT chunk length** against the
   table. Keep the other settings fixed for the comparison.
5. Press Enter to finish, or `b` to return to the main menu. Valid edits are saved
   immediately and remain in effect for subsequent runs and menu sessions.

Changing defaults affects future jobs. Existing model runs retain their saved
settings. Each version starts a fresh policy training run; these menu operations
do not resume optimizer state from the previous version.

## Train the baseline and reuse its data

For the new `1.0` baseline, choose **4**, select `poly_mailer_bottom_v1` and
`poly_mailer_top_v1`, choose **ACT**, and enter `act_poly_mailer_v1.0` as the name.
Read the confirmation and type `TRAIN` when ready.

For `1.1` and `1.2`, first change the learning rate using option **5**. Then choose
**7. Train using an existing model's frozen dataset and split**, select the new
`act_poly_mailer_v1.0` baseline, choose **ACT**, and enter the new version name.
This keeps the images, actions, split, seed, and image size identical across runs.
The new version uses the current ACT training defaults.

An archived model outside `ckpt/` does not appear in the training menu. Its
checkpoints and report remain available in its archive folder. The original
completed model was moved to `/home/adiel/old_models/act_poly_mailer_v1.0/`;
that archive is separate from a newly trained `ckpt/act_poly_mailer_v1.0/`.

## Compare outcomes before changing another parameter

Choose **6** to inspect each version's report. Compare the loss curves over many
epochs, saved settings, and best-checkpoint epoch. For physical testing, use the
same held-out parcel placements for every version and record grasp/scan success,
drops, and cycle time.

Keep candidates from both the best-validation epoch and later training available
for evaluation. The [ACT authors' tuning guidance](https://github.com/tonyzhaozh/act)
notes that physical smoothness and success can improve after loss plateaus.
A validation minimum at epoch 107 alone does not establish that all later
checkpoints perform worse on the robot.

After comparing learning rates, hold the preferred rate fixed and change one
other factor, such as chunk length or model size, in the next versions. Physical
testing and the reports should guide the choice; version numbers only label it.
