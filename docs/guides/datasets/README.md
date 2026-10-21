# Datasets: meaning and behavior

Use [review and preparation](preparation.md) for counting, playback, decisions,
conversion, and rebuilding. Use [curation](curation.md) for quarantine, restore,
transfer, top-up, and merge operations.

## Projects, episodes, and counts

A project is a collection beneath the dataset root. Its `collect_data/` directory
contains raw episode folders. The project name selects a registered configuration
in `scripts/scripts_config.py`; `poly_mailer_bottom` is one default example.
Medium-only projects can hold several faces. Face-specific projects require the
matching face in episode metadata.

The episode counter uses metadata, not video inspection:

| Count | Meaning |
| --- | --- |
| Complete | `recording_complete` is true and the metadata frame count is a positive integer. |
| Incomplete | An active, interrupted, zero-frame, or otherwise non-complete recording. |
| Unknown | Missing, unreadable, or unsupported recording metadata. |

Those counts do not verify frame files or physical task success. Review status
is separate: a complete episode can still be `unreviewed` or `rejected`.

The tools support schema-3 `episode_metadata.json` only. Unsupported schemas,
missing metadata, and the alternate filename `metadata.json` are refused. The
raw `control_period_ms` must be positive and finite; missing recording rates are
not guessed. The tools do not migrate unsupported archives.

## How image playback works

Raw camera frames are JPG images with numeric filenames. The review player
sorts those numbers, loads matching top/left-wrist/right-wrist images, and shows
the three views side by side. Replacing the images in sequence produces video
playback without first creating an MP4. Display delay is based on episode
elapsed time divided by frame count, adjusted by configured playback speed;
the configured fallback period applies when timing is unavailable.

Playback uses an average interval, not per-frame timestamps, so it approximates
recorded speed. The last frame remains visible until a decision or replay. Review
opens no robot interfaces and never moves the robot. `--terminal-only` expects
separate visual inspection; it does not provide image playback.

## Review decisions and end checks

`accepted`, `rejected`, and `unreviewed` are persisted decisions, not inferred
physical outcomes. Default playback selects unreviewed episodes. Decisions are
saved immediately to raw metadata and synchronized to matching converted HDF5
files. A rejection does not erase raw recordings or alter trained checkpoints.
Review refuses converted files with missing or unsupported provenance.

Acceptance checks matching frame identifiers and trusted local observations.
Advisory checks compare the start with home, assess measured recording rate, and
compare the end with the taught scan pose. The holding arm must meet forward-
kinematics position/orientation tolerances, the other arm must be home, and
joints must settle for at least 0.5 seconds. Driver velocities are placeholders,
so settling uses differences between successive joint observations.

The current check also expects both gripper commands near 1.0. This can warn on
valid partial-width grasps; see the [gripper-width limitation](../recording/README.md#gripper-width-and-handoff).
A missing local scan pose produces a warning rather than supplying a guessed
pose. These checks do not establish grasp success.

### Count and review options

| Argument | Meaning |
| --- | --- |
| `count_episodes.py --details` | Print totals plus each episode's medium, label face, and review status. |
| `count_episodes.py --project poly_mailer_bottom` | Optional: count only that exact project folder instead of every project. |
| `count_episodes.py --root datasets` | Optional: set the parent dataset directory; `datasets/` is the default. |
| `review_episodes.py --project "datasets/$PROJECT"` | Open recordings from this project folder; here the path is `datasets/poly_mailer_bottom`. Unlike the count tool, this option takes a folder path. |

| Review option | Meaning |
| --- | --- |
| `--include-reviewed` | Revisit accepted and rejected episodes as well as unreviewed ones. |
| `--only-rejected` | Review only current rejections. Do not combine with `--include-reviewed`. |
| `--episodes EPISODE_ID_1 EPISODE_ID_2` | Select exact folder names under `collect_data/`; replace the example IDs. |
| `--terminal-only` | Ask for decisions in the terminal without opening video. Inspect the videos separately first. |

`a` accepts, `r` rejects, `s` skips, `p` replays, space toggles pause, and `q`
quits. `--set-status` supports `accepted`, `rejected`, and `unreviewed` for batch
decisions. `--sync-review-status` copies existing raw review decisions into
matching HDF5 metadata without selecting a new decision. Those modes are mutually
exclusive; review `--dry-run` is available only with one of them.

## Conversion and rebuilding

Validation reads raw episodes and reports lengths, rate, overruns, review status,
and warnings. Conversion writes accepted, complete, fresh schema-3 episodes to
`train_data/`, plus `output_videos/` and `conversion_logs/`. Camera and observation
frame identifiers must match. Raw sources are preserved. Face-specific projects
also enforce their registered face.

| Argument | Meaning |
| --- | --- |
| `--dataset-name "$PROJECT"` | Select a name registered in `PREPARE_ACT_DATASETS["projects"]` in `scripts/scripts_config.py`. This is a name, not a folder path. |
| `--convert` | Write the accepted episodes' HDF5 files, review videos, and conversion logs. Without this switch, the command validates and reports only. |
| `--root datasets` | Optional: use another parent dataset directory. Keep the training configuration pointed at the same root. |
| `--allow-rollouts` | Optional: include rollout sources only in explicitly named `rollout`/`rollouts` projects. Leave it off for demonstration collections. |

`--rebuild-to NEW --convert` copies accepted raw episodes into a fresh registered
project and converts there. It requires a source `--dataset-name`, an unused
destination folder, and `--convert`. Conversion refuses existing HDF5 targets.
The rebuild validates the selection, copies through a temporary sibling, records
provenance, and retains an incomplete-build marker until conversion succeeds.

Rebuilding matters because the vendor loader reads every HDF5 in its training
folder. A rejected converted episode is not removed automatically. Stale and
incomplete training folders are refused by training and downstream conversion.
Fresh robomimic datasets, frozen splits, and checkpoints must be created
separately; raw curation does not rebuild them.

## Curation behavior

Curation checks medium, schema, camera set, recording rate, episode horizon,
and a destination's label-face constraint when present. It refuses path/episode
collisions and symlinks, hashes payloads, logs provenance, and plans before
writing. Recorded actions and episode provenance are not rewritten; review is
a separate operation. Applied moves roll back on failure.

| Operation | Effect |
| --- | --- |
| Status | Reports review/face counts, quarantine contents, and stale conversion state. |
| Quarantine | Moves rejected raw episodes and matching converted/video artifacts into `rejected_data/`. |
| Restore | Returns explicitly selected quarantined episodes and artifacts; review decisions stay unchanged. |
| Transfer | Moves a selected count or exact episode IDs of accepted raw recordings to an existing project. |
| Top-up | Moves enough accepted raw recordings to reach a destination's final accepted total. |
| Merge | Copies accepted raw recordings into a new project; `--move` changes this to a move. |

Converted artifacts are matched by embedded episode IDs, not their numeric HDF5
indices. Curation appends `curation_log.jsonl` and marks affected conversions
with `train_data/STALE.json`. Frozen datasets, split manifests, and checkpoints
remain unchanged; warnings identify references that need a new training snapshot.
Copy merges preserve source recordings and do not stale unchanged source data.

### Curation options

| Argument or operation | Meaning |
| --- | --- |
| `--from NAME ...` | Source project names. `transfer` takes exactly one source; `top-up` and `merge` accept several. |
| `--to NAME` | Destination project. It must exist for `transfer`/`top-up` and must not exist for `merge`. |
| `transfer --count 5` | Move five accepted raw episodes into the destination. Alternatively use `--episodes ID ...` to choose exact episodes; do not combine the selectors. |
| `top-up --target 50` | Move enough accepted raw episodes to reach 50 accepted destination episodes. This is a final total, not 50 additional episodes. |
| `merge` | Copy all accepted raw episodes into a new project, preserving the source copies. |
| `merge --move` | Move the accepted raw episodes instead of copying them. Only `merge` accepts this switch. |
| `--allow-rollouts` | Explicitly allow rollout sources in an appropriately named rollout destination; leave off for demonstrations. |
| `--dry-run` / `--yes` | Preview without writes / apply without prompting. Remove `--dry-run` to apply with a prompt. |

`status` and `--project NAME` resolve bare names beneath the dataset root;
`--root PATH` changes that parent. Restore requires explicit episode IDs.
Without `--dry-run` or `--yes`, mutation commands print a plan and ask before
applying it. `--yes` skips that prompt. Transfer takes one source, while top-up
and merge accept several. Curation transfer/top-up/merge handles raw episodes,
not a new converted training dataset.

Rollouts are excluded by default. Deliberate inclusion requires `--allow-rollouts`
and an appropriately named destination containing the separate token `rollout`
or `rollouts`. Demonstration collections do not need this opt-in.
