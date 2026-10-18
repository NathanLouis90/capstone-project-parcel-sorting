# Curate reviewed demonstrations

Curation plans operations, checks compatible medium/schema/cameras/rate,
refuses collisions and symlinks, hashes file payloads, and logs provenance.
Metadata and recorded actions are never rewritten. New training collections
require fresh pick-to-scan schema-3 episodes; do not transfer archived episodes.

```bash
python3 scripts/curate_datasets.py status --project poly_mailer
python3 scripts/curate_datasets.py quarantine --project poly_mailer --dry-run
python3 scripts/curate_datasets.py quarantine --project poly_mailer --yes
```

Quarantine preserves rejected raw recordings and matching converted files in
`rejected_data/`. Restore returns them without changing their review decisions.
Use `--help` on `transfer`, `top-up`, and `merge` for combining accepted projects
of the same medium. Register every source/target name in `scripts_config.py`.
The tools plan before writing and roll back applied moves on failure.

Transfers/quarantine mark affected conversions stale. Rebuild accepted-only
training snapshots with the [preparation guide](preparation.md). Frozen
robomimic datasets, splits and checkpoints are not rebuilt by curation; create
new outputs. Rollout data requires an explicit opt-in and a project name
containing `rollout` or `rollouts`.
