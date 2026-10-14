# Policy A: receive, present the label, and stage

Policy A moves a parcel from receiving to the barcode station, releases it at staging, and returns home. The intended final model handles poly mailer bags, carton boxes and envelopes. Current early tests use poly mailer bags; the other two parcel types will be added later.

| Parcel type | Demonstration order |
| --- | --- |
| Poly mailer bag or carton box | The left arm picks up, presents the label, stages the parcel and returns home. The right arm stays home with its gripper closed. |
| Envelope | The left arm slides an edge toward the right arm and returns home. After a short pause, the right arm grabs the edge, presents the label, stages the envelope with an overhanging edge and returns home. |

For envelopes, the arms move one after the other, never simultaneously. Start and finish every episode with both arms home and both grippers closed. Keep unused arms unsynchronized.

## 1. Choose a recording folder

Replace the example values below, then paste and run this block in a Bash terminal at the repository root with `Xtrainer` activated. These lines only set terminal variables. Run later Bash blocks in that same terminal; set the variables again if you open another:

```bash
SET_ID="set01"
MEDIUM="poly_mailer"
PROJECT="${SET_ID}_${MEDIUM}_A"
```

Choose any `SET_ID`; `MEDIUM` must be `poly_mailer`, `carton` or `envelope`. `set01` is a label, not a requirement to collect 25 episodes. For existing data, set `PROJECT` directly to the existing folder name; no folder renaming is needed.

Complete [hardware setup](../../README.md#software-setup) and leave the robot server running in another terminal. Use the [recording guide](recording_guide.md) for leader alignment and button operation.

## 2. Record

```bash
python3 experiments/run_control.py --show-img \
  --project-name "$PROJECT" --policy-stage A --medium "$MEDIUM" \
  --no-capture-barcode
```

Use green button press/releases to start and stop each episode. Present the label steadily at the scanner; do not search or wiggle. Scanner capture is optional during demonstrations. To save actual reads, use the [barcode guide](barcode_scanning_guide.md).

## 3. Register, review and prepare

Edit `scripts/scripts_config.py` and paste the Python entry below inside its existing `PREPARE_ACT_DATASETS["projects"]` dictionary. Replace the key and medium to match your terminal values. This is a file edit; do not paste it into the terminal:

```python
"set01_poly_mailer_A": {
    "policy_stage": "A",
    "medium": "poly_mailer",
    "bin_index": None,
    "episode_len": 400,
    "train_ratio": 0.8,
    "camera_names": ["top", "left_wrist", "right_wrist"],
},
```

Choose `episode_len` from the length of your demonstrations. Follow [dataset preparation](dataset_preparation.md) to check episodes, use one-key video review to accept/reject them, and convert accepted episodes. Existing converted files get their review status synchronized automatically:

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT"
# Only if the project has not already been converted:
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT" --convert
```

## 4. Train

For the current robot test, train with the Dobot ACT software. Run the whole block below in the same Bash terminal. The first line sets `CHECKPOINT_DIR`; the next command starts training. Choose a fresh directory for each run:

```bash
CHECKPOINT_DIR="./ckpt/act_${PROJECT}"
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name "$PROJECT" --ckpt_dir "$CHECKPOINT_DIR" \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

See [Dobot ACT training](act_training.md) for settings and how to train with several recording folders. That supports your 25, 50, 75 and 100-recording tests; choose other counts if useful. Those labels count recorded demonstrations, including any held aside for validation. Rejected episodes do not reach training.

For the final ACT/DP comparison, combine the A projects you want to include using `policy_A_unified` in the [ACT/DP guide](act_dp_training.md). Include all three parcel types once their data is ready. A dataset containing only poly mailers is an early test, not evidence that the model handles cartons or envelopes. Models trained through this route cannot yet run the robot.

## 5. Run and evaluate the Dobot ACT model

Stop the recorder and follow the [inference setup](inference_evaluation.md#run-a-dobot-act-model). Home both arms and place the parcel at receiving. Use the same variables, or set them again in a new terminal:

```bash
PYTHONPATH=. python3 experiments/run_inference.py \
  --task-name "$PROJECT" --checkpoint-dir "$CHECKPOINT_DIR" \
  --model-name policy_best.ckpt --show-img
```

The run length defaults to the registered task's `episode_len`. It does not detect task completion automatically. Keep access to the emergency stop and inspect the result.

Count success only if the parcel is picked up, its label is presented steadily, it is released correctly at staging, and both arms return home. For envelopes, require the overhanging edge. Measure barcode-read success separately when using the scanner. Log failures and any manual help, using the [evaluation guide](inference_evaluation.md#record-the-result).
