# ACT and Diffusion Policy training with robomimic

Use this route to compare ACT and Diffusion Policy, or to train one Policy B model that takes the chosen bin as an input. Both algorithms use the same camera images and joint states. Joint values are scaled in the same way, and the same recordings are reserved for validation instead of training.

These models can currently be checked with recorded data only. To train a model that can run the robot now, use [Dobot ACT training](act_training.md). Start with the [Policy A](policy_a.md) or [Policy B](policy_b.md) guide to record and [prepare your data](dataset_preparation.md).

## 1. Set up training

Run from the repository root in Python 3.8 `Xtrainer`:

```bash
python3 -m pip install -r requirements-robomimic.txt
python3 -m pip install --no-deps -e robomimic-r2d2
python3 -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

Use a working NVIDIA driver for GPU training. Small CPU checks are available below. Stop the recorder before training; these commands do not need the robot server or scanner.

## 2. Choose which projects to combine

A **recipe** selects the recordings and model inputs:

| Recipe | What it trains |
| --- | --- |
| `policy_A_unified` | One A model from the chosen A projects, across parcel types |
| `policy_B_conditioned` | One B model from both bins; the chosen bin is an extra model input |
| `policy_A_poly_mailer`, `policy_A_carton`, `policy_A_envelope` | Optional A comparisons using just one parcel type |
| `policy_B_bin_0`, `policy_B_bin_1` | Optional B comparisons using only one bin, without a bin input |

For final A, include poly mailer, carton and envelope projects. You can start with poly mailers only, but that only tests poly mailers. For B, include both bins for each parcel type and aim for similar episode counts in each bin.

Replace the values in this block. `PROJECTS` contains converted project folders, each with `train_data/`; add or remove entries as needed:

```bash
RECIPE="policy_A_unified"
PROJECTS=("datasets/your_recording_folder" "datasets/another_recording_folder")
DATASET_NAME="your_dataset_name"
DATASET="datasets/training/${DATASET_NAME}.hdf5"
SPLIT_FILE="datasets/training/${DATASET_NAME}.split.json"
CONFIG_DIR="ckpt/${DATASET_NAME}_configs"
```

For B, choose `RECIPE="policy_B_conditioned"` and list B projects from both bins. These variables are examples, not configured project names. Keep them in the same terminal or set them again before later commands.

## 3. Convert and reserve validation episodes

```bash
python3 scripts/convert_to_robomimic.py \
  --recipe "$RECIPE" --projects "${PROJECTS[@]}" \
  --output "$DATASET" --split-file "$SPLIT_FILE"
```

The converter combines accepted episodes, turns compressed camera images into RGB images, and keeps the joint states and demonstrated actions. B's bin input stays constant throughout an episode: `[1, 0]` for bin 0 or `[0, 1]` for bin 1. It refuses a conditioned-B dataset with only one bin.

The split file records exactly which episodes train the models and which validate them. Both algorithms use that same list. By default, approximately 80% are used for training and 20% for validation, with each parcel type represented in both groups. B also keeps each parcel-type/bin combination represented. Each group needs at least two independent parcel cycles; recordings linked to the same cycle stay together.

Use a new `DATASET_NAME` when changing the included recordings. Existing datasets are not replaced, and reusing a split with changed source files is refused. A warning about missing parcel types means the dataset covers only an early, partial test.

## 4. Generate configurations and train

```bash
python3 scripts/configure_robomimic.py \
  --dataset "$DATASET" --split-file "$SPLIT_FILE" --output-dir "$CONFIG_DIR"

PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "$CONFIG_DIR/${RECIPE}_act.json"
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "$CONFIG_DIR/${RECIPE}_diffusion_policy.json"
```

Run one model at a time if GPU memory is limited. Conversion, image size, training settings and evaluation thresholds are in `ROBOMIMIC` in `scripts/scripts_config.py`. Change those settings before generating configs; use fresh output directories for new comparisons.

The configs select all three cameras and joint positions. Conditioned B adds the destination input. Validation uses scaling values measured from the training recordings, so validation data does not influence them.

Check for `finished run successfully!`, finite training/validation losses, and saved `.pth` files under `<config-dir>/runs/<experiment>/<timestamp>/models/`. Keep the dataset, split and config with the checkpoint. The trainer asks before replacing an existing run; use a fresh directory or a fresh `--name` on retry.

To check installation and data handling with two training updates, generate smaller models in a new directory:

```bash
SMOKE_DIR="ckpt/${DATASET_NAME}_installation_check"
python3 scripts/configure_robomimic.py \
  --dataset "$DATASET" --split-file "$SPLIT_FILE" \
  --output-dir "$SMOKE_DIR" --smoke --cpu
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "$SMOKE_DIR/${RECIPE}_act_smoke.json"
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config "$SMOKE_DIR/${RECIPE}_diffusion_policy_smoke.json"
```

These reduced models only check that the pipeline runs. They are not task-performance results. Normal ACT training may download pretrained image-model weights on first use.

## 5. Check whether B uses the requested bin

This check applies only to `policy_B_conditioned`. Choose a saved `.pth` from either trained algorithm:

```bash
CHECKPOINT="ckpt/path_to_your_saved_checkpoint.pth"
python3 scripts/check_destination_swap.py \
  --checkpoint "$CHECKPOINT" --dataset "$DATASET" \
  --output "ckpt/${DATASET_NAME}_bin_check.json"
```

The script runs validation episodes twice with the same images and joint states. One run uses the recorded bin; the other changes only the bin input. It reports how much the predicted right-arm joint angles change. Little change suggests the model may be ignoring the bin input. A large change does not prove correct placement; physical testing is still required once robot deployment is available.

Add `--cpu` if needed. Use `--max-episodes` and `--max-steps` to limit the check. Defaults and the warning threshold are in `ROBOMIMIC`.
