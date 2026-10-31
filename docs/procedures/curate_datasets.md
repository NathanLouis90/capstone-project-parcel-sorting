# Curate datasets

The result is a checked, reversible change to reviewed recording projects (quarantine, restore, transfer, top-up or merge), or an audit of a model's training data against the rollout motion bounds.

These tools are optional. For deleting rejected recordings and moving overflow, the [training menu](09_train_models.md) is enough.

## Before you start

- [Review the episodes](08_review_episodes.md) involved and stop the recorder. No robot server is needed.
- Open one terminal:
  ```bash
  conda activate Xtrainer
  cd ~/dobot_xtrainer
  ```
- Every project you change must be listed in `DATASETS["projects"]` in `config/settings.py`. Default names (`poly_mailer_bottom`, `poly_mailer_top_extra`, `carton_front`, ...) are already listed. To add another, copy an entry with the same medium, cameras and recording rate.

## Check projects

1. Count recordings with per-episode details.
   ```bash
   python3 tools/count_episodes.py --details
   ```
   Expect: a project table, then medium, label face and review status for each episode. Add `--project poly_mailer_bottom` to show one project.

2. Show one project's review, face and quarantine counts.
   ```bash
   python3 tools/curate_datasets.py status --project poly_mailer_bottom
   ```
   Expect: JSON with `counts`, `media_faces`, `train_data_stale` and `issues`.

## Quarantine rejected episodes

3. Preview moving the project's rejected episodes into `rejected_data/`.
   ```bash
   python3 tools/curate_datasets.py quarantine --project poly_mailer_bottom --dry-run
   ```
   Expect: `quarantine: N operations` and one `MOVE` line per file. Add `--episodes EPISODE_ID ...` to limit the selection.
4. Apply the same selection.
   ```bash
   python3 tools/curate_datasets.py quarantine --project poly_mailer_bottom --yes
   ```
   Expect: the same plan, applied without a prompt. Omit `--yes` to confirm interactively.

## Restore a quarantined episode

5. Preview, then rerun without `--dry-run` and confirm. Replace `EPISODE_ID` with a folder under `rejected_data/`.
   ```bash
   python3 tools/curate_datasets.py restore --project poly_mailer_bottom --episodes EPISODE_ID --dry-run
   ```
   Expect: `MOVE` lines back into `collect_data/`. The episode stays `rejected` until you review it again.

## Transfer, top up, or merge accepted episodes

6. Preview one operation. Each example takes accepted episodes only.
   Move five accepted episodes (one source, existing destination; or use `--episodes ID ...` instead of `--count`):
   ```bash
   python3 tools/curate_datasets.py transfer --from poly_mailer_bottom_extra --to poly_mailer_bottom --count 5 --dry-run
   ```
   Fill the destination up to 50 accepted episodes in total:
   ```bash
   python3 tools/curate_datasets.py top-up --from poly_mailer_bottom_extra --to poly_mailer_bottom --target 50 --dry-run
   ```
   Copy accepted episodes into a new, registered destination that does not exist yet (add `--move` to move instead):
   ```bash
   python3 tools/curate_datasets.py merge --from poly_mailer_bottom poly_mailer_bottom_extra --to poly_mailer --dry-run
   ```
   Expect: `MOVE` or `COPY` lines, `MARK STALE` and `APPEND AUDIT` lines, and a warning that existing splits and checkpoints are not rebuilt.
7. Rerun the chosen command with `--yes` in place of `--dry-run`.
   Expect: the plan is applied; train new models from the [menu](09_train_models.md) to use the changed projects.

## Audit a model's training data against rollout bounds

8. Check recorded command steps, tracking gaps and initial targets in the checkpoint's training split.
   ```bash
   python3 tools/check_rollout_compatibility.py --checkpoint ckpt/act_poly_mailer_v1.1/best.pth
   ```
   Expect: JSON ending with `"compatible_joint_gaps": true` and zero `violations`; exit code 0 (2 when a bound is exceeded). Add `--split valid` or `--split all` for other recordings.

A passing audit is not a physical motion check. See [rollout compatibility](../reference/datasets.md#rollout-compatibility-check).

## If something goes wrong

- `Unregistered project: NAME` -> add `NAME` to `DATASETS["projects"]` in `config/settings.py`.
- `Merge destination already exists` -> choose an unused registered name for `merge`.
- `Not enough accepted episodes` -> lower `--count`, or review more episodes first.
- `label_face mismatch` or another `mismatch` -> the destination expects another face, medium, camera set or rate; choose a compatible destination.
- `Cross-filesystem move refused` -> use `merge` without `--move` to copy.
- `Use --dataset to inspect each dataset in a multi-dataset checkpoint` -> rerun with `--dataset PATH_TO_HDF5`.
