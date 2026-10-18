# Matched ACT and Diffusion Policy training

Both algorithms use the same RGB images, 14 joint/gripper observations, action
normalization and frozen train/validation split. Train a separate pair for each
medium. No scanner, destination or label-face input is given to either policy.

Complete [recording](../recording/README.md) and [preparation](../datasets/preparation.md).
Run these steps in one terminal from the repository root with Python 3.8
`Xtrainer` activated. No robot server is needed. Stop recording before training.
See [terminal setup](../../terminal_commands.md).

## 1. Build a dataset and freeze its split

```bash
MEDIUM=poly_mailer
python3 scripts/convert_to_robomimic.py --recipe "$MEDIUM" \
  --projects "datasets/$MEDIUM" \
  --output "datasets/training/$MEDIUM.hdf5" \
  --split-file "datasets/training/$MEDIUM.split.json"
```

`MEDIUM=poly_mailer` sets a variable for this terminal. Use `envelope` or `carton`
to repeat the workflow for another medium. Keep the variable set for later steps.

| Argument | Meaning |
| --- | --- |
| `--recipe "$MEDIUM"` | Select the medium's dataset recipe; here it is `poly_mailer`. |
| `--projects "datasets/$MEDIUM"` | Read this prepared project folder containing `train_data/`. Several compatible folders can follow this option. |
| `--output "datasets/training/$MEDIUM.hdf5"` | Write the combined robomimic dataset to this new file. |
| `--split-file "datasets/training/$MEDIUM.split.json"` | Save the train/validation allocation and source hashes for both algorithms to share. |

If you rebuilt into `poly_mailer_v2`, use `--projects datasets/poly_mailer_v2`
while keeping `--recipe poly_mailer`. The recipe is the parcel type; the project
path identifies the actual prepared collection. Choose unused output filenames
when creating another training snapshot.

Default 80/20 allocation gives 40 training and 10 validation episodes from 50
independent accepted demonstrations. Linked cycles stay in one partition. At
least two independent cycles are needed. Source hashes protect the split;
changed sources require fresh dataset and split paths. An existing matching
split can be reused. `--allow-rollouts` is an explicit opt-in for separately
named rollout projects; leave it off for demonstration collections.

## 2. Generate the two training configurations

```bash
python3 scripts/configure_robomimic.py \
  --dataset "datasets/training/$MEDIUM.hdf5" \
  --split-file "datasets/training/$MEDIUM.split.json" \
  --output-dir "ckpt/${MEDIUM}_configs"
```

| Argument | Meaning |
| --- | --- |
| `--dataset ...hdf5` | Use the dataset created in step 1. |
| `--split-file ...split.json` | Verify and use the same frozen split; it must match the dataset. |
| `--output-dir "ckpt/${MEDIUM}_configs"` | Write both JSON configs and helper scripts here; for this example, `ckpt/poly_mailer_configs/`. |

The generated training configs are `poly_mailer_act.json` and
`poly_mailer_diffusion_policy.json`. Their `train.output_dir` points to `runs/`
under the configuration directory. Edit settings in `scripts/scripts_config.py`
before generating configs when changing shared experiment defaults.

## 3. Train ACT, then Diffusion Policy

Run the second command after the first training run finishes:

```bash
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "ckpt/${MEDIUM}_configs/${MEDIUM}_act.json"
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "ckpt/${MEDIUM}_configs/${MEDIUM}_diffusion_policy.json"
```

`PYTHONPATH=.:robomimic-r2d2` makes the repository and bundled trainer importable
for each command. `--config` selects the generated JSON file, including the
algorithm, dataset, split, hyperparameters, and output location. It does not
select an existing checkpoint. Keep the split unchanged and train both models
from scratch. Training saves timestamped experiment folders beneath
`ckpt/poly_mailer_configs/runs/`; use a saved `.pth` file from the experiment's
`models/` directory for evaluation.

## Small configuration checks

To generate small CPU configurations from your prepared dataset, use:

```bash
python3 scripts/configure_robomimic.py \
  --dataset "datasets/training/$MEDIUM.hdf5" \
  --split-file "datasets/training/$MEDIUM.split.json" \
  --output-dir "ckpt/${MEDIUM}_smoke_configs" --smoke --cpu
```

The three path arguments have the meanings above; the separate output directory
keeps these configs apart from full runs. `--smoke` reduces model sizes and
training to one epoch with two training steps. `--cpu` disables CUDA in the
generated configs. This command generates files; it does not train models.
To train them, use step 3's commands with the smoke directory and filenames
`poly_mailer_act_smoke.json` and `poly_mailer_diffusion_policy_smoke.json`
(substitute your medium). These models validate software only and must not run
live hardware. Model files, normalization statistics, and configuration are saved
in robomimic `.pth` checkpoints. The [runner](../runtime/evaluation.md) restores
normalization and pads/updates DP observation history, resetting it each cycle.

Compare physical success and cycle time using separate held-out placements;
validation loss alone is not a sorting-success measurement.

## Reproduce the software smoke check

For a complete synthetic check that needs no recorded dataset:

```bash
python3 scripts/smoke_training.py --output /tmp/parcel-model-smoke
```

`--output /tmp/parcel-model-smoke` chooses a new result directory; the command
refuses an existing one. Change the path for another run. It creates synthetic
files, trains tiny ACT and DP models, reloads each checkpoint and requests three actions without opening
hardware. It writes logs and `results.json`; the checkpoints are not usable
production policies.
