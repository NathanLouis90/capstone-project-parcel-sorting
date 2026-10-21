# Train Dobot ACT

Use [matched ACT/DP training](act_dp.md) for comparison experiments. Use this
procedure for vendor `.ckpt` models. Read the [training README](README.md) for
option meanings and checkpoint compatibility.

## 1. Prepare the training input

1. Review and [convert a fresh project](../datasets/preparation.md).
2. Rebuild accepted-only conversions if review decisions changed after conversion.
3. Stop recording. Prepare [one terminal](../../terminal_commands.md) with Python
   3.8 `Xtrainer` activated, the full dependencies installed, and CUDA available.
4. Choose the exact registered project, such as `poly_mailer_bottom`,
   `envelope_top`, or `carton_front`. Keep custom projects registered for the
   correct medium in `scripts/scripts_config.py`.
5. Choose a fresh checkpoint directory for this run. No robot server is needed.

## 2. Start training

```bash
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name poly_mailer_bottom --ckpt_dir ./ckpt/poly_mailer_bottom_vendor \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

Replace the task and checkpoint directory together for another collection.
Keep underscore option names, such as `--task_name`. Reduce `--batch_size` if
GPU memory is insufficient. Set `--validate_every 100` or `--save_every 1000`
when different validation/checkpoint intervals are needed, and record your seed.

## 3. Keep and evaluate the saved model

Keep `config.pkl`, `dataset_stats.pkl`, and `policy_best.ckpt` together in the
checkpoint directory. Keep its saved task registered for the requested medium.
Follow [cycle evaluation](../runtime/evaluation.md) with `--backend vendor` and
the checkpoint directory. Use the [ACT/DP workflow](act_dp.md#1-build-a-dataset-and-freeze-its-split)
when selecting several prepared collections for matched training.
