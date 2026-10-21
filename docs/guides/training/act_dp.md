# Train matched ACT and Diffusion Policy models

Complete [recording](../recording/protocol.md) and
[dataset preparation](../datasets/preparation.md). Stop the recorder. Prepare
[one terminal](../../terminal_commands.md) with Python 3.8 `Xtrainer` activated
and the complete training dependencies installed. No robot server is needed.

Read the [training README](README.md) for algorithms, options, dataset selection,
frozen splits, and checkpoint formats. Train a separate ACT/DP pair per medium.

## 1. Build a dataset and freeze its split

Set the medium and select a prepared collection:

```bash
MEDIUM=poly_mailer
python3 scripts/convert_to_robomimic.py --recipe "$MEDIUM" \
  --projects "datasets/${MEDIUM}_bottom" \
  --output "datasets/training/$MEDIUM.hdf5" \
  --split-file "datasets/training/$MEDIUM.split.json"
```

1. Keep `MEDIUM` set in this terminal. Use `envelope` or `carton` for another medium.
2. Replace the `--projects` value with the prepared folders you want to include.
   Keep one medium per recipe. For a rebuilt project, use its actual folder,
   such as `--projects datasets/poly_mailer_v2`, with `--recipe poly_mailer`.
3. Choose unused output filenames for a new snapshot. Include at least two
   independent accepted cycles and keep rollout inclusion off for demonstrations.
4. To combine top and bottom mailers, use this alternative command after
   preparing both projects:

```bash
python3 scripts/convert_to_robomimic.py --recipe poly_mailer \
  --projects datasets/poly_mailer_top datasets/poly_mailer_bottom \
  --output datasets/training/poly_mailer_top_bottom.hdf5 \
  --split-file datasets/training/poly_mailer_top_bottom.split.json
```

For cartons, list the desired `carton_top`, `carton_bottom`, `carton_front`, and
`carton_rear` project paths. Existing medium-only folders can also be selected.
Use your chosen dataset and split paths together in step 2; replace both paths
there if you used the combined example.

## 2. Generate the two training configurations

Edit shared defaults in `scripts/scripts_config.py` before generating configs
if you need different experiment settings. For the first example above, run:

```bash
python3 scripts/configure_robomimic.py \
  --dataset "datasets/training/$MEDIUM.hdf5" \
  --split-file "datasets/training/$MEDIUM.split.json" \
  --output-dir "ckpt/${MEDIUM}_configs"
```

Check for `${MEDIUM}_act.json` and `${MEDIUM}_diffusion_policy.json` under the
output directory. Keep both configurations on the same frozen split.

## 3. Train ACT, then Diffusion Policy

Run the second command after the first training run finishes:

```bash
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "ckpt/${MEDIUM}_configs/${MEDIUM}_act.json"
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "ckpt/${MEDIUM}_configs/${MEDIUM}_diffusion_policy.json"
```

Train both from scratch. Keep the split unchanged. Find timestamped runs under
`ckpt/${MEDIUM}_configs/runs/` and select a saved `.pth` from a run's `models/`
directory for [checkpoint checks and physical evaluation](../runtime/evaluation.md).
Use separate held-out physical placements to compare success and cycle time.

## Small configuration checks

To generate small CPU configurations from your prepared dataset, run:

```bash
python3 scripts/configure_robomimic.py \
  --dataset "datasets/training/$MEDIUM.hdf5" \
  --split-file "datasets/training/$MEDIUM.split.json" \
  --output-dir "ckpt/${MEDIUM}_smoke_configs" --smoke --cpu
```

Check the generated `${MEDIUM}_act_smoke.json` and
`${MEDIUM}_diffusion_policy_smoke.json` files. To train them, use step 3's commands
with these filenames and the smoke configuration directory. Keep outputs separate
from full runs. Never use smoke checkpoints on live hardware.

## Reproduce the software smoke check

For a complete synthetic check without recorded datasets, choose a new output
folder and run:

```bash
python3 scripts/smoke_training.py --output /tmp/parcel-model-smoke
```

Read the logs and `results.json` under the output folder. Use another folder for
another run. Do not use these synthetic checkpoints for physical policies.
