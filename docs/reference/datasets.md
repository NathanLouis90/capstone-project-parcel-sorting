# Datasets reference

Episode format, counting, review, curation, and the prepared training data. For the steps, see [review episodes](../procedures/08_review_episodes.md), [train models](../procedures/09_train_models.md) and [curate datasets](../procedures/curate_datasets.md).

## Projects, episodes and counts

A project is a folder under `datasets/` whose `collect_data/` holds raw episode folders. `poly_mailer_bottom` is the default example; overflow projects such as `poly_mailer_bottom_extra` and frozen collections such as `poly_mailer_bottom_v1` are ordinary projects too. The training menu lists every folder that has `collect_data/`. Projects named after a face (`<medium>_<face>`) carry that face in each episode's metadata.

`tools/count_episodes.py` reads metadata only:

| Count | Meaning |
| --- | --- |
| Complete | `recording_complete` is true and the metadata frame count is a positive integer. |
| Incomplete | Active, interrupted, zero-frame, or otherwise not complete. |
| Unknown | Missing, unreadable, or unsupported metadata. |

These counts do not check frame files or task success. Review status is separate: a complete episode can still be `unreviewed` or `rejected`.

| Count option | Meaning |
| --- | --- |
| `--details` | Also print each episode's medium, label face and review status. |
| `--project poly_mailer_bottom` | Show only this project folder name. |
| `--root datasets` | Parent dataset folder; default `datasets/` (`COUNT_EPISODES` in `config/settings.py`). |

## Episode files

| Path in the episode folder | Content |
| --- | --- |
| `topImg/`, `leftImg/`, `rightImg/` | JPG frames from the top, left-wrist and right-wrist cameras, named `0.jpg`, `1.jpg`, ... |
| `observation/` | One pickle per frame with `joint_positions` (14 values) and `control` (14 action targets). |
| `episode_metadata.json` | Schema-3 provenance written by the recorder and updated by review. |

The 14 values are six joints plus gripper for the left arm, then the same for the right arm. Camera and observation frame identifiers must match exactly, and their number must equal `frame_count`.

Only schema 3 is supported. Missing metadata, other schemas, and the filename `metadata.json` are refused. `control_period_ms` must be positive and finite; a missing rate is never guessed. The tools do not migrate unsupported archives. Observation pickles are trusted local data; never load them from unknown sources.

Metadata fields: `schema_version`, `medium`, `label_face`, `episode_id` (the folder name), `cycle_id`, `started_at`, `ended_at`, `recording_complete`, `review_status`, `reviewed_at`, `frame_count`, `control_overruns`, `control_period_ms`, and `source` for rollout recordings.

## Image playback

`recording/review_episodes.py` sorts the numeric JPG names, loads matching top, left-wrist and right-wrist images, and shows them side by side, so playback needs no MP4. The delay per frame is the episode's elapsed time divided by its frame count, adjusted by `playback_speed`; `fallback_period_ms` applies when timing is missing (`REVIEW_EPISODES` in `config/settings.py`). Playback uses this average interval, not per-frame timestamps, so it approximates the recorded speed. The last frame stays visible until you decide or replay. Review opens no robot interfaces.

`--terminal-only` asks for decisions in the terminal without playback; inspect the recordings elsewhere first.

## Review decisions and end checks

`accepted`, `rejected` and `unreviewed` are persisted operator decisions, not inferred outcomes. Default playback selects unreviewed episodes. Each decision is written immediately to `episode_metadata.json` with a `reviewed_at` time. If the project has a `train_data/` folder of per-episode HDF5 files, review checks that each matching file has the same recording and updates its review status too; `--sync-review-status` copies existing raw decisions into those files. A rejection does not delete recordings or change trained models.

Accepting an episode first verifies its frame files, then prints advisory warnings:

- `Start joints differ from home` or `Start grippers are not open` (open is 1.0).
- `End must hold the scan pose, closed grippers and idle arm home, settled for 0.5 s`: the holding arm must reach its taught scan pose within the supervisor's position and orientation tolerances (forward kinematics), its gripper must be within 0.08 of closed, the other arm must be home with an open gripper, and joints must stay still for 0.5 s. Settling uses differences between successive joint observations because driver velocities are placeholders.
- `Scan pose is unconfigured; teach scan_right` (or `scan_left`): no pose is guessed.
- `N frames exceed inference joint limits`.
- `Measured rate X Hz differs from 25.00 Hz`: more than 10% (`rate_tolerance_fraction`) from the 40 ms control period.

Warnings do not block acceptance and do not establish grasp success. A valid partial-width grasp can trigger the end warning; see [gripper width and handoff](recording.md#gripper-width-and-handoff).

| Review option | Meaning |
| --- | --- |
| `--project datasets/poly_mailer_bottom` | Project folder path (not a bare name) containing `collect_data/`. |
| `--include-reviewed` | Also revisit accepted and rejected episodes. |
| `--only-rejected` | Only current rejections. Not combinable with `--include-reviewed`. |
| `--episodes ID ...` | Exact folder names under `collect_data/`. |
| `--terminal-only` | Decide in the terminal without playback. Interactive review only. |
| `--set-status accepted\|rejected\|unreviewed` | Batch decision for episodes already inspected. |
| `--sync-review-status` | Copy raw decisions into matching HDF5 files. Not combinable with `--set-status`. |
| `--dry-run` | Check a `--set-status` or `--sync-review-status` batch without writing. |

Keys in the video window: `a` accept, `r` reject, `s` skip, `p` replay, space pause, `q` quit. Batch modes check the whole selection before writing any decision.

## Menu dataset operations

The [training menu](training.md#menu-behaviour) provides the everyday operations:

- **Delete rejected recordings** permanently removes explicitly rejected episodes (including any in `rejected_data/`) and their attributable HDF5 files and videos. There is no quarantine. Accepted and unreviewed episodes stay; trained models and their frozen data are unchanged.
- **Move recordings** moves accepted episodes to another project, creating the folders when the name is new. Episode IDs and review decisions are preserved. Collisions, symlinks and incompatible media, schema, cameras or recording rate are refused before anything moves. No registration in `config/settings.py` is needed.

Both operations append to each affected project's `curation_log.jsonl` and write `train_data/STALE.json` (delete only when `train_data/` already exists), so per-project HDF5 files are not mistaken for current data. The menu's own training reads raw recordings and ignores these markers.

## Curation tool

`tools/curate_datasets.py` offers reversible, audited operations for registered projects. Every project it changes must be listed in `DATASETS["projects"]` in `config/settings.py`; `status` also reads unregistered folders. The registry contains medium-only projects (`envelope`, `poly_mailer`, `carton`), every `<medium>_<face>`, and `poly_mailer_top_extra` / `poly_mailer_bottom_extra`, each with schema 3, cameras `top`, `left_wrist`, `right_wrist`, a 40 ms control period and a 500-frame episode limit.

| Operation | Effect |
| --- | --- |
| `status` | Review, face and quarantine counts, stale state of `train_data/`, and issues. |
| `quarantine` | Move rejected episodes, and matching HDF5 files and videos, into `rejected_data/`. With `--episodes`, every selected episode must be rejected. |
| `restore` | Return explicitly selected quarantined episodes. Their review status stays `rejected`. |
| `transfer` | Move `--count N` of the earliest accepted episodes (by start time), or exact `--episodes`, from one source to an existing destination. |
| `top-up` | Move enough accepted episodes from one or more sources for the destination to reach `--target N` accepted in total (not N more). |
| `merge` | Copy accepted episodes from one or more sources into a new destination; `--move` moves instead. |

Curation checks medium, schema, camera set, recording rate, episode length, and the destination's label face when it has one. It refuses path and episode collisions, symlinks, and cross-filesystem moves, hashes payloads, and plans before writing. Applied moves roll back on failure. Episode metadata and recorded actions are never rewritten.

Each run prints its plan (`MOVE`/`COPY`, `MARK STALE`, `APPEND AUDIT`, warnings). `--dry-run` stops there; `--yes` applies without a prompt; with neither, it asks before applying. `--root PATH` changes the parent dataset folder. HDF5 files are matched by embedded episode ID, not file index. Copy merges leave sources unchanged and do not mark them stale. Existing prepared training data, splits and checkpoints are never rebuilt; train new models to use the changed projects.

Rollout recordings are excluded by default. Including them needs `--allow-rollouts` and a destination whose name contains the separate token `rollout` or `rollouts`. Demonstrations never need this.

## Rollout compatibility check

`tools/check_rollout_compatibility.py` reads only the joint and action arrays of a prepared HDF5 (`--dataset`) or of the dataset saved in a checkpoint (`--checkpoint`), for the `train` split by default (`--split valid|all`). It opens no hardware and no images.

| Measured gap | Bound | Source |
| --- | --- | --- |
| Consecutive recorded commands (`command_step`) | 0.17 rad per joint | `RUNTIME["max_joint_increment_rad"]` |
| Command versus measured joints (`target_tracking`, `previous_command_tracking`) | 0.6 rad | `SUPERVISOR["tracking_tolerance_rad"]` |
| First target versus home (`initial_approach`) | 0.6 rad | `SUPERVISOR["policy_approach_max_rad"]` |

Gripper channels are excluded. The report also counts initial targets that need a paced approach (more than one command step from home) and starts outside the 0.12 rad home tolerance. The exit code is 0 when no bound is exceeded and 2 otherwise. A pass covers joint gaps only, not workspace or cable clearance or live policy predictions. Runtime behaviour is described in [runtime](runtime.md).

## Training cache

The training menu builds prepared data directly from accepted raw recordings into `datasets/.training_cache/<hash>/`:

| File | Content |
| --- | --- |
| `dataset.hdf5` | One `demo_N` per recording: RGB images resized to the chosen square size, `qpos`, `actions`, provenance, and `train`/`valid` masks. |
| `split.json` | Source recording IDs, cycle IDs, SHA-256 hashes, seed and validation percentage. |
| `manifest.json` | The description that produced the hash and the dataset's SHA-256. |

The folder name is a hash of the split, image size and format, so identical selections reuse the same data after an integrity check, and any change in recordings or split settings creates new data. Recordings that change during preparation are refused. `datasets/.training_cache/preferences.json` holds the menu's saved hyperparameter defaults. Keep the cache: trained models refer to their prepared data, and [training on frozen data](training.md#training-on-frozen-data) reuses it.
