# Curate reviewed demonstrations

Run in one terminal from the repository root with `Xtrainer` activated; no
robot server is needed. See [terminal setup](../../terminal_commands.md).

Curation plans operations, checks compatible medium/schema/cameras/rate,
refuses collisions and symlinks, hashes file payloads, and logs provenance.
Metadata and recorded actions are never rewritten. New training collections
require fresh pick-to-scan schema-3 episodes; do not transfer archived episodes.
The recorded `control_period_ms` must be present and match the destination;
curation never assumes a rate for missing metadata.

```bash
python3 scripts/curate_datasets.py status --project poly_mailer
```

`status` is a subcommand that reports review counts, label-face counts,
quarantined episodes, and stale conversion state. `--project poly_mailer`
selects `datasets/poly_mailer/`. `--root PATH` optionally changes the dataset
parent; a bare project name is resolved beneath it.

## Quarantine or restore rejected episodes

```bash
python3 scripts/curate_datasets.py quarantine --project poly_mailer --dry-run
python3 scripts/curate_datasets.py quarantine --project poly_mailer --yes
```

Run the first command and inspect its plan before using the second.
`quarantine` selects all episodes currently marked rejected unless you add
`--episodes EPISODE_ID_1 EPISODE_ID_2` to select exact folder names.
`--dry-run` prints the proposed moves without changing files. `--yes` applies
the plan without a confirmation prompt. If neither switch is given, the tool
prints the plan and asks before applying it.

Quarantine preserves rejected raw recordings and matching converted files in
`rejected_data/`. Restore returns them without changing their review decisions.

```bash
python3 scripts/curate_datasets.py restore --project poly_mailer \
  --episodes EPISODE_ID --dry-run
```

Replace `EPISODE_ID` with a folder name under `datasets/poly_mailer/rejected_data/`.
`restore` requires explicit `--episodes`; remove `--dry-run` to apply with a
confirmation prompt. A restored rejection stays rejected until reviewed again.

## Transfer, top up, or merge accepted collections

Register every source and target name in `scripts/scripts_config.py` with the
same medium and compatible settings. The examples below assume existing source
projects `poly_mailer_extra` and `poly_mailer_session2`, an existing destination
`poly_mailer`, and a registered but not yet created `poly_mailer_combined`.

```bash
python3 scripts/curate_datasets.py transfer --from poly_mailer_extra \
  --to poly_mailer --count 5 --dry-run
python3 scripts/curate_datasets.py top-up --from poly_mailer_extra poly_mailer_session2 \
  --to poly_mailer --target 50 --dry-run
python3 scripts/curate_datasets.py merge --from poly_mailer poly_mailer_extra \
  --to poly_mailer_combined --dry-run
```

These are alternative operations. Each example only previews its own plan.

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

Transfer, top-up, and merge operate on raw episodes; they do not create a new
converted training dataset. Use the preparation guide afterward.
The tools plan before writing and roll back applied moves on failure.

Transfers/quarantine mark affected conversions stale. Rebuild accepted-only
training snapshots with the [preparation guide](preparation.md). Frozen
robomimic datasets, splits and checkpoints are not rebuilt by curation; create
new outputs. Rollout data requires an explicit opt-in and a project name
containing `rollout` or `rollouts`.
