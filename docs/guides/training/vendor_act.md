# Dobot ACT training

Use this optional vendor route for `.ckpt` models. For the ACT/DP comparison,
use [matched robomimic training](act_dp.md). The checkpoint formats
are distinct; select the matching supervisor backend.

Record and prepare a fresh per-medium project first. Run from the repository
root in the Python 3.8 `Xtrainer` environment with CUDA available:

```bash
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name poly_mailer --ckpt_dir ./ckpt/poly_mailer_vendor \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

| Command part | Meaning |
| --- | --- |
| `PYTHONPATH=.` | Allow this command to import modules from the repository root. |
| `MPLBACKEND=Agg` | Save plots without opening interactive plotting windows. |
| `--task_name poly_mailer` | Select a registered training task and its prepared dataset. Use the exact project name from `scripts/scripts_config.py`. |
| `--ckpt_dir ./ckpt/poly_mailer_vendor` | Save this run's checkpoints, configuration, statistics, and plots in this directory. Choose a fresh directory per run. |
| `--batch_size 8` | Use eight training samples per batch; reduce this if GPU memory is insufficient. |
| `--num_steps 30000` | Set the training step limit to 30,000. This is not an episode count. |
| `--lr 2e-5` | Set the optimizer learning rate to `0.00002`. |
| `--chunk_size 45` | Predict a sequence of 45 actions at each policy query. |
| `--kl_weight 10` | Set the ACT latent-distribution regularization weight to 10. |
| `--seed 0` | Set the random seed for this run. Keep seeds recorded when comparing results. |

These option names use underscores, such as `--task_name`, rather than the
hyphens used by most other repository tools. Optional `--validate_every 100`
checks validation loss every 100 steps; `--save_every 1000` writes periodic
checkpoints every 1,000 steps. Both values are step intervals. No robot server
is needed. See [terminal setup](../../terminal_commands.md).

Use `envelope` or `carton` for the other registered tasks. Keep `config.pkl`,
`dataset_stats.pkl`, and `policy_best.ckpt` together. The saved task must remain registered for
the requested medium, including when training a custom accepted-only project. Specify a fresh checkpoint directory for each run.

The loader reads every HDF5 file in the training folder. Rebuild accepted-only
files after rejecting an already-converted episode. Shared task settings in
`scripts/scripts_config.py` determine camera names, episode horizon, and the
training fraction. Stop the recorder before training. Physical evaluation uses
[the cycle supervisor](../runtime/evaluation.md).
