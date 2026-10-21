# Training: meaning and behavior

Use [matched ACT/DP training](act_dp.md) for the comparison stack. Use
[Dobot ACT training](vendor_act.md) for the optional vendor stack. These procedures
need the complete Python 3.8 `Xtrainer` setup from the repository README;
`requirements.txt` alone is insufficient. Neither procedure needs a robot server.

## What the policies learn

The learned part picks up the parcel and carries it to a scan pose. The
supervisor performs scanner-window handling, backup wrist rotations, bin choice,
release, and homing. Both comparison algorithms receive RGB camera images and
14 joint/gripper observation entries. Scanner tokens, destination bins, and
label-face metadata do not enter their observations.

ACT predicts an action chunk; Diffusion Policy predicts actions using its
configured observation/action horizons. The comparison uses the same images,
action normalization, and frozen train/validation split. A separate policy pair
is trained for each medium. Validation loss measures prediction quality on the
held-out data; it is not a physical sorting-success rate.

## Selecting datasets

`--projects` in `convert_to_robomimic.py` selects prepared project folders,
each containing `train_data/`. One folder selects one collection; several
compatible folders combine only those selected collections. For example,
`datasets/poly_mailer_top` and `datasets/poly_mailer_bottom` can supply one
mailer snapshot. Carton top/bottom/front/rear projects can be selected similarly.
Existing medium-only collections and registered rebuilt collections remain usable.

`--recipe` identifies the medium, not the collection name. A rebuilt
`poly_mailer_v2` project still uses `--recipe poly_mailer`. Without `--projects`,
the converter selects existing registered training folders for the recipe medium.
Explicit selection is useful when only particular sessions or faces should enter
training. Preparation and the converter exclude unaccepted data and default to
excluding rollouts.

### Dataset conversion options

| Argument | Meaning |
| --- | --- |
| `--recipe "$MEDIUM"` | Select the medium's dataset recipe; here it is `poly_mailer`. |
| `--projects "datasets/${MEDIUM}_bottom"` | Use only this prepared face collection containing `train_data/`. List several compatible folders to combine selected datasets. |
| `--output "datasets/training/$MEDIUM.hdf5"` | Write the combined robomimic dataset to this new file. |
| `--split-file "datasets/training/$MEDIUM.split.json"` | Save the train/validation allocation and source hashes for both algorithms to share. |

The dataset and split must be passed together to configuration generation. A
new source selection needs unused output paths. Rollout inclusion requires the
explicit opt-in and rollout naming rules described in the [dataset README](../datasets/README.md#curation-options).

## Frozen splits and shared configuration

The default train fraction is 0.8. Fifty independent accepted demonstrations
therefore give 40 training and 10 validation episodes. Demonstrations linked by
the same cycle remain in one partition to prevent leakage; at least two
independent cycles are required. With linked demonstrations, episode totals may
differ from a simple 80/20 count.

The split records source IDs, hashes, cycle IDs, recipe, and seed. Changed
sources require a new dataset and split. An existing matching split can be
reused. Both algorithms use the same train/validation filters and normalization.

| Argument | Meaning |
| --- | --- |
| `--dataset ...hdf5` | Use the dataset created in step 1. |
| `--split-file ...split.json` | Verify and use the same frozen split; it must match the dataset. |
| `--output-dir "ckpt/${MEDIUM}_configs"` | Write both JSON configs and helper scripts here; for this example, `ckpt/poly_mailer_configs/`. |

Shared defaults in `scripts/scripts_config.py` control camera inputs, resize,
training settings, horizons, and smoke settings. Generated normal configs are
`${MEDIUM}_act.json` and `${MEDIUM}_diffusion_policy.json`, and `train.output_dir`
points to `runs/` under the configuration directory. `--config` in the trainer
selects that JSON configuration, not an existing checkpoint.

## Checkpoint formats and runtime loading

| Stack | Saved assets | Runtime selection |
| --- | --- | --- |
| Matched robomimic ACT/DP | `.pth` file containing model, normalization statistics, and configuration; stored under a run's `models/` | `--backend robomimic --checkpoint /path/to/model.pth` |
| Vendor Dobot ACT | `config.pkl`, `dataset_stats.pkl`, and a model such as `policy_best.ckpt` together in one directory | `--backend vendor --checkpoint ckpt/PROJECT_vendor` |

The formats are distinct. Vendor `--model-name` chooses a model filename within
its checkpoint directory. The robomimic runner restores normalization and
maintains/pads DP observation history, resetting that history for each cycle.
The checkpoint's medium must match the requested runtime medium.

## Vendor ACT task selection and options

`--task_name` selects one registered project's prepared folder. Default examples
include `poly_mailer_bottom`, `envelope_top`, and `carton_front`. Original
`poly_mailer`, `envelope`, and `carton` tasks retain their medium-only folders.
`ModelTrain/constants.py` derives tasks from the shared project registry.
Custom checkpoint task names must remain registered for the requested medium.

| Command part | Meaning |
| --- | --- |
| `PYTHONPATH=.` | Allow this command to import modules from the repository root. |
| `MPLBACKEND=Agg` | Save plots without opening interactive plotting windows. |
| `--task_name poly_mailer_bottom` | Select only this registered project's prepared dataset. Use the exact project name from `scripts/scripts_config.py`. |
| `--ckpt_dir ./ckpt/poly_mailer_bottom_vendor` | Save this run's checkpoints, configuration, statistics, and plots in this directory. Choose a fresh directory per run. |
| `--batch_size 8` | Use eight training samples per batch; reduce this if GPU memory is insufficient. |
| `--num_steps 30000` | Set the training step limit to 30,000. This is not an episode count. |
| `--lr 2e-5` | Set the optimizer learning rate to `0.00002`. |
| `--chunk_size 45` | Predict a sequence of 45 actions at each policy query. |
| `--kl_weight 10` | Set the ACT latent-distribution regularization weight to 10. |
| `--seed 0` | Set the random seed for this run. Keep seeds recorded when comparing results. |

Vendor option names use underscores. `--validate_every 100` checks validation
loss every 100 steps; `--save_every 1000` writes periodic checkpoints every 1,000
steps. Those values and `--num_steps` are step counts, not episode counts.
`MPLBACKEND=Agg` saves plots without interactive windows. The loader reads every
HDF5 in the selected training folder, so accepted-only rebuilding is needed
after converted episodes are rejected. Registered settings control episode
horizon, train fraction, and camera names.

## Smoke checks

`configure_robomimic.py --smoke --cpu` generates small CPU configurations; it
does not run training. Smoke settings reduce model sizes and use one epoch with
two training steps. Filenames become `${MEDIUM}_act_smoke.json` and
`${MEDIUM}_diffusion_policy_smoke.json`. Separate output directories keep smoke
and full experiment artifacts apart.

`smoke_training.py --output NEW_DIRECTORY` creates synthetic data, trains tiny
ACT and DP models, reloads their checkpoints, and requests three actions from
each. It writes logs and `results.json`, opens no hardware, and refuses an
existing output directory. These checkpoints test software only and must not
be used on live hardware.

Physical success and cycle-time comparisons use separate held-out placements;
retries are reported separately in [cycle evaluation](../runtime/evaluation.md).
