# Repository tests

The tests check the current per-medium pick-to-scan workflow. They use temporary
recordings, synthetic images, fake clocks, and mocked controllers. They do not
connect to robots, cameras, or scanner devices, and do not require real datasets
or trained checkpoints. They cannot verify physical clearance or grasp success.

## Prepare the environment

Complete the [repository setup](../README.md#software-setup), including the
Python 3.8 `Xtrainer` environment, pinned training dependencies, and editable
packages. Base `requirements.txt` alone is insufficient. Tests that exercise
model adapters import PyTorch and bundled robomimic; they do not train full models.

```bash
conda activate Xtrainer
cd /home/adiel/dobot_xtrainer
```

`conda activate` selects the project's Python environment. `cd` enters the
checkout; replace this path if yours is elsewhere. No robot server is needed.

## Run the suite

```bash
PYTHONPATH=.:robomimic-r2d2 python3 -m pytest tests/ -q
```

| Command part | Meaning |
| --- | --- |
| `PYTHONPATH=.:robomimic-r2d2` | Make the repository and bundled robomimic package importable for this command. |
| `python3 -m pytest` | Run pytest using the activated environment's Python. It discovers both pytest functions and `unittest.TestCase` tests. |
| `tests/` | Limit discovery to the maintained repository suite. Running discovery over the whole checkout can include vendor and hardware scripts. |
| `-q` | Print concise progress and the final result. Exit status 0 means the selected tests passed. |

## Run selected checks

Run a file, one test, or tests whose names match a topic:

```bash
PYTHONPATH=.:robomimic-r2d2 python3 -m pytest tests/test_medium_recording.py -v
PYTHONPATH=.:robomimic-r2d2 python3 -m pytest tests/test_cycle.py::test_retry_has_new_id_and_stops_after_second_failure -v
PYTHONPATH=.:robomimic-r2d2 python3 -m pytest tests/ -k 'no_read or fault' -q
```

A file path selects that module; `::test_name` selects one test inside it.
`-v` prints each test name and result. `-k 'no_read or fault'` selects names
matching either term; quotes keep the expression together. Add `-x` to stop
after the first failure, or `--collect-only -q` to list selected tests without
running them. A parametrized test appears once for each input case.

## What each file checks

| File | Coverage |
| --- | --- |
| `test_medium_recording.py` | Schema-3 metadata, allowed label faces, required filenames, and HDF5 provenance without scanner observations. |
| `test_preparation_review.py` | Accepted-only conversion, required raw metadata, persisted review decisions, and skipping rejected incomplete episodes. |
| `test_episode_review.py` | Raw/HDF5 review synchronization, payload preservation, review controls, and failed-update handling. |
| `test_dataset_curation.py` | Quarantine/restore, transfer/top-up/merge, rate and identity checks, hashes, rollback, and fresh rebuilds. |
| `test_medium_conversion.py` | RGB conversion, frozen splits, supported metadata, and matched ACT/DP configuration generation. |
| `test_barcode_scanner.py` | Keyboard decoding, scan-window freshness, mapped tokens, device cleanup, and recorder button toggling. |
| `test_inference_safety.py` | Finite actions, joint increments, gripper handling, workspace checks, and loop pacing. |
| `test_act_checkpoint.py` | Vendor checkpoint paths, required files, saved configuration, and model-builder overrides. |
| `test_policy_adapter.py` | ACT inputs, DP frame history, medium checks, idle-arm parking, warmup, and reset behavior. |
| `test_handoff.py` | Scan-pose position/orientation, closed grippers, idle-arm home, and settling time. |
| `test_scripted_motion.py` | 25 Hz interpolation, cable limits, feedback divergence, halting, and commissioned waypoints. |
| `test_cycle.py` | Operator outcomes, no-read return, one linked retry, token isolation, cycle logs, and fault stopping. |
| `test_robot_home.py` | Read-only inspection, recovery, homing, and bounded withdrawal using fake controllers. |

## Interpret failures and add tests

`ModuleNotFoundError` usually means the wrong environment, missing editable
installation, or missing `PYTHONPATH`. Follow the setup instructions before
changing a test. Import/dependency failures are not passing checks.

Keep tests in `test_*.py`, with pytest functions named `test_*` or methods in a
`unittest.TestCase`. Use `tmp_path` for files and `monkeypatch` or mocks for
hardware. Do not use local recordings, checkpoints, or calibration as fixtures.
No minimum coverage percentage is configured. Add regressions for changes to
motion safety, metadata validation, dataset integrity, and checkpoint behavior.
Unsupported-schema rejection tests protect the schema-3 input boundary; they
do not provide compatibility conversion.

For a separate check that actually trains tiny synthetic ACT and DP models,
use the [training smoke check](../docs/guides/training/act_dp.md#reproduce-the-software-smoke-check).
It is outside the normal pytest suite and opens no hardware.
