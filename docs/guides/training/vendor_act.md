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

Use `envelope` or `carton` for the other registered tasks. Keep `config.pkl`,
`dataset_stats.pkl`, and `policy_best.ckpt` together. The saved task must remain registered for
the requested medium, including when training a custom accepted-only project. Specify a fresh checkpoint directory for each run.

The loader reads every HDF5 file in the training folder. Rebuild accepted-only
files after rejecting an already-converted episode. Shared task settings in
`scripts/scripts_config.py` determine camera names, episode horizon, and the
training fraction. Stop the recorder before training. Physical evaluation uses
[the cycle supervisor](../runtime/evaluation.md).
