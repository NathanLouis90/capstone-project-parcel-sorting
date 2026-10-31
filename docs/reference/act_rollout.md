# ACT rollout reference

Temporal ensembling and the replan interval are inference settings. The menu saves them with a model so rollout restores the chosen behaviour, but they do not change the ACT training objective or network size. Existing weights can be evaluated with ensembling on or off without retraining. Other saved settings are covered in [hyperparameters](hyperparameters.md).

## Settings

Set defaults in the training menu under **5**, **1. ACT**, **a. Advanced ACT settings** (items 9–11):

| Setting | Default | Meaning |
| --- | --- | --- |
| Temporal ensembling | off | Predict a new chunk every control step and blend the overlapping predictions for the current step. |
| Ensemble coefficient | 0.01 | Positive values favour older predictions, zero averages equally, negative values favour newer ones. |
| Replan interval when ensembling is off | 0 | 0 executes a full chunk before querying again; a positive value (at most the chunk length) executes that many steps, then predicts a fresh chunk. |

With ensembling on, the policy replans every step regardless of the stored interval. Checkpoints without these fields default to ensembling off and full-chunk execution. Changing menu defaults never rewrites existing checkpoints or running jobs.

The weighting follows the [original ACT evaluation code](https://github.com/tonyzhaozh/act/blob/main/imitate_episodes.py): predictions are ordered oldest first, with weights proportional to `exp(-coefficient * prediction_index)`. Larger positive values keep more influence from older predictions; negative coefficients test stronger emphasis on recent observations.

## Correction latency

The control period is 40 ms. With chunk length 16:

| Mode | Interval between new predictions | Effect |
| --- | --- | --- |
| Ensembling off, replan interval 0 | 16 steps, about 0.64 s | A whole chunk runs before a fresh observation affects the next prediction. |
| Ensembling off, replan interval 4 | 4 steps, about 0.16 s | Replans sooner and discards the unused tail of the previous chunk; commands can jump at chunk boundaries. |
| Ensembling on | every step, about 0.04 s | Fresh predictions are blended with older ones; corrections can be smoother but carry some history bias. |

These are desired query intervals, not end-to-end reaction times: camera age, inference, network and robot tracking add delay. Ensembling needs a forward pass every step, so check control overruns and inference time on the intended GPU.

As described in the [ACT paper](https://arxiv.org/html/2304.13705v1#S4.SS1), ensembling averages overlapping predictions for the same timestep, not consecutive executed actions. Its smoothing can affect contact timing and gripper opening and closing as well as arm motion.

## Recovery it can and cannot provide

If a bag slips or a grasp approach is offset, more frequent prediction lets the policy react to the observed state sooner, and ensembling can make the correction smoother. Older predictions can also pull against an abrupt change and delay a needed correction. Compare the modes empirically rather than assuming the smoother one recovers better.

The policy still has to have learned useful actions for the state it sees. Ensembling adds no missed-grasp detector, regrasp planner or automatic retry. Demonstrations that include good recoveries can cover states missing from otherwise clean data.

Controller alarms, tracking errors, invalid actions and timeouts still trigger the normal fault stop, and recovery after a fault is the operator's procedure (see [runtime](runtime.md)). The ensemble history resets at the start of every cycle or retry (after a prediction-only warmup) and again after a paced initial approach, so predictions from an earlier attempt never influence a new one.

## Overrides

`evaluation/check_checkpoint.py` and `evaluation/run_cycle.py` accept:

- `--act-temporal-ensemble` / `--no-act-temporal-ensemble`
- `--act-ensemble-coefficient VALUE`
- `--act-query-frequency STEPS` (replan interval with ensembling off)

Without overrides, the checkpoint's saved settings apply. The effective settings are printed at startup, for example `ACT rollout settings: {"chunk_length": 16, "coefficient": 0.01, "query_frequency": 4, "temporal_ensemble": false}`. Overrides affect only the loaded instance; the checkpoint file is unchanged. They apply to ACT checkpoints only.

The checkpoint checker loads the weights and requests predictions from synthetic observations without opening hardware, which is a quick way to confirm the effective settings:

```bash
python3 evaluation/check_checkpoint.py --medium poly_mailer --checkpoint ckpt/act_poly_mailer_v1.1/best.pth --steps 3
python3 evaluation/check_checkpoint.py --medium poly_mailer --checkpoint ckpt/act_poly_mailer_v1.1/best.pth --steps 3 \
  --no-act-temporal-ensemble --act-query-frequency 4
```

For live trials, add the same overrides to the cycle command in [run cycles](../procedures/10_run_cycles.md). Use identical held-out placements and record the rollout settings with the results. Compare grasp retention, successful corrections, contact timing, dropped parcels and control overruns as well as overall success and cycle time; training loss cannot rank inference-only choices.

Other factors that affect corrections include chunk length, learning rate, KL weight, model size and observation quality. For DP, observation history and executed action horizon govern how often fresh observations influence the next actions. Change one factor at a time; see [tuning](tuning.md).
