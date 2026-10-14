# ACT training with the Dobot software

This guide uses `ModelTrain/model_train.py`, the ACT trainer supplied with the Dobot system. Its `.ckpt` models can run the robot through `experiments/run_inference.py`. It is useful for the current poly-mailer test and for checking improvements as you collect more demonstrations.

For ACT versus Diffusion Policy, use the [shared ACT/DP guide](act_dp_training.md). That route trains both algorithms in robomimic. Its `.pth` checkpoints cannot yet run the robot here. The two training routes produce different checkpoint formats; do not interchange them.

## 1. Prepare data and the environment

Follow the [Policy A guide](policy_a.md) or [Policy B guide](policy_b.md) to record, register and prepare a project. Any folder name and collection size are allowed. An optional naming pattern is `<set_id>_<medium>_<policy_stage>`, with `_bin_<number>` added for B.

Run `bash` blocks in a Bash terminal from the repository root in Python 3.8 `Xtrainer`. Replace example values before pasting; keep assignments and commands that use them in the same terminal. Python blocks below are edits to the specified configuration file. The Dobot trainer requires a working GPU:

```bash
conda activate Xtrainer
nvidia-smi
python3 -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

Require `CUDA available: True`. Stop recording before training; training does not need the robot server or scanner. The first run may download pretrained image-model weights.

## 2. Train a registered project

Replace `your_recording_folder` and `your_model_name`, then run the entire block below in the Bash terminal. The first two lines set `TASK` and `CHECKPOINT_DIR`; the Python command uses them. `TASK` must match a registered project or combined task. Use a fresh checkpoint directory for each model:

```bash
TASK="your_recording_folder"
CHECKPOINT_DIR="./ckpt/your_model_name"
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name "$TASK" --ckpt_dir "$CHECKPOINT_DIR" \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

These values are starting settings, not required settings:

| Argument | Meaning |
| --- | --- |
| `--batch_size` | Demonstration samples per training batch; reduce it if GPU memory runs out |
| `--num_steps` | Number of training updates |
| `--lr` | Learning rate |
| `--chunk_size` | Number of future actions predicted at once |
| `--kl_weight` | ACT training setting; leave at `10` for the initial test unless you are tuning the model |
| `--seed` | Random seed; keep it fixed when comparing data sizes |
| `--validate_every`, `--save_every` | How often to check held-out data and save checkpoints |

`episode_len`, camera inputs and `train_ratio` come from the registered task, not this command. Always specify the task and output directory: the trainer's defaults refer to an old cube example. Use `ModelTrain/model_train.py --help` for additional arguments.

Outputs include `policy_best.ckpt`, `policy_last.ckpt`, `config.pkl`, `dataset_stats.pkl` and loss plots. Keep the configuration and statistics with the checkpoint. A low validation loss does not prove physical task success.

## 3. Add more recordings

A **set** is a collection you choose. It need not contain 25 demonstrations. The project's current plan is to compare models after collecting 25, 50, 75 and 100 demonstrations; these are test milestones, not software limits. The current test uses poly mailers only, before adding cartons and envelopes to Policy A.

To combine converted recording folders, edit `ModelTrain/constants.py`. Paste the Python block below after the project-registration loop and before `DT` and `FPS`; do not paste it into the terminal. Replace the source names and combined task name first:

```python
source_names = ["your_recording_folder", "another_recording_folder"]
combined_name = "your_combined_task"
projects = [PREPARE_ACT_DATASETS["projects"][name] for name in source_names]
settings = projects[0]
for project in projects:
    assert all(project[key] == settings[key] for key in
               ("policy_stage", "medium", "bin_index", "camera_names"))
TASK_CONFIGS[combined_name] = {
    "dataset_dir": [str(DATASETS_ROOT / name / "train_data") for name in source_names],
    "episode_len": max(project["episode_len"] for project in projects),
    "train_ratio": settings["train_ratio"],
    "camera_names": list(settings["camera_names"]),
    "policy_stage": settings["policy_stage"],
    "medium": settings["medium"],
    "bin_index": settings["bin_index"],
}
```

Each source must already be registered and converted. This example combines the same task and parcel type; for B it also requires the same bin. The task details let inference choose the correct arm. Add as many source folder names as needed; there is no two-set limit. Source files do not need merging or renaming.

Set `TASK` to your combined name, choose a new `CHECKPOINT_DIR`, and repeat the training command. Use those same values for inference. Train each data-size comparison from scratch with matching settings; resuming an earlier model changes both data size and training history.

The Dobot multi-folder loader reserves validation episodes only from the first listed folder. For example, if two folders each have 25 accepted recordings and `train_ratio=0.8`, it uses 45 for training and 5 for validation. Keeping the same first folder keeps that validation set consistent across cumulative runs. Label results with both the accepted-recording count and the actual training/validation counts printed by the trainer; rejected episodes can reduce the totals.

## 4. Evaluate on the robot

Follow [inference and evaluation](inference_evaluation.md). Stay at the robot during testing and record successes, failures and any manual help.

For B, this trainer does not read the destination input. Train and select a separate checkpoint for each bin. Use robomimic when you need one B model that takes the chosen bin as an input. For the eventual A model across all three parcel types, follow the `policy_A_unified` workflow in the shared guide.
