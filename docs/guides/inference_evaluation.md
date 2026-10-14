# Inference and evaluation

A model succeeds only when the parcel reaches the required physical state. Validation loss and offline predictions are diagnostic evidence. This repository currently supports supervised single-stage real-robot trials with vendor ACT checkpoints, and offline evaluation with robomimic ACT/DP checkpoints. The conditioned robomimic robot runtime and autonomous A-to-B supervisor are not implemented.

## Choose the checkpoint path

| Checkpoint | Available evaluation | Entry point |
| --- | --- | --- |
| Vendor ACT `.ckpt`, with matching `config.pkl` and `dataset_stats.pkl` | Supervised real-robot A or specialist B-bin trial | `experiments/run_inference.py` |
| Robomimic ACT/DP `.pth` | Held-out predictions and conditioned-B destination swap | `scripts/check_destination_swap.py` |

Use [vendor training](act_training.md) for early shakedown or the separate B-bin baseline. Use [robomimic training](diffusion_policy_training.md) for the main unified A / conditioned B comparison. Do not pass one framework's checkpoint to the other runtime. Keep the training dataset, frozen split, configuration and normalization statistics with each checkpoint.

## Offline checks first

Run hardware-free checks without starting the robot server:

```bash
conda activate Xtrainer
python3 -m pytest -q tests
python3 experiments/run_inference.py --help
python3 scripts/prepare_act_datasets.py --dataset-name first_set_poly_mailer_A
```

Confirm accepted demonstrations start/end near home, idle arms stay home/closed, and their measured rate is near 25 Hz. Review timing warnings: historical recordings may have been captured faster than the now-paced loop. Do not assume a model trained on those recordings will reproduce the same physical speed at 25 Hz.

For a conditioned B `.pth`, run the [destination-swap check](diffusion_policy_training.md#offline-destination-swap-check) on held-out episodes. Investigate a small right-arm swap response, high action error or inference latency exceeding 40 ms. Averages can hide slow chunk-generation steps; the real-robot runtime reports each overrun. Offline swap results are diagnostic, not a physical success rate.

## Prepare a supervised vendor trial

1. Register the parcel task in `PREPARE_ACT_DATASETS["projects"]` with the correct stage, medium, bin and training `episode_len`. Keep the matching camera framing/flips and checkpoint files. The runner refuses unregistered parcel metadata, missing checkpoint files and a rollout longer than the configured training horizon. Verify the task's horizon also matches the saved checkpoint training configuration; selecting a task does not automatically prove that correspondence.
2. Clear the workspace and keep the physical emergency stop within reach. Stop recording, camera preview and other camera owners. Start the robot server in its own terminal using `python3 experiments/launch_nodes.py`; startup accesses hardware and can move followers/cycle grippers.
3. Home both followers using the [terminal robot guide](robot_home_guide.md), following its explicit motion flags. Confirm both grippers closed. Place A's parcel at receiving, or B's parcel at staging. Stage envelopes with an overhanging edge.
4. Verify `RUN_INFERENCE["robot_types"]` matches each actual controller before relying on forward kinematics. Configure limits only from reviewed geometry. The legacy width formula conflicts with driver commands; inference checks the full possible jaw span conservatively. FK endpoint bounds do not prove that an entire motion path is collision-free.
5. Confirm the initial gripper observations match your recordings. Defaults are `[0.99114583, 0.97942708]`, measured from existing first frames; the closed command is `1.0`. The driver does not provide trustworthy live gripper observations through its joint-state getter. New calibration/datasets may require updating these values.

Launch one explicitly chosen A checkpoint:

```bash
PYTHONPATH=. python3 experiments/run_inference.py \
  --task-name first_set_poly_mailer_A \
  --checkpoint-dir ./ckpt/act_first_set_poly_mailer_A \
  --model-name policy_best.ckpt --episode-len 400 --show-img
```

For the vendor B-bin-0 baseline, choose its corresponding trained task/checkpoint:

```bash
PYTHONPATH=. python3 experiments/run_inference.py \
  --task-name first_set_poly_mailer_B_bin_0 \
  --checkpoint-dir ./ckpt/act_first_set_poly_mailer_B_bin_0 \
  --model-name policy_best.ckpt --episode-len 400 --show-img
```

Use B-bin-1's matching files for bin 1. This baseline selects a checkpoint manually; it does not feed destination into the vendor model. Envelope A uses both arms; mailer/carton A enables only the left arm, and B enables only the right. The unused arm's predictions are ignored and its target remains home/closed. Both followers are checked for home before launch. Model loading happens before camera/robot access.

Recording and inference share `CONTROL["control_period_ms"] = 40` in `experiments/experiments_config.py`. Every iteration sleeps for its remaining period or warns on an overrun. Review videos use the same period. Inference prints step/overrun totals on exit. It checks finite action shape, absolute joint increments, J3/J4 limits and commanded jaw-tip workspace bounds before policy motion. A failure stops further policy commands; it does not trigger automatic recovery or guarantee an immediate hardware emergency stop. Use the physical stop when required.

Press `q` in the preview to end a supervised rollout. Use Ctrl+C to interrupt the process. A finished horizon only means the loop ended: inspect the parcel and arm positions before recovery. The runner does not return home automatically after a trial, and a software interruption does not replace the hardware stop procedure.

## Score physical trials

Fix the evaluation protocol before comparing algorithms: same held-out parcels, media/bin balance, starting-pose distribution, cameras, control period and trial count. Keep evaluation parcels/demonstrations outside training. Use a consistent number of trials in every medium × destination cell and record all attempts, including safety stops, no-reads and timeouts. A failed attempt followed by a recovery is not an autonomous success.

For A, count success only when the parcel is acquired, the label is presented without searching/wiggling, the parcel is released correctly at staging and both arms return home. Envelope staging must leave a graspable overhanging edge. Report scan read success separately when the scanner is used.

For B, count success only when the right arm grasps the staged parcel, releases it inside the intended bin and returns home while the left remains home/closed. Report correct-bin success by medium and bin. Wrong-bin placement is a failure even if pickup succeeded.

For a future complete A-to-B cycle, additionally require a valid scan, reset of both arms/grippers to the training state, a reset of B's policy buffers and the correct fixed destination. No-read cycles must stop without guessing. Until that supervisor and the robomimic robot adapter exist, manual A/B switching measures stage performance rather than autonomous full-cycle success.

Keep a CSV outside tracked source files, for example `ckpt/evaluation/trials.csv`, with:

```text
trial_id,cycle_id,algorithm,checkpoint,policy_stage,medium,intended_bin,scan_token,scan_valid,grasp_success,staging_success,overhang_ok,correct_bin,release_success,returned_home,idle_arm_ok,duration_s,steps,overruns,operator_intervention,outcome,failure_reason
```

Compute success as successful trials divided by all attempted trials. Report numerator/denominator per medium/bin, overall success, intervention rate, no-read rate, wrong-bin rate, timing and overrun counts. Keep physical evaluation videos and failed trials for review. Compare specialist A only as the O6 ablation and separate B-bin policies as the baseline.
