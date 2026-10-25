# Curate reviewed demonstrations

The standard workflow is now `python3 scripts/train_models.py` after review.
Choose **2** to permanently delete rejected recordings without quarantine.
Choose **3** to move accepted recordings, including overflow beyond a chosen
count; type a new destination name and the menu creates its folders automatically.
Choose **4** to train on selected collections without merging or copying source
folders. No project registration is required. See the [menu guide](../training/menu.md).

## Advanced legacy commands

The commands below retain the older reversible quarantine and registered-project
workflow for explicit advanced use. They are not required by the menu.

Prepare [one terminal](../../terminal_commands.md) with `Xtrainer` activated.
Stop recording. No robot server is needed. Read the [dataset README](README.md)
for operation meanings, compatibility rules, stale markers, and provenance.

## 1. Check the project

```bash
python3 scripts/curate_datasets.py status --project poly_mailer
```

Replace `poly_mailer` with the exact project name, such as `poly_mailer_bottom`.
Inspect review counts, face counts, quarantine contents, and conversion state.
Use `--root PATH` when the project is outside the configured dataset root.

## 2. Quarantine rejected episodes

1. Mark the intended episodes rejected using the [review procedure](preparation.md).
2. Preview the moves:

```bash
python3 scripts/curate_datasets.py quarantine --project poly_mailer --dry-run
```

3. Check every source and destination. Add `--episodes EPISODE_ID_1 EPISODE_ID_2`
   if you need an exact subset.
4. Apply the reviewed plan:

```bash
python3 scripts/curate_datasets.py quarantine --project poly_mailer --yes
```

Use the same project and episode selection in both commands. Omit `--yes` to
review the plan and confirm interactively instead.

## 3. Restore a quarantined episode

Replace `EPISODE_ID` with a folder name under that project's `rejected_data/`:

```bash
python3 scripts/curate_datasets.py restore --project poly_mailer \
  --episodes EPISODE_ID --dry-run
```

Inspect the plan, then rerun without `--dry-run` and confirm. Review the restored
episode again before accepting it; restoration does not change its rejection.

## 4. Transfer, top up, or merge accepted episodes

1. Register the sources and destination in `scripts/scripts_config.py` with the
   same medium and compatible schema, cameras, recording rate, horizon, and any
   destination label-face constraint.
2. Use existing destinations for transfer/top-up. Use a registered destination
   that does not exist for merge.
3. Choose one operation below and preview its plan. These examples assume
   existing `poly_mailer`, `poly_mailer_extra`, and `poly_mailer_session2` projects,
   plus a registered, unused `poly_mailer_combined` destination.

The face-specific overflow projects `poly_mailer_bottom_extra` and
`poly_mailer_top_extra` are registered with the same settings as their sources.
Create their raw recording folders before using `transfer`:

```bash
mkdir -p datasets/poly_mailer_bottom_extra/collect_data
mkdir -p datasets/poly_mailer_top_extra/collect_data
```

`transfer --count N` selects the earliest accepted recordings by start time.
To keep the earliest 50 accepted episodes in a source and move only newer
overflow episodes, select their exact folder IDs with `--episodes ID ...`
instead. Rejected episodes do not count toward the accepted total.

Move five accepted episodes:

```bash
python3 scripts/curate_datasets.py transfer --from poly_mailer_extra \
  --to poly_mailer --count 5 --dry-run
```

Top up the destination to 50 accepted episodes:

```bash
python3 scripts/curate_datasets.py top-up --from poly_mailer_extra poly_mailer_session2 \
  --to poly_mailer --target 50 --dry-run
```

Copy accepted episodes into a new combined project:

```bash
python3 scripts/curate_datasets.py merge --from poly_mailer poly_mailer_extra \
  --to poly_mailer_combined --dry-run
```

4. Check the full plan, including stale markers and audit paths.
5. Rerun only your chosen command without `--dry-run` and confirm it, or replace
   `--dry-run` with `--yes` to apply the reviewed plan without a prompt.
6. Keep `--allow-rollouts` off for demonstrations. For deliberate rollout use,
   follow the [explicit naming and opt-in rules](README.md#curation-options).

## 5. Rebuild training outputs

Follow [fresh preparation](preparation.md#3-rebuild-after-decisions-change) after
changing a collection. Rebuild accepted-only conversions and create new frozen
robomimic datasets, splits, and checkpoint outputs. Do not reuse stale training
folders or assume curation rebuilt converted data.
