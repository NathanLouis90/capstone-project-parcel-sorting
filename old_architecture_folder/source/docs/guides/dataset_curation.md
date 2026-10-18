# Curate reviewed datasets

Use this guide after watching episodes with `scripts/review_episodes.py`. Curation moves or copies recordings that you have already judged; it does not decide whether a grasp or placement succeeded. The current experiment milestones are **50 and 100 accepted demonstrations**, with training and validation counts reported separately. There is no requirement to train 25- or 75-demonstration models.

Run Bash blocks from the repository root with `Xtrainer` activated:

```bash
conda activate Xtrainer
cd /home/adiel/dobot_xtrainer
```

Stop recorders, conversion and training processes that use the affected projects before applying curation. Preview each operation with `--dry-run`. Without it, the tool prints the complete plan and asks for confirmation. `--yes` applies the checked plan without a prompt. Failed preflight checks change nothing; a filesystem error during application triggers rollback of completed operations. Move operations use same-filesystem renames. Keep a separate backup against power loss or disk failure.

## Project names and compatibility

Existing recording projects use `set01_...` and `set02_...`, without an underscore between `set` and its number. Preliminary folders use `preliminary_...`. Names identify collections, not a fixed episode count. Register custom names under `PREPARE_ACT_DATASETS["projects"]` in `scripts/scripts_config.py` before using them as transfer/merge destinations or preparing them. Current set01/set02 and fresh `train50_...` / `train100_...` poly-mailer/carton names are registered. Historical `first_set_...` aliases remain for older checkpoints.

Transfers and merges accept only `accepted`, completed episodes. They check recorded stage, medium, B destination, camera set, nominal recording period and maximum episode length against the destination settings. Registered source settings and existing destination episodes must also agree. A folder name never overrides recorded metadata. Unreviewed/rejected source episodes are skipped during automatic selection; explicitly selecting one is refused.

Older recordings have no `control_period_ms`. For those recordings, the tool assumes the configured 40 ms nominal period and prints a warning. It does not infer a nominal period from the episode's elapsed duration. Review measured timing separately with preparation; old and new recordings can have different actual rates despite sharing a nominal target.

## 1. Review and check status

The following assignment selects the existing A collection for the remaining examples. Repeat it in a new terminal:

```bash
PROJECT="set01_poly_mailer_A"
python3 scripts/review_episodes.py --project "datasets/$PROJECT"
python3 scripts/curate_datasets.py status --project "$PROJECT"
```

Review keys are **a** accept, **r** reject, **s** skip, **p** replay, **space** pause/resume and **q** quit. `status` reports accepted, rejected, unreviewed, invalid and quarantined counts; recorded stage/medium/bin groups; identity problems; and stale/incomplete conversion markers.

For a per-episode listing, including metadata that disagrees with folder names:

```bash
python3 scripts/count_episodes.py --project preliminary_carton_B --details
```

## 2. Remove rejected recordings from active data

```bash
python3 scripts/curate_datasets.py quarantine --project "$PROJECT" --dry-run
python3 scripts/curate_datasets.py quarantine --project "$PROJECT"
```

Only rejected episodes move. `--episodes ID_1 ID_2` limits the selection to those folder names. The layout becomes:

```text
datasets/<project>/
  collect_data/<accepted_or_unreviewed_episode>/
  rejected_data/<rejected_episode>/
  rejected_data/converted/train_data/episode_init_<original_index>.hdf5
  rejected_data/converted/output_videos/<episode_id>_video.mp4
  train_data/STALE.json
  curation_log.jsonl
```

Matching HDF5 files are identified by embedded episode IDs, never by their numeric filenames. Matching review videos move with them. Quarantine retains all data and review decisions; it does not delete recordings. Count, review, preparation and conversion tools enumerate `collect_data/` or `train_data/`, so quarantined content is excluded.

To undo quarantine, set the exact episode folder name shown in the curation plan or under `rejected_data/`:

```bash
EPISODE_ID="your_quarantined_episode_id"
python3 scripts/curate_datasets.py restore --project "$PROJECT" \
  --episodes "$EPISODE_ID" --dry-run
python3 scripts/curate_datasets.py restore --project "$PROJECT" \
  --episodes "$EPISODE_ID"
```

Restore returns matching conversions/videos to their original locations. The restored episode remains rejected. Use the review tool to change that decision after inspecting it. A conflicting raw folder or converted filename blocks the entire restore.

## 3. Move accepted recordings between projects

Review the preliminary project first. Only episodes that you explicitly accept can be reused:

```bash
python3 scripts/review_episodes.py --project datasets/preliminary_poly_mailer_A
python3 scripts/curate_datasets.py transfer \
  --from preliminary_poly_mailer_A --to set01_poly_mailer_A \
  --count 1 --dry-run
```

Repeat the transfer without `--dry-run` to apply it. `--count K` picks the oldest accepted recording timestamps first, breaking ties by episode ID and source path, and prints the selected IDs. To choose specific episodes, replace `--count 1` with `--episodes ID_1 ID_2`. Never use both options together.

After reviewing set02, the same command moves its accepted A episodes into set01:

```bash
python3 scripts/curate_datasets.py transfer \
  --from set02_poly_mailer_A --to set01_poly_mailer_A \
  --count 5 --dry-run
```

Use the actual accepted count. For B, repeat separately with `set02_poly_mailer_B_bin_0` and `set01_poly_mailer_B_bin_0`, then the bin-1 equivalents. A and B cannot be mixed, and B bins cannot be mixed in one Dobot training project.

Transfers move raw episode directories only. Existing converted HDF5 files stay in the source project's `train_data/`; both affected projects are marked stale. Nothing is silently renamed or renumbered. Keep B's original A-source links; the tool warns about affected links and records the move in audit logs rather than rewriting episode metadata.

## 4. Fill a project to a target

For the worked example, suppose project A has 24 accepted and one rejected, and project B has five accepted. Run:

```bash
python3 scripts/curate_datasets.py quarantine --project A
python3 scripts/curate_datasets.py top-up --to A --from B --target 25
```

A ends with 25 accepted active episodes and one quarantined rejection. B retains four accepted episodes. A/B in this example are project names; register the destination's settings first. The 25 target illustrates replenishment and is not an experiment milestone.

For your 50-demonstration A collection, after reviewing both potential sources:

```bash
python3 scripts/curate_datasets.py top-up \
  --to set01_poly_mailer_A \
  --from preliminary_poly_mailer_A set02_poly_mailer_A \
  --target 50 --dry-run
```

`--target` counts accepted episodes already in the destination, not all folders. Selection is oldest-first across all listed sources. Insufficient accepted source episodes block the entire operation. A destination already at or above target is unchanged. The present local sources do not yet provide 50 accepted A demonstrations; review and collect enough before applying this target.

## 5. Combine projects

Register `combined_poly_mailer_A` with the same A/poly-mailer settings and a sufficient `episode_len`, then preview:

```bash
python3 scripts/curate_datasets.py merge \
  --from set01_poly_mailer_A set02_poly_mailer_A \
  --to combined_poly_mailer_A --dry-run
```

The destination must be new. Copy is the default; `--move` removes selected raw episodes from sources instead. Both modes preserve episode IDs and metadata. Duplicate IDs across sources or the destination block the entire plan. A copy merge leaves source training files usable; the new destination receives a stale marker until rebuilt through the fresh-project workflow below.

Every affected project receives an append-only `curation_log.jsonl` entry containing UTC time, command, transaction ID, episode IDs, original/destination paths, and SHA-256 hashes of every affected file. Copy-merge sources receive audit entries without becoming stale. Logs preserve provenance outside episode metadata so review synchronization remains compatible.

## 6. Rebuild fresh training snapshots for 50 and 100

Every curation change to an active raw episode set writes `train_data/STALE.json`, even if no conversions existed yet. Preparation, direct conversion, robomimic source conversion and the Dobot training launcher refuse stale input. Do not delete this marker to reuse old files: raw episode changes can invalidate the entire numerical HDF5 index mapping.

When `status` confirms exactly 50 accepted A demonstrations, create the registered, unused `train50_poly_mailer_A` project:

```bash
python3 scripts/curate_datasets.py status --project set01_poly_mailer_A
python3 scripts/prepare_act_datasets.py \
  --dataset-name set01_poly_mailer_A \
  --rebuild-to train50_poly_mailer_A --convert
```

This validates accepted raw episodes against the destination settings, copies them unchanged into the fresh project, and converts them there. It leaves the source and its stale marker unchanged. Rejected/unreviewed episodes and old HDF5 files are not copied. New HDF5 indices are consecutive. A `BUILDING.json` marker blocks training until every conversion succeeds; a failed rebuild requires another fresh output name. Rebuild provenance is logged in the new project. The name `train50` does not enforce a count: check `status` before running it.

Train the registered `train50_poly_mailer_A` task using the [Dobot ACT guide](act_training.md). With an 80/20 split and 50 accepted demonstrations, expect 40 training and 10 validation episodes. After reaching 100 accepted source demonstrations, rebuild into the unused `train100_poly_mailer_A` project and train from scratch; expect 80/20 episodes. Keep the 50 snapshot unchanged. Repeat separately for each B bin. Use new model output directories and report actual split counts, especially if combining folders through the older multi-folder loader.

Existing robomimic datasets, frozen split files and checkpoints are never modified. The tool warns when local manifests, robomimic metadata or checkpoint configs reference affected sources. It cannot establish the provenance of an opaque checkpoint without a saved source/config reference. Build new robomimic dataset/split files and retrain when the accepted episode set changes.

## 7. Rollouts and demonstrations

Automatic policy rollout recording is outside this curation change. The current inference workflow still requires [operator evaluation](inference_evaluation.md). If an existing/future raw recording carries `source: "rollout"`, preparation and robomimic conversion exclude it by default. Compatible raw rollout episodes can use the existing review playback layout.

Moving or merging rollout data requires `--allow-rollouts` and a destination name with a separate `rollout` or `rollouts` word, for example `rollout_poly_mailer_A`. Preparation/conversion also require explicit opt-in and an explicit rollout project name; robomimic's output dataset name must identify rollouts too. Register custom rollout destinations first. Do not mix evaluation attempts into demonstration training sets by accident.

## 8. Preliminary carton findings, 17 October 2026

The read-only audit found five episodes in `preliminary_carton_A` labelled A, and four B plus one A in `preliminary_carton_B`. All ten episodes record `medium: "poly_mailer"`, despite the carton folder names.

The exceptional folder is `preliminary_carton_B/collect_data/20261015102831505618_update_policy`. Its metadata still records `episode_id: "20261015102831505618"`, stage A, no demonstrated bin and no destination. Renaming a directory does not update its stage or episode ID. The counter reads metadata, so its A,B result is accurate. Metadata cannot establish which physical task was demonstrated; watch the recording before deciding how to repair or exclude it. Curation does not automatically relabel these files, and the ID mismatch must be resolved before normal review/transfer can accept that episode.

Future carton recording commands must specify both `--policy-stage A` or `B` and `--medium carton`, plus the intended `--demonstrated-bin` for B. No recorder CLI changes are required.

Follow-up correction on 17 October 2026: the operator confirmed that the exceptional episode demonstrates a carton placed into bin 0 using Policy B. Its metadata now records B/carton/manual bin 0, and its folder was restored to `20261015102831505618` to match the original episode ID. Original metadata is backed up in the project's `.metadata_backups/`; before/after metadata and file hashes are recorded in `curation_log.jsonl`. All 844 observation/image files are unchanged. The project has a stale marker for fresh rebuilding, and the episode remains unreviewed. Other preliminary carton episodes still require their recorded medium to be checked.

For future recordings, run this from the repository root with `Xtrainer` activated:

```bash
python3 experiments/run_control.py --show-img \
  --project-name set01_carton_B_bin_0 \
  --policy-stage B --medium carton --demonstrated-bin 0
```

For bin 1, change both the project suffix and `--demonstrated-bin` to `1`. Stop and restart the recorder to change stage, medium or bin. Recording-button presses do not change these settings. For Policy A, use `--policy-stage A`, an A project name, and omit `--demonstrated-bin`.

For a saved metadata mistake, back up `episode_metadata.json` outside the active episode folders first. Correct `policy_stage`, `medium`, `demonstrated_bin`, the manual `destination` object (`bin_index`, `source`, correction-time `recorded_at`), and `destination_resolved` together. Preserve original timestamps, cycle ID, observations/images and review status, and keep the directory name equal to `episode_id`. Do not invent a scan or A-source pairing. Log the correction and mark previous conversions stale; if conversions already exist, rebuild into a fresh project rather than changing raw metadata alone and reusing those HDF5 files.

## Troubleshooting

| Refusal or report | Action |
| --- | --- |
| `Unregistered project` | Register the exact destination name and settings in `scripts_config.py`. |
| `requires accepted review status` / `requires rejected review status` | Review first; transfer/merge require accepted, quarantine requires rejected. |
| `policy_stage`, `medium`, `bin_index`, `camera_names` or `control_period_ms mismatch` | Select recordings of the same task/setup/rate; inspect recorded metadata rather than trusting folder names. |
| `episode_len exceeded` | Review length and register a justified longer destination limit; never silently truncate. |
| `episode_id/path collision` | Choose another destination/selection; existing episodes are never overwritten. |
| `episode_id differs from folder name` | Investigate a renamed recording; do not guess stage or change only one copy of already-converted metadata. |
| `Incomplete recording`, frame-count/camera mismatch, nonnumeric observation names | Inspect raw recording integrity; incomplete episodes cannot be transferred as accepted data. |
| `Not enough accepted episodes` / `No accepted episodes to merge` | Review more candidates, collect more, or choose a smaller target. |
| `Unknown episode IDs`, duplicate IDs or `Use episode folder names` | Use exact child directory names, not paths, without duplicates. |
| `Source and destination ... differ` / `sources must be unique` | Select distinct source/destination projects. |
| `Merge destination already exists` / fresh rebuild destination exists | Choose a new registered output project. |
| `Stale train_data` | Use `--rebuild-to NEW --convert`; preserve the old training folder. |
| `Rollout requires --allow-rollouts` | Keep evaluation separate, or explicitly opt in using a registered rollout-named destination. |
| `Cross-filesystem move refused` | Use a copy merge on the destination filesystem. |
| `Source changed since planning` | Stop writers and rerun the preview. |
| Symlink or special-file refusal | Use ordinary dataset directories and regular files. |
| Filesystem/permission/lock error | Stop competing curation processes and check permissions/storage; inspect the reported rollback result before retrying. |
| Missing metadata or converted provenance | Inspect the recording/conversion; do not attribute a numerical HDF5 filename to an episode by guessing. |
| Legacy rate or A/B source-link warning | Check measured timing/source provenance; metadata stays unchanged and the move is recorded in the audit log. |
