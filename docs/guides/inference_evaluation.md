# Run a model and evaluate the result

**Inference** means using a trained model to predict the robot's next actions. **Evaluation** means measuring whether those actions complete the parcel task.

| Checkpoint | What you can do now |
| --- | --- |
| Dobot ACT `.ckpt`, with its matching `config.pkl` and `dataset_stats.pkl` | Run one task on the real robot |
| Robomimic ACT/DP `.pth` | Check predictions using recorded data; robot deployment is not implemented |

Use the [Policy A guide](policy_a.md) or [Policy B guide](policy_b.md) for task-specific preparation and success criteria. Automatic switching between A and B is not implemented.

## Run a Dobot ACT model

1. Select a [registered recording or combined task](act_training.md) and its trained checkpoint. Check that the task's parcel type, bin and maximum steps match the checkpoint's training configuration.
2. Stop the recorder, camera preview and other camera owners. Start `python3 experiments/launch_nodes.py` in another terminal. Server startup accesses the robot and cycles its grippers.
3. Follow the [homing guide](robot_home_guide.md) to put both arms at home. Close both grippers. Place A's parcel at receiving or B's parcel at staging; an envelope at staging needs an overhanging edge.
4. Keep the camera positions/flips and starting pose consistent with recording. Verify `RUN_INFERENCE["robot_types"]` matches your robot before relying on its position checks. Stay near the physical emergency stop throughout the test.

Replace the example task and checkpoint directory, then paste the entire block into a Bash terminal at the repository root with `Xtrainer` activated. The first two lines set terminal variables; the next command starts the model on the robot. No Python-file edit is needed for this block:

```bash
TASK="your_registered_task"
CHECKPOINT_DIR="./ckpt/your_model_name"
PYTHONPATH=. python3 experiments/run_inference.py \
  --task-name "$TASK" --checkpoint-dir "$CHECKPOINT_DIR" \
  --model-name policy_best.ckpt --show-img
```

The runner loads the model, checks that both arms are at home, and runs up to the task's configured `episode_len`. An optional `--episode-len` can shorten the run but cannot exceed that limit. A completed run length is not proof that the task succeeded.

For poly mailer/carton A, only the left arm runs. Envelope A uses both arms. B uses only the right arm. Predictions for an unused arm are ignored, and its target stays home/closed. For B, select the checkpoint trained for the intended bin; this runner does not supply a bin input to the Dobot model.

Press `q` in the preview or use Ctrl+C to end the process. Neither replaces the physical emergency stop. Inspect the arms and parcel before recovery; the runner does not automatically return home after the test.

## Understand safety and timing messages

The runner refuses invalid numeric predictions, large changes in joint angle, angles outside configured limits, and proposed gripper-tip positions outside the allowed workspace. “J3/J4” refers to the third and fourth joints of each arm. A software refusal stops further policy commands; use the hardware stop for immediate emergency stopping.

Limits and initial gripper values are in `RUN_INFERENCE` in `experiments/experiments_config.py`. Existing first-frame gripper observations were `[0.99114583, 0.97942708]`; the closed command is `1.0`. Check these against new recordings/calibration. The position calculation checks the full possible jaw span because the older gripper-width formula disagrees with the driver convention. These checks do not prove an entire movement path is collision-free.

Recording and inference aim for one step every 40 ms, or 25 Hz. An **overrun** means a step took longer than 40 ms. The runner prints overruns and a total at exit. Review recordings captured at another rate before testing their models: the robot may move at a different speed from the demonstrations.

## Record the result

Choose the same test parcels, starting-pose variations and number of attempts when comparing models. Keep test examples out of training. For your data-size test, train models at the chosen milestones, such as 25/50/75/100 recorded demonstrations, then apply the same test procedure to each.

| Task | Count success only when |
| --- | --- |
| A | The parcel is picked up, the label is presented steadily, the parcel is released correctly at staging, and both arms return home. Envelopes must leave an overhanging edge. |
| B | The parcel is grasped from staging, released inside the intended bin, and the right arm returns home while the left stays home/closed. |

Record barcode-read success separately when using the scanner. Wrong-bin placement, safety stops, timeouts and manual help are failures for an autonomous attempt. Log all attempts, not only successful ones.

A useful CSV under `ckpt/evaluation/` can record:

```text
trial_id,checkpoint,accepted_recordings,training_episodes,validation_episodes,policy_stage,medium,intended_bin,scan_success,task_success,manual_help,duration_s,overruns,failure_reason
```

Report successful attempts divided by all attempts, separately for each parcel type and B bin. Keep videos of failures. Manual switching between A and B measures stage performance; it does not establish autonomous full-cycle success.

For robomimic B, the [requested-bin check](act_dp_training.md#5-check-whether-b-uses-the-requested-bin) compares predictions on recorded data after changing only the bin input. It helps diagnose whether the model uses that input; it is not a physical success test.
