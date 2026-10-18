# Matched ACT and Diffusion Policy training

Both algorithms use the same RGB images, 14 joint/gripper observations, action
normalization and frozen train/validation split. Train a separate pair for each
medium. No scanner, destination or label-face input is given to either policy.

Complete [recording](../recording/README.md) and [preparation](../datasets/preparation.md).
Run from the repository root in Python 3.8 `Xtrainer`:

```bash
MEDIUM=poly_mailer
python3 scripts/convert_to_robomimic.py --recipe "$MEDIUM" \
  --projects "datasets/$MEDIUM" \
  --output "datasets/training/$MEDIUM.hdf5" \
  --split-file "datasets/training/$MEDIUM.split.json"
python3 scripts/configure_robomimic.py \
  --dataset "datasets/training/$MEDIUM.hdf5" \
  --split-file "datasets/training/$MEDIUM.split.json" \
  --output-dir "ckpt/${MEDIUM}_configs"
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "ckpt/${MEDIUM}_configs/${MEDIUM}_act.json"
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "ckpt/${MEDIUM}_configs/${MEDIUM}_diffusion_policy.json"
```

Use `envelope` or `carton` for the other recipes. Keep the same split for both
algorithms and train from scratch. Default 80/20 allocation gives 40 training
and 10 validation episodes from 50 independent accepted demonstrations. Linked
cycles stay in one partition. At least two independent cycles are needed.
Source hashes protect the split; changed sources require fresh output paths.

`--smoke --cpu` on configuration generation creates small one-epoch/two-step
checks with `_smoke` names. These models validate software only and must not run
live hardware. Model files, normalization statistics and configuration are saved
in robomimic `.pth` checkpoints. The [runner](../runtime/evaluation.md) restores
normalization and pads/updates DP observation history, resetting it each cycle.

Compare physical success and cycle time using separate held-out placements;
validation loss alone is not a sorting-success measurement.

## Reproduce the software smoke check

```bash
python3 scripts/smoke_training.py --output /tmp/parcel-model-smoke
```

Choose a new output directory. This creates synthetic files, trains tiny ACT and
DP models, reloads each checkpoint and requests three actions without opening
hardware. It writes logs and `results.json`; the checkpoints are not usable
production policies.
