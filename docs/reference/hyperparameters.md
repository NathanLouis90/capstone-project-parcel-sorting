# Hyperparameters reference

Every training-menu setting, the additional backend settings saved with each model, and how to read the full configuration inventory. To change settings, use option **5** in [train models](../procedures/09_train_models.md). For experiment planning, see [tuning](tuning.md).

## Where the values are recorded

Each model's `training_report.html`, `training_report.md` and `training_summary.txt` include the full saved configuration, grouped by purpose, with each field's value, whether it is active, and its menu location. `full_configuration.csv` holds the same inventory for comparing runs.

The inventory also lists bookkeeping, disabled evaluation options and backend defaults; not all of these are useful tuning controls. The report prefers the trainer's captured run configuration over an input file edited afterwards, and never replaces a run's settings with current menu defaults.

## Common controls (saved separately for ACT and DP)

Open **5. Edit hyperparameter defaults**, choose **1. ACT** or **2. DP**, then the setting number. The values below are built-in starting defaults; the model's report shows what a run actually used.

| # | Parameter | Default | Meaning |
| --- | --- | --- | --- |
| 1 | Epochs | 1000 | Maximum training rounds. |
| 2 | Batch size | 8 | Sequence samples per optimizer update. Reduce if GPU memory is insufficient. |
| 3 | Learning rate | 0.0001 | Initial policy learning rate. |
| 4 | Training batches per epoch | 100 | Fixed update budget per epoch; an epoch is not a pass over all recordings. |
| 5 | Validation batches per epoch | 10 | Sampled validation batches per epoch. |
| 6 | ACT chunk length / DP prediction horizon | 16 | Length of the predicted action sequence; the meaning differs by algorithm. |
| 7 | Validation percentage | 20 | Shared split setting, applied when preparing new data. |
| 8 | Random seed | 0 | Shared split seed and training seed. |
| adv. | Periodic checkpoint interval | 50 epochs | Best-validation checkpoints are saved separately. |
| adv. | Image size | 128 (square pixels) | Applied when preparing new data; minimum 80. |
| adv. | Training device | `cuda` | `cpu` is also supported. |

Editing 7 or 8 in either profile updates both, so paired training uses the same recordings. Training on another model's frozen data (option **7**) keeps that model's split, seed and image size; the other settings come from the chosen algorithm's defaults.

The editor validates values before saving: positive integers for counts and sizes, a finite positive learning rate, a seed below 2^32, and the per-algorithm rules below.

## ACT controls

Choose **a. Advanced ACT settings** in the ACT editor.

| # | Parameter | Default | Meaning |
| --- | --- | --- | --- |
| 1 | KL weight | 20 | Weight on the variational KL regularization. |
| 2 | Hidden dimension | 512 | Transformer embedding width. Must divide evenly by the attention heads. |
| 3 | Feedforward dimension | 3200 | Transformer feedforward width. |
| 4 | Encoder layers | 4 | Encoder depth. |
| 5 | Decoder layers | 7 | Decoder depth. |
| 6 | Attention heads | 8 | Attention heads per layer. |
| 7 | Latent dimension | 32 | Variational latent width. |
| 8 | Pretrained image backbone | yes | Start the image network from pretrained weights. |
| 9 | Temporal ensembling | no | Rollout only: blend overlapping action predictions. |
| 10 | Ensemble coefficient | 0.01 | Rollout only: positive favours older, zero averages, negative favours newer predictions. |
| 11 | Replan interval with ensembling off | 0 | Rollout only: 0 executes the full chunk; otherwise predict again after this many steps (at most the chunk length). |
| 12 | Joint-input noise std | 0.5 | Training only: Gaussian noise on normalized joint inputs; 0 disables it. Validation and rollout are noise-free. |

Items 13–15 are the shared advanced settings (checkpoint interval, image size, device).

Settings 9–11 are saved in new checkpoints and reports but do not change the training loss, and can be overridden at rollout without retraining. With ensembling on, ACT predicts every control step whatever the stored replan interval. Checkpoints missing these fields use clearly labelled fallbacks (ensembling off, full chunk). See [ACT rollout](act_rollout.md).

Joint-input noise exists because the first poly-mailer ACT run (`act_poly_mailer_v1.0`, trained without it) learned to predict actions from the joint angles alone: from epoch 100 onward, swapping the camera scene changed its predictions by 0.000 rad, and it drove toward an average parcel position and stopped. Validation loss did not reveal this. A 150-epoch pilot with noise 0.5 changed predictions by 0.20–0.32 rad when the scene changed, at similar validation loss. Runs trained before this setting existed report it as 0 (off). When comparing runs, check camera use directly, not only validation loss.

## DP controls and saved DP settings

Choose **a. Advanced DP settings** in the DP editor for items 1–5.

| # | Parameter | Default | Meaning |
| --- | --- | --- | --- |
| 1 | Observation history | 2 | Observation frames used for each prediction. |
| 2 | Executed action horizon | 8 | Actions executed before predicting again. |
| 3 | U-Net dimensions | 256, 512, 1024 | Denoising network widths; at least two multiples of 8. |
| 4 | Training diffusion steps | 100 | DDPM noise schedule length. |
| 5 | Inference diffusion steps | 100 | DDPM sampling steps per prediction; at most the training steps. |
| common 6 | Prediction horizon | 16 | Total predicted sequence length. |

The prediction horizon must satisfy `observation history - 1 + executed action horizon <= prediction horizon`, and be a multiple of 2^(number of U-Net levels - 1) (4 for the default three levels). Changing ACT chunk length does not change DP prediction horizon.

Saved but not exposed in the menu: U-Net timestep embedding 256, convolution kernel 5, normalization groups 8, EMA enabled with power 0.75, DDPM scheduler with `squaredcos_cap_v2` noise schedule, `epsilon` prediction, sampled-output clipping on. DDIM fields are present but labelled inactive.

## Optimizer and objective

| Parameter | ACT | DP | Notes |
| --- | --- | --- | --- |
| Optimizer | AdamW | Adam | Not exposed in the menu. |
| Weight decay | 0.0001 | 0 | Not exposed. |
| Gradient clipping | none | none | Not exposed. |
| Learning-rate scheduler | `linear` named, inactive | `multistep` fallback, inactive | An empty epoch schedule means no scheduler is built. |
| Learning-rate epoch schedule | `[]` | `[]` | Not exposed. |
| Decay factor | 1 | 0.1 | No effect while the schedule is empty. |
| Objective | Reconstruction L1 + KL weight × KL | Denoising loss | The values cannot rank ACT against DP. |
| Image backbone | `resnet18` | not applicable | Not exposed. |

ACT's own loss ignores the generic `algo.loss.l1_weight`, `l2_weight` and `cos_weight` fields, and its backbone ignores generic `observation.encoder` options; the report labels these unused. It also lists current bundled ACT build defaults that runs do not store, such as dropout 0.1, ReLU activation, no pre-layer normalization, no dilation, sine position embeddings and fixed image normalization. These are labelled implementation defaults, not verified historical settings.

## Data, checkpoint and bookkeeping fields

The inventory also lists every saved field for:

- dataset paths, frozen train/validation masks, sequence length, frame stacking, padding, action and observation normalization, data workers, caching and HDF5 read settings;
- input modalities, camera names, unused goal/depth/scan channels and generic encoder configuration;
- checkpoint enablement, intervals, explicit save epochs and save conditions;
- optional training-time rollouts, rendering and videos (marked inactive when disabled);
- logging switches, experiment names, output folders and initialization paths;
- derived snapshot facts: actual training and validation counts, image size, split seed and actual validation percentage.

An empty list, empty object, `False`, zero and `null` stay distinct, and no field is dropped for being disabled or unfamiliar.

## Learning-rate graph

The settings table records the configured initial rate; the epoch log records the optimizer's actual rate. A schedule or warmup makes them differ, so a changing rate is plotted to relate loss changes to optimizer changes. When every logged rate is constant, the report states the rate and the number of epochs instead of drawing a flat line. Without logged history, it says the rate cannot be verified. For example, `act_poly_mailer_v1.0` used 0.0001 for all 1,000 epochs: its scheduler was named `linear`, but the empty epoch schedule meant none was built.
