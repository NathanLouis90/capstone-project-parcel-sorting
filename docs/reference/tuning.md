# Tuning reference

How to plan versioned ACT experiments so each run changes one factor. Menu steps are in [train models](../procedures/09_train_models.md); parameter meanings are in [hyperparameters](hyperparameters.md).

## Versioned model names

Model names such as `act_poly_mailer_v1.0`, `act_poly_mailer_v1.1` and `act_poly_mailer_v1.2` identify separate training experiments. The version label only names the run; the settings come from the menu defaults at the time it starts, and each run saves its own settings and report. Every version is a fresh training run; no optimizer state carries over from the previous version.

## Learning-rate comparison

Keep the dataset, split, seed, batch size, chunk length, architecture and training budget fixed, and change only the learning rate:

| Model name | Learning rate | Epochs | Batch size | ACT chunk length |
| --- | --- | --- | --- | --- |
| `act_poly_mailer_v1.0` | 0.0001 | 1000 | 8 | 16 |
| `act_poly_mailer_v1.1` | 0.00003 | 1000 | 8 | 16 |
| `act_poly_mailer_v1.2` | 0.00001 | 1000 | 8 | 16 |

These are controlled trials, not validated optimal settings: they keep the baseline and test two lower rates. The [original ACT training example](https://github.com/tonyzhaozh/act#simulated-experiments) uses 0.00001, but its dataset and epoch definition differ, so do not copy its epoch count.

Use 100 training and 10 validation batches per epoch, 20% validation and seed 0. Leave the advanced ACT settings at their baseline: hidden dimension 512, feedforward 3200, 4 encoder and 7 decoder layers, 8 heads, latent dimension 32, KL weight 20, pretrained backbone, 128-pixel images.

## Setting each version

In the menu, choose **5**, **1. ACT**, then **3. Learning rate**, and check **1. Epochs**, **2. Batch size** and **6. ACT chunk length** against the table. Edits are saved immediately and apply to every later run until changed; existing models keep their saved settings.

Train the baseline with option **4** on `poly_mailer_bottom_v1` and `poly_mailer_top_v1`. For later versions, change the learning rate, then use option **7** with the baseline as the source. This keeps images, actions, split, seed and image size identical; the new version uses the current ACT defaults.

A model folder moved out of `ckpt/` (for example into an archive folder) no longer appears in the menu, though its checkpoints and report stay in that folder. An archived model and a newly trained `ckpt/act_poly_mailer_v1.0/` are separate runs even when they share a name; option **7** can only use a source that is still under `ckpt/` and whose prepared data still exists.

## Comparing outcomes

Use option **6** to inspect each version's report: loss curves over many epochs, saved settings, and the best-checkpoint epoch. For physical tests, use the same held-out parcel placements for every version and record grasp and scan success, drops and cycle time.

Keep both the best-validation checkpoint and later checkpoints available for evaluation. The [ACT authors' tuning notes](https://github.com/tonyzhaozh/act) observe that physical smoothness and success can keep improving after the loss plateaus. A validation minimum at epoch 107, for example, does not show that later checkpoints are worse on the robot.

After choosing a learning rate, hold it fixed and change one other factor, such as chunk length or model size, in the next versions. Physical tests and reports guide the choice; version numbers only label it.

Temporal ensembling and replan interval can be compared on the same trained weights without retraining; see [ACT rollout](act_rollout.md). Record those inference settings with the physical results, because their effect does not appear in training or validation loss.
