# ACT dataset preparation and training

This guide covers the vendor ACT trainer for shakedown runs and specialist baselines. The main comparison trains unified A and destination-conditioned B with both ACT and Diffusion Policy through [robomimic-r2d2](diffusion_policy_training.md). The vendor loader ignores destination observations, so its B-bin models must remain separate. Per-medium A models are the O6 ablation, not the main design.

## 1. Prepare the environment

Run commands from the repository root in the existing Python 3.8 `Xtrainer` environment. Required vendor modules are supplied only as Python 3.8 bytecode.

```bash
conda activate Xtrainer
cd /path/to/capstone-project-parcel-sorting
nvidia-smi
python3 -c "import torch; print(torch.__version__); print('CUDA available:', torch.cuda.is_available())"
```

Training requires `CUDA available: True` because the vendor trainer uses CUDA directly. Counting, conversion and training do not require the robot server, recorder or scanner reader. Finish recording before conversion. The first model construction may download ImageNet ResNet18 weights.

## 2. Register recording projects

Edit [scripts/scripts_config.py](../../scripts/scripts_config.py). `PREPARE_ACT_DATASETS["root_dir"]` is the parent of the recording projects and supplies their ACT training paths. `COUNT_EPISODES["root_dir"]` independently sets the counter's root.

Each key under `PREPARE_ACT_DATASETS["projects"]` must match an existing recording folder. [ModelTrain/constants.py](../../ModelTrain/constants.py) registers that key as an ACT `--task_name` automatically. Recording a folder does not register it for training.

| Setting | Meaning and example |
| --- | --- |
| Project key | Exact folder name, such as `first_set_carton_A` |
| `policy_stage` | `"A"` or `"B"`; must match episode metadata |
| `medium` | `"poly_mailer"`, `"carton"`, or `"envelope"`; must match episode metadata |
| `bin_index` | `None` for A; `0` or `1` for the corresponding B task |
| `episode_len` | Maximum accepted recording frames and inference rollout horizon; default project setting: `400` |
| `train_ratio` | Training fraction for a single-folder task; default project setting: `0.8` |
| `camera_names` | Camera inputs; default: `["top", "left_wrist", "right_wrist"]` |

For example, add this entry inside the `projects` dictionary for a carton A recording:

```python
"first_set_carton_A": {
    "policy_stage": "A",
    "medium": "carton",
    "bin_index": None,
    "episode_len": 400,
    "train_ratio": 0.8,
    "camera_names": ["top", "left_wrist", "right_wrist"],
},
```

Copy it for `first_set_carton_B_bin_0` and `first_set_carton_B_bin_1`, changing `policy_stage` to `"B"` and `bin_index` to `0` and `1`. For envelopes, use names such as `first_set_envelope_A` and `medium="envelope"`; for poly mailers, use `medium="poly_mailer"`. Repeat for another collection set with its actual folder names.

The installed configuration initially contains only the three `first_set_poly_mailer_*` projects. Carton, envelope and later-set examples require registration before use. Restart the helper or trainer after configuration changes. The helper checks `bin_index` only when it is not `None`; keep an explicit destination for every B project.

The loader supports variable recording lengths. Set `episode_len` high enough for the longest accepted recording. It is a rollout horizon, not automatic task-completion detection. For a single folder with 25 episodes, `train_ratio=0.8` gives 20 training and 5 validation episodes.

## 3. Count, validate and convert

The preparation helper uses hyphenated argument names:

| Argument | Default | Purpose |
| --- | --- | --- |
| `--dataset-name NAME` | All configured projects | Validate or convert one registered recording project |
| `--root PATH` | `PREPARE_ACT_DATASETS["root_dir"]` | Override the dataset root for this invocation |
| `--convert` | Off | Write HDF5 files and review videos after validation |
| `-h`, `--help` | — | Show available arguments and registered project names |

Examples after registering the named projects:

```bash
python3 scripts/count_episodes.py

# Validate one project for each medium.
python3 scripts/prepare_act_datasets.py --dataset-name first_set_poly_mailer_A
python3 scripts/prepare_act_datasets.py --dataset-name first_set_carton_B_bin_0
python3 scripts/prepare_act_datasets.py --dataset-name first_set_envelope_B_bin_1

# Convert one selected project after validation.
python3 scripts/prepare_act_datasets.py --dataset-name first_set_carton_B_bin_0 --convert

# Validate every configured project without writing training files.
python3 scripts/prepare_act_datasets.py

# Use a different dataset root for one validation run.
python3 scripts/prepare_act_datasets.py --root /path/to/datasets --dataset-name first_set_envelope_B_bin_1
```

Add `--convert` to the selected project's validation command to convert it. Omitting `--dataset-name` with `--convert` selects every configured project; use that only when all selected projects have unused HDF5 outputs. Existing HDF5 files are refused, not overwritten or skipped. For already-converted projects, validate without `--convert` and proceed to training.

Preparation checks completed metadata, matching frame identifiers and counts, expected stage, medium, destination and recording length. The converter preserves raw files when rejecting mismatches. A counter status of "Complete" means recording ended with a nonzero metadata frame count; it does not establish physical task success.

```text
datasets/<project>/
├── collect_data/<episode_id>/  # Raw frames and episode metadata
├── train_data/                # episode_init_<index>.hdf5, numbered from 0
├── output_videos/             # Review videos
└── conversion_logs/           # Per-episode conversion logs
```

Finish collecting a set before conversion. The helper cannot append to an already-converted project; use a separate project for a later set. Review videos for successful grasping, staging and correct-bin placement before training. If the accepted episode set changes, rebuild its converted outputs in an unused project rather than training on stale HDF5 files.

`--root` does not change training configuration. Before training from another root, update `PREPARE_ACT_DATASETS["root_dir"]` to the same path.

## 4. Choose training arguments

The trainer uses underscore argument names. These are the defaults declared in [ModelTrain/model_train.py](../../ModelTrain/model_train.py); the examples below explicitly select a registered task and batch size 8.

| Argument | CLI default | Purpose |
| --- | --- | --- |
| `--task_name NAME` | `move_cube_new` | Registered ACT task; use the configured recording project name |
| `--ckpt_dir PATH` | `./ckpt/ckpt_move_cube_new` | Output folder for checkpoints, configuration, statistics and plots |
| `--batch_size N` | `16` | Samples per training batch; examples use `8` |
| `--num_steps N` | `30000` | Optimizer steps, not epochs |
| `--lr VALUE` | `2e-5` | Learning rate |
| `--chunk_size N` | `45` | Number of future actions predicted together |
| `--kl_weight N` | `10` | Weight of the ACT latent-variable KL loss |
| `--seed N` | `0` | Random seed |
| `--hidden_dim N` | `512` | Transformer hidden width |
| `--dim_feedforward N` | `3200` | Transformer feedforward width |
| `--validate_every N` | `100` | Validation interval in steps |
| `--save_every N` | `1000` | Periodic checkpoint interval in steps |
| `--resume_ckpt_path PATH` | None | Checkpoint path passed to the vendor trainer for resuming |
| `--skip_mirrored_data` | Off | Request that the loader skip mirrored data |
| `--no_encoder` | Off | Disable the ACT latent encoder |
| `--temporal_agg` | On | Temporal aggregation setting; the CLI has no disable flag |
| `--load_pretrain` | Off | Legacy option marked unused in the entry point; leave unchanged |
| `--eval_every N` | `100` | Legacy option marked unused in the entry point; leave unchanged |
| `-h`, `--help` | — | Show available arguments |

`episode_len`, `train_ratio` and camera inputs are project settings, not trainer CLI arguments. The trainer defaults to the vendor cube task, so always specify your parcel task and checkpoint folder. Use a fresh folder for a new run because reusing one can overwrite outputs.

Training uses all 14 arm/gripper state values. The loader adds two zero base-action dimensions internally, so a 16-dimensional action head is expected. The current setup uses all three cameras without cropping or masking.

## 5. Train one model at a time

These examples use the same initial settings for all three media. Register and convert each named project first; the commands illustrate different tasks, not a complete set of models.

Poly mailer, Policy A:

```bash
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name first_set_poly_mailer_A \
  --ckpt_dir ./ckpt/act_first_set_poly_mailer_A \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

Carton, Policy B bin 0:

```bash
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name first_set_carton_B_bin_0 \
  --ckpt_dir ./ckpt/act_first_set_carton_B_bin_0 \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

Envelope, Policy B bin 1:

```bash
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name first_set_envelope_B_bin_1 \
  --ckpt_dir ./ckpt/act_first_set_envelope_B_bin_1 \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

For vendor shakedown or specialist runs, repeat with the selected A or B-bin task names and distinct checkpoint folders. Replace `first_set` with another registered collection set when needed. Wait for each run to finish before starting the next. If GPU memory runs out, retry in a fresh folder with `--batch_size 4`.

The trainer prints the split, validation loss and step progress. Outputs include `config.pkl`, `dataset_stats.pkl`, periodic checkpoints, `policy_last.ckpt`, `policy_best.ckpt` and loss plots. Keep the configuration and normalization statistics with their matching checkpoint.

## 6. Combine collection sets when needed

Convert both sets first. Preparation registers one folder per task. To train corresponding tasks from two sets together, add entries after the generated project loop in `ModelTrain/constants.py`, before the fixed constants. For example, for cartons:

```python
for suffix in ("A", "B_bin_0", "B_bin_1"):
    TASK_CONFIGS[f"combined_carton_{suffix}"] = {
        "dataset_dir": [
            str(DATASETS_ROOT / f"first_set_carton_{suffix}" / "train_data"),
            str(DATASETS_ROOT / f"second_set_carton_{suffix}" / "train_data"),
        ],
        "episode_len": 400,
        "train_ratio": 0.8,
        "camera_names": ["top", "left_wrist", "right_wrist"],
    }
```

This is a configuration example, not an installed combined task. Use `--task_name combined_carton_A` and a fresh `--ckpt_dir ./ckpt/act_combined_carton_A`; repeat for both B tasks. Replace `carton` with `poly_mailer` or `envelope` for those media. No HDF5 merging or renaming is needed. Keep stages and B destinations separate in this vendor baseline; use the robomimic recipes for unified A and conditioned B.

The vendor multi-folder loader holds out validation only from the first folder. With 25 episodes per folder and `train_ratio=0.8`, two sets give 45 training and 5 validation episodes, not 40/10. Holding out examples from both sets requires another layout or a loader change.

## 7. Evaluate the vendor baseline

Low validation loss does not establish task success. Use the [inference and evaluation guide](inference_evaluation.md) for supervised trials, explicit checkpoint arguments, home checks and per-medium/bin metrics. Vendor inference parks the unused arm for registered tasks; envelope A uses both arms. It has no A/B supervisor or destination-conditioned B input.

For the main comparison, evaluate held-out robomimic episodes using the destination-swap check. Robomimic real-robot inference is out of scope for this pass.
