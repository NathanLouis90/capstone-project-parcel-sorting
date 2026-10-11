# ACT training for the first poly-mailer dataset

Train three separate models: Policy A, Policy B for bin 0, and Policy B for bin 1. Each project contains 25 recorded episodes. The current ACT loader does not use the destination observation, so the two Policy B destinations remain separate tasks.

The current 75 recordings were converted and verified on 11 October 2026. Each project now has 25 HDF5 files and 25 readable review videos. For these recordings, start with the environment check and then the training commands. A CPU forward/backward compatibility check passed on a converted episode; that check did not launch full GPU training. Existing local checkpoints may come from later workstation runs; use a fresh output directory when retraining.

## Prepare the environment

Use the existing Python 3.8 `Xtrainer` environment. Some vendor modules are supplied only as Python 3.8 bytecode and will not import in a different Python version.

```bash
conda activate Xtrainer
cd /home/adiel/dobot_xtrainer
nvidia-smi
python3 -c "import torch; print(torch.__version__); print('CUDA available:', torch.cuda.is_available())"
```

Training requires `CUDA available: True` because the vendor trainer uses CUDA directly. The workstation has an NVIDIA RTX 4500 Ada GPU with approximately 24 GB of memory. GPU devices are hidden inside the Codex filesystem sandbox; run training from the workstation terminal.

Conversion and training are offline operations. Neither requires the robot server, recorder, or scanner reader. Finish any active recording before conversion.

## Configure dataset projects

Edit `scripts/scripts_config.py` rather than the helper scripts. `COUNT_EPISODES["root_dir"]` controls the counter's default dataset root. `PREPARE_ACT_DATASETS["root_dir"]` controls both the preparation helper and the corresponding ACT training task paths.

Each entry in `PREPARE_ACT_DATASETS["projects"]` defines a project folder name, `policy_stage`, `medium`, `bin_index`, `episode_len`, `train_ratio`, and `camera_names`. `ModelTrain/constants.py` reads these entries automatically. To add carton recordings, add entries with `medium="carton"` and their actual dataset folder names. Use `bin_index=None` for Policy A and the demonstrated destination index for Policy B.

The current defaults remain the three poly-mailer projects, a 400-step episode length, an 80/20 split, and three cameras. Restart the helper or trainer after editing configuration. A helper's `--root` override applies only to that invocation; update the configured root as well before training elsewhere.

Recording defaults, including project name, policy stage, medium, barcode capture, and demonstrated bin, are in `experiments/experiments_config.py` under `RUN_CONTROL`. Recording CLI flags override those defaults. Scanner settings and the metadata filename remain in `barcode_scanning/barcode_scanning_config.py`; the counter now uses the same metadata filename as the recorder.

## Validate and convert

```bash
python3 scripts/prepare_act_datasets.py
python3 scripts/prepare_act_datasets.py --convert
```

The first command validates completed metadata and matching frame identifiers. The second converts all three projects into `train_data/episode_init_0.hdf5` through `episode_init_24.hdf5` and creates review videos in `output_videos/`. It refuses to overwrite existing HDF5 outputs. Once the conversion is complete, proceed to training instead of running conversion again.

Conversion logs are stored in each project's `conversion_logs/` folder. The converter rejects mismatched frames instead of deleting raw recording files. These checks do not establish physical task success; review the videos and exclude failed grasping, staging, or placement demonstrations before a production training run.

The task entries generated in `ModelTrain/constants.py` use these projects:

| Task | Maximum recorded frames | Configured episode length | Split |
| --- | ---: | ---: | --- |
| `first_set_poly_mailer_A` | 324 | 400 | 20 training, 5 validation episodes |
| `first_set_poly_mailer_B_bin_0` | 279 | 400 | 20 training, 5 validation episodes |
| `first_set_poly_mailer_B_bin_1` | 256 | 400 | 20 training, 5 validation episodes |

The 400-step setting is a rollout horizon, not automatic task-completion detection. The loader supports variable recording lengths. Keep all three camera inputs for this initial baseline. No crop or mask is applied by this setup.

## Train one model at a time

The following settings are an initial baseline using the installed trainer's default learning rate and chunk size, with batch size reduced to 8. Training uses all 14 arm/gripper state values. The loader adds two zero base-action dimensions internally, so its 16-dimensional action head is expected.

Policy A:

```bash
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name first_set_poly_mailer_A \
  --ckpt_dir /home/adiel/dobot_xtrainer/ckpt/act_poly_mailer_A \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

Policy B, bin 0:

```bash
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name first_set_poly_mailer_B_bin_0 \
  --ckpt_dir /home/adiel/dobot_xtrainer/ckpt/act_poly_mailer_B_bin_0 \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

Policy B, bin 1:

```bash
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name first_set_poly_mailer_B_bin_1 \
  --ckpt_dir /home/adiel/dobot_xtrainer/ckpt/act_poly_mailer_B_bin_1 \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

Wait for each run to finish before starting the next. Each command uses optimizer steps, not epochs. The first model construction may download ImageNet ResNet18 weights. If GPU memory runs out, retry in a new checkpoint directory with `--batch_size 4`.

The trainer prints the dataset split, validation loss, and step progress. It saves `config.pkl`, `dataset_stats.pkl`, periodic checkpoints, `policy_last.ckpt`, `policy_best.ckpt`, and loss plots. Keep the configuration and normalization statistics with their matching checkpoint. Use a fresh checkpoint directory for a new experiment because the trainer can overwrite files in a reused directory.

## Evaluate separately

A low validation loss does not establish task success, especially when training images show hands or leader arms that will be absent during inference. Evaluate each policy with the intended camera framing and starting pose.

Do not launch `experiments/run_inference.py` solely to inspect a checkpoint: it commands real robots and currently commands both arms. A left-only deployment must keep the unused follower parked and ignore its predicted commands. This training setup does not implement autonomous A/B handoff or left-only inference.
