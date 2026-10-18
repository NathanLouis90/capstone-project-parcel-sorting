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

Run the following block in a **Bash terminal**, from the repository root with `Xtrainer` activated. It defines terminal variables for the commands below; do not paste it into a Python file or `scripts_config.py`.

Before pasting it, replace the example folder names in `PROJECTS` with your actual converted project folders, each containing `train_data/`. Add or remove folders as needed. Replace `your_dataset_name` with a name for the combined dataset. The last three lines build the output paths automatically:

```bash
RECIPE="policy_A_unified"
PROJECTS=("datasets/your_recording_folder" "datasets/another_recording_folder")
DATASET_NAME="your_dataset_name"
DATASET="datasets/training/${DATASET_NAME}.hdf5"
SPLIT_FILE="datasets/training/${DATASET_NAME}.split.json"
CONFIG_DIR="ckpt/${DATASET_NAME}_configs"
```

For B, change the first line to `RECIPE="policy_B_conditioned"` and list B projects from both bins. Run this variable block first, then the conversion command in the **same terminal**. It only sets variables; it does not convert data or start training. Run the block again in a new terminal, or after changing `DATASET_NAME` so its derived paths update.

The variable names are shortcuts, not required Python settings. This table shows what the commands need:

| Variable | Meaning | Needed when? |
| --- | --- | --- |
| `RECIPE` | Which task's recordings and inputs to select | Required by conversion as `--recipe` |
| `PROJECTS` | Existing converted project folders; one or more entries are allowed | Set this to choose your inputs. `--projects` is optional; omitting it selects all registered projects. |
| `DATASET_NAME` | A label used to build the output paths | Optional convenience; it is not a script argument |
| `DATASET` | Output `.hdf5` training file to create | Required by conversion as `--output`; used again for training setup |
| `SPLIT_FILE` | Output `.json` file listing training and validation episodes | Required as `--split-file` for conversion and training setup; generated automatically |
| `CONFIG_DIR` | Folder for generated training configurations and model runs | Needed later as `--output-dir`; not used by conversion |

## 3. Convert and reserve validation episodes

After running the variable block, paste this command into that same terminal. `$RECIPE`, `${PROJECTS[@]}`, `$DATASET` and `$SPLIT_FILE` use the values you set above:

```bash
python3 scripts/convert_to_robomimic.py \
  --recipe "$RECIPE" --projects "${PROJECTS[@]}" \
  --output "$DATASET" --split-file "$SPLIT_FILE"
```

You can also write values directly in the command, without setting variables. For an A dataset from one project, replace the example folder and output names, then run this Bash block:

```bash
python3 scripts/convert_to_robomimic.py \
  --recipe policy_A_unified --projects datasets/your_recording_folder \
  --output datasets/training/your_dataset_name.hdf5 \
  --split-file datasets/training/your_dataset_name.split.json
```

Run only one of these conversion commands. Later variable-based commands still need their variables set.

If every file is skipped as "not accepted", use the [review tool](dataset_preparation.md#review-all-episodes-with-one-command) to record your decisions and synchronize the existing HDF5 files. Merely creating HDF5 files does not mark episodes accepted.

The converter combines accepted episodes, turns compressed camera images into RGB images, and keeps the joint states and demonstrated actions. B's bin input stays constant throughout an episode: `[1, 0]` for bin 0 or `[0, 1]` for bin 1. It refuses a conditioned-B dataset with only one bin.

A **split** divides accepted recordings into two groups:

- **Training episodes:** the model learns its actions from these recordings.
- **Validation episodes:** the model predicts actions on these reserved recordings, and training reports how closely they match the recorded actions. They are not used for training updates.

For example, 25 accepted, independent poly-mailer A recordings at an 80/20 split give 20 training episodes and 5 validation episodes. A “25-recording model” therefore does not necessarily train on all 25. Validation measures prediction error; real-robot task success still needs separate trials.

The converter creates the split file automatically. You choose its filename, not the episode lists. ACT and DP use that same file so one algorithm is not checked on a different set of recordings. Keep it with the dataset and model configuration; do not edit its lists manually.

The default training fraction is `ROBOMIMIC["train_fraction"] = 0.8` in `scripts/scripts_config.py`. Each parcel type appears in both groups; B also represents each parcel-type/bin combination. Each combination needs at least two independent parcel cycles before splitting. Recordings linked to one cycle stay together, so actual counts can differ from an exact 80/20 ratio. Change the fraction before converting to a new dataset. Dobot ACT uses its separate per-project `train_ratio` setting.

Use a new `DATASET_NAME` when changing the included recordings. Existing datasets are not replaced, and reusing a split with changed source files is refused. A warning about missing parcel types means the dataset covers only an early, partial test.

## 4. Generate configurations and train

Run this block in the same Bash terminal where you set `DATASET`, `SPLIT_FILE`, `CONFIG_DIR` and `RECIPE`. The first command writes configuration files; the next two train ACT and DP:

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

To check installation and data handling with two training updates, run this block in the same Bash terminal. Its first line sets `SMOKE_DIR`, then the commands create and train smaller models in that directory:

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

This check applies only to `policy_B_conditioned`. Replace the example checkpoint path with a saved `.pth` from either trained algorithm, then run the whole block in the same Bash terminal. The first line sets `CHECKPOINT`; the next command performs the check:

```bash
CHECKPOINT="ckpt/path_to_your_saved_checkpoint.pth"
python3 scripts/check_destination_swap.py \
  --checkpoint "$CHECKPOINT" --dataset "$DATASET" \
  --output "ckpt/${DATASET_NAME}_bin_check.json"
```

The script runs validation episodes twice with the same images and joint states. One run uses the recorded bin; the other changes only the bin input. It reports how much the predicted right-arm joint angles change. Little change suggests the model may be ignoring the bin input. A large change does not prove correct placement; physical testing is still required once robot deployment is available.

Add `--cpu` if needed. Use `--max-episodes` and `--max-steps` to limit the check. Defaults and the warning threshold are in `ROBOMIMIC`.
