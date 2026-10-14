# ACT and Diffusion Policy with robomimic-r2d2

The main comparison uses one unified A policy across envelopes, poly mailers and cartons, and one destination-conditioned B policy across all media and both bins. Both algorithms use the bundled robomimic loader, the same images/qpos, training statistics and frozen episode split. The vendor ACT trainer is retained for shakedown runs; its B models must use separate bins because its loader ignores destination.

## Environment

Run from the repository root in Python 3.8 `Xtrainer`. The separate training requirements pin versions exercised by the CPU integration checks. Install CUDA 11.8 PyTorch wheels first if training on a working NVIDIA driver:

```bash
conda activate Xtrainer
python3 -m pip install torch==2.0.1 torchvision==0.15.2 --index-url https://download.pytorch.org/whl/cu118
python3 -m pip install -r requirements-robomimic.txt
python3 -m pip install --no-deps -e robomimic-r2d2
python3 -c "import torch, diffusers, robomimic; print(torch.__version__, diffusers.__version__, robomimic.__file__); print('CUDA:', torch.cuda.is_available())"
python3 -m pytest -q tests
```

ACT's `robomimic` branch DETR backend is included under `third_party/act`, with its license and revision. It accepts the algorithm's device and disables pretrained downloads for smoke runs. Final ACT configurations use ImageNet pretrained weights, which may download on first construction. Diffusion Policy uses the configured visual encoder. Language observations are not used; CLIP is loaded only when a language key is requested.

The integration checks used Python 3.8.10, torch 2.0.1+cu118, torchvision 0.15.2+cu118, diffusers 0.11.1 and huggingface-hub 0.25.2. CPU smoke tests do not establish GPU installation or full-training performance. A working NVIDIA driver is required for CUDA; `nvidia-smi` and `torch.cuda.is_available()` should both succeed before a GPU run. Version compatibility was also checked against [Diffusers package metadata](https://pypi.org/project/diffusers/0.11.1/) and the [ACT robomimic branch](https://github.com/tonyzhaozh/act/tree/robomimic).

## Review and vendor-format conversion

Keep recording commands unchanged. Register each project in `PREPARE_ACT_DATASETS["projects"]` in `scripts/scripts_config.py`. A projects have a medium and stage A; B projects have a medium, stage B and explicit bin. Set `episode_len` per project, increasing envelope A's limit only when its accepted demonstrations require it.

```bash
python3 scripts/prepare_act_datasets.py --dataset-name first_set_poly_mailer_A
python3 scripts/prepare_act_datasets.py \
  --review-episode datasets/first_set_poly_mailer_A/collect_data/<episode> \
  --review-status accepted
python3 scripts/prepare_act_datasets.py --dataset-name first_set_poly_mailer_A --convert
```

Replace `<episode>` with the actual folder ID; repeat review and conversion for each project. Review raw camera sequences or existing review videos first. Mark failures `rejected`. `--convert` skips unreviewed and rejected episodes. The low-level legacy converter remains available, but it does not replace this review gate. If old HDF5 metadata still says unreviewed, marking the raw episode does not update the HDF5: rebuild into a fresh output project, preserving raw data. Do not use stale files after rejecting an episode. Robomimic conversion also checks the current raw review status when the raw episode is available.

Preparation reports `frame_count / (ended_at - started_at)`, warns outside 10% of the shared 25 Hz target, and reports recorded overruns. Older fast-loop data may fail this rate check and needs review/recollection. It also warns on start/end home drift, idle-arm movement/open grippers and inference J3/J4 violations, including right J4 at or above 0.6 rad. These checks are advisory; invalid metadata and episodes longer than their configured limit remain hard failures.

## Named recipes and shared conversion

`ROBOMIMIC` in `scripts/scripts_config.py` contains conversion, training and evaluation settings.

| Recipe | Selected episodes | Destination input |
| --- | --- | --- |
| `policy_A_unified` | A across all media/projects | No |
| `policy_B_conditioned` | B across all media/projects and both bins | Yes |
| `policy_A_envelope`, `policy_A_poly_mailer`, `policy_A_carton` | One A medium, O6 ablation | No |
| `policy_B_bin_0`, `policy_B_bin_1` | One B bin across media, specialist baseline | No |

The converter reads `<project>/train_data/episode_init_*.hdf5` from multiple projects. Vendor files contain 14-D qpos/actions and padded JPEG byte rows. Output contains `data/demo_i/obs/{qpos,top,left_wrist,right_wrist}`, optional `destination`, 14-D `actions`, per-demo `num_samples`, total samples and episode provenance attributes. Images become RGB uint8 HWC, resized identically to the configured 128 × 128 pixels. B destination is checked against the recorded bin and held constant for the episode.

After registering and converting the named projects:

```bash
python3 scripts/convert_to_robomimic.py \
  --recipe policy_A_unified \
  --projects datasets/first_set_poly_mailer_A datasets/first_set_carton_A datasets/first_set_envelope_A \
  --output datasets/robomimic/policy_A_unified.hdf5 \
  --split-file datasets/robomimic/policy_A_unified.split.json

python3 scripts/convert_to_robomimic.py \
  --recipe policy_B_conditioned \
  --projects datasets/first_set_poly_mailer_B_bin_0 datasets/first_set_poly_mailer_B_bin_1 \
    datasets/first_set_carton_B_bin_0 datasets/first_set_carton_B_bin_1 \
    datasets/first_set_envelope_B_bin_0 datasets/first_set_envelope_B_bin_1 \
  --output datasets/robomimic/policy_B_conditioned.hdf5 \
  --split-file datasets/robomimic/policy_B_conditioned.split.json
```

Add later collection projects to the same `--projects` list. Omitting `--projects` selects all configured projects and filters them through the recipe. Conditioned B refuses one-bin data, reports counts per medium × bin and warns on imbalance. Missing media cause a partial-shakedown warning, not a claim that the full comparison dataset is complete.

Splits stratify A by medium and B by medium × bin, with the configured 80/20 fraction and seed. Every stratum needs at least two independent cycle IDs so both filters are represented; small strata may differ from 80/20. Repeated cycles stay together. The explicit JSON split records source IDs and SHA-256 checksums and is embedded in HDF5 along with `mask/train` and `mask/valid`. Reusing it with changed source files is refused. Retain dataset, split and configuration together; use fresh output names for a revised dataset.

## Generate matched configurations

The parcel generator lives alongside the upstream `config_gen` scripts and uses their `ConfigGenerator`. It checks the explicit split against the HDF5 masks. ACT and DP share low-dimensional normalization fitted only to training data and action min/max scaling fitted only to training data. Validation uses those same statistics. Images use robomimic RGB processing, not episode mean/std normalization. ACT additionally uses its standard ImageNet normalization.

```bash
python3 scripts/configure_robomimic.py \
  --dataset datasets/robomimic/policy_A_unified.hdf5 \
  --split-file datasets/robomimic/policy_A_unified.split.json \
  --output-dir ckpt/configs_A
python3 scripts/configure_robomimic.py \
  --dataset datasets/robomimic/policy_B_conditioned.hdf5 \
  --split-file datasets/robomimic/policy_B_conditioned.split.json \
  --output-dir ckpt/configs_B
```

This writes `<recipe>_act.json`, `<recipe>_diffusion_policy.json`, matching split sidecars and launch scripts. A uses `qpos` plus the three images. Conditioned B adds `destination` to the low-dimensional keys, yielding a 16-D state and 14-D action. ACT concatenates all configured low-dimensional keys; DP uses the same keys in its observation encoder. B specialist recipes omit destination.

Defaults use action horizon/chunk settings appropriate to each algorithm: ACT predicts 16 actions; DP observes 2 steps and predicts 16, executing 8 actions between queries. The loader's frame stacking and sequence length match those horizons. Rollouts are disabled: training does not connect to a robot or simulation environment.

## Train and smoke-check

```bash
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config ckpt/configs_A/policy_A_unified_act.json
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config ckpt/configs_A/policy_A_unified_diffusion_policy.json
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config ckpt/configs_B/policy_B_conditioned_act.json
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config ckpt/configs_B/policy_B_conditioned_diffusion_policy.json
```

Run one model at a time on limited hardware. Choose fresh output directories or an explicit fresh `--name` on retry; the upstream trainer prompts before overwriting an existing run. Check for `finished run successfully!`, finite training/validation losses and saved `.pth` checkpoints under `<config-dir>/runs/<experiment>/<timestamp>/models/`. Exceptions return a failing process status.

For a two-step integration run, generate reduced smoke configurations into a fresh directory. Omit `--cpu` when testing CUDA:

```bash
python3 scripts/configure_robomimic.py \
  --dataset datasets/robomimic/policy_B_conditioned.hdf5 \
  --split-file datasets/robomimic/policy_B_conditioned.split.json \
  --output-dir ckpt/smoke_B --smoke --cpu
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config ckpt/smoke_B/policy_B_conditioned_act_smoke.json
PYTHONPATH=.:robomimic-r2d2 python3 robomimic-r2d2/robomimic/scripts/train.py \
  --config ckpt/smoke_B/policy_B_conditioned_diffusion_policy_smoke.json
```

Repeat with A. Smoke models have reduced capacity and no ACT pretrained backbone; do not compare their task scores with final models. Hardware-free tests create synthetic vendor files to exercise conversion and split checks. Integration verification covered both recipes and both algorithms for two optimizer steps plus validation on synthetic data; no real parcel-trained checkpoint was supplied.

## Offline destination-swap check

```bash
python3 scripts/check_destination_swap.py \
  --checkpoint ckpt/configs_B/runs/<experiment>/<timestamp>/models/<checkpoint>.pth \
  --dataset datasets/robomimic/policy_B_conditioned.hdf5 \
  --output ckpt/evaluation/destination_swap.json
```

Replace checkpoint placeholders with the actual file. Add `--cpu` for CPU evaluation. The script selects held-out B episodes and checks their split against the checkpoint's training dataset. It resets policy state and uses identical random seeds for true/swapped passes, keeping images and qpos fixed while swapping `[1, 0]` with `[0, 1]`. It reports joint RMSE against held-out actions, right-arm destination-swap RMS, gripper change, predicted motion and average time per step in physical action units. Low swap RMS warns that conditioning may be ignored; sensitivity alone does not prove correct-bin placement. Default limit: 12 episodes and 100 steps; edit config or use `--max-episodes` and `--max-steps`.

Robomimic real-robot deployment is out of scope. Use the [inference and evaluation guide](inference_evaluation.md) for the current vendor deployment path and physical evaluation protocol. The [supervisor design](../parcel_sorting_design_notes.md#supervisor-design-not-yet-implemented) is documentation only.
