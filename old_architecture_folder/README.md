# Superseded architecture archive

`source/` preserves first-party source, tests, and guides from commit `7b5c290`.
It documents the retired staged design and is not an active import or test root.
Bundled third-party packages and hardware manuals remain at their original paths.

`datasets/` and `ckpt/` preserve local artifacts unchanged and are excluded from Git.
Use the archived configuration and the original Git revision to inspect old training runs.
Do not mix these recordings with fresh pick-to-scan demonstrations.

## Historical records

- [Migration inventory](migration_policy_ab.md): baseline source hits and dispositions.
- [Redesign validation](reports/per_medium_validation.md): checks performed during the migration.
- `source/version.txt`: original Dobot SDK release notes.
- `source/scripts/4_collect2train_data.py` and `6_dataset_count.py`: superseded dataset helpers.
- `source/examples/`: original device and dataset demonstration scripts.

Current workflows are listed in the [documentation index](../docs/README.md).
