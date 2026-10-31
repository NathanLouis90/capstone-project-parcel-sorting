# Repository Guidelines

## Project Structure

This repository automates parcel sorting with a dual-arm Dobot X-Trainer using ACT and Diffusion Policy (robomimic).

- Entrypoints by workflow stage: `setup/` (ports, leaders, offsets, cameras, labels, scanner, waypoints), `robot/` (server, homing), `recording/` (teleoperate, record, review), `training/` (menu), `evaluation/` (cycles, checkpoint check), `tools/` (dataset utilities, motion simulation).
- `parcel_sorting/`: the library. `safety/` (kinematics, limits, handoff; pure numpy) and `scanning/` are the lowest layer; `hardware/`, `policies/` and `data/` build on them; `runtime/` and `training/` are on top. Imports point downward only; nothing imports from the stage folders.
- Extension points: new media are `MEDIA` entries in `config/settings.py` (no code lists media); new policy types (e.g. a VLA) implement `Policy` and register in `POLICY_LOADERS` (`parcel_sorting/policies/interface.py`); new task flows reuse the `Cycle` skills (`pick`, `scan`, `place`) and always command the robot through `MotionLoop`. See `docs/reference/architecture.md#extending-the-system`.
- `config/settings.py`: every editable setting. Local, ignored files: `config/dobot_settings.ini`, `config/waypoints.local.yaml`.
- `robomimic-r2d2/`: ACT/DP training stack. `third_party/`: ACT model, Dynamixel and Feetech SDKs.
- `tests/`: hardware-free regression tests. `docs/procedures/`: step-by-step instructions. `docs/reference/`: explanations.
- `datasets/`, `ckpt/`, `cycle_logs/`, `logs/`, `output/`: ignored local data.

## Build, Test, and Development Commands

Run from the repository root with `conda activate Xtrainer` (Python 3.8.10). Follow `docs/procedures/01_install.md`; the repository is installed with `python3 -m pip install --no-deps -e .`, so no `PYTHONPATH` is needed.

- `python3 -m pytest`: run the regression suite.
- `python3 evaluation/run_cycle.py --medium poly_mailer --dry-run --fake-token DEST-A-S138683 --csv /tmp/cycle.csv`: simulate one cycle.
- `python3 evaluation/check_checkpoint.py --medium poly_mailer --checkpoint ckpt/MODEL/best.pth`: load a checkpoint without hardware.
- `python3 training/train_models.py`: dataset and training menu.
- `python3 robot/launch_nodes.py`: start the hardware server (moves grippers; only after setup).

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions/modules, `PascalCase` classes, and `UPPER_SNAKE_CASE` constants. Preserve surrounding style and Python 3.8 compatibility. Keep hardware access separate from validation and dataset logic. New settings go in `config/settings.py`, in the section for the program that reads them. Entry scripts stay thin when their logic is shared or tested; put that logic in `parcel_sorting/`. Do not add `sys.path` manipulation. No formatter or linter is configured.

## Documentation

Procedures (`docs/procedures/`) are copy-paste instructions: numbered steps, one command block and one `Expect:` line each, no background. Explanations, option tables and design reasons go in `docs/reference/`. Update both when behaviour or commands change.

## Testing Guidelines

Tests use pytest; name files `tests/test_*.py` and functions `test_*`. Use temporary directories, synthetic recordings, and mocked hardware. Add regression coverage for changed safety, metadata, conversion, and checkpoint behaviour. Programs that move the robot are procedures in `setup/` or `evaluation/`, never tests.

## Commit & Pull Request Guidelines

Recent commits use imperative, descriptive subjects such as "Reject nonfinite policy outputs before gripper clipping." Keep changes focused. PRs should explain behaviour changes, list validation commands/results, link relevant issues, and document configuration or dataset impacts.

## Configuration & Robot Safety

Copy `config/dobot_settings.example.ini` to `config/dobot_settings.ini`; preserve existing calibration. Never commit credentials, recordings, or checkpoints. Robot server startup cycles both grippers and recorder startup homes both followers. Perform motion checks with clear arm paths and immediate emergency-stop access. Do not add per-step work to the live 25 Hz control loop.
