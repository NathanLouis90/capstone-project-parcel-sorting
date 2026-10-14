# Policy B: sort from staging into a bin

Policy B uses only the right arm to pick up a staged parcel, release it into the chosen bin and return home. The left arm stays home with its gripper closed. Both arms and grippers start and finish at home/closed.

The intended final model handles all three parcel types and both bins. It receives the destination throughout the episode: `[1, 0]` means bin 0 and `[0, 1]` means bin 1. The barcode scanner itself is not a model input.

Record each bin in its own folder. You can then combine both bins when training through robomimic. The Dobot ACT software cannot use the bin input, so its current robot tests need a separate checkpoint for each bin.

## 1. Choose a folder and destination

Replace the example values below, then paste and run this block in a Bash terminal at the repository root with `Xtrainer` activated. These lines only set terminal variables. Run later Bash blocks in that same terminal; set the variables again if you open another:

```bash
SET_ID="set01"
MEDIUM="poly_mailer"
BIN=0
PROJECT="${SET_ID}_${MEDIUM}_B_bin_${BIN}"
```

Choose any collection size or `SET_ID`. `MEDIUM` must be `poly_mailer`, `carton` or `envelope`; `BIN` must be `0` or `1`. For existing recordings, set `PROJECT` directly to their actual folder name.

Complete [hardware setup](../../README.md#software-setup), start the robot server in another terminal, and follow the [recording guide](recording_guide.md). Synchronize only the right arm.

## 2. Record

Place the parcel at staging. Envelopes need an overhanging edge so the right gripper can grab them without sliding. The label must match the chosen bin: DEST-A for bin 0 or DEST-B for bin 1.

```bash
python3 experiments/run_control.py --show-img \
  --project-name "$PROJECT" --policy-stage B --medium "$MEDIUM" \
  --demonstrated-bin "$BIN" --no-capture-barcode
```

Start and stop each episode with green button press/releases. Demonstrate placement in the selected bin. With scanner capture off, the recorder saves the bin you specified; it cannot check the physical label or where you placed the parcel.

Repeat with `BIN=1` and update `PROJECT` before starting the other bin's recorder. Aim for roughly equal accepted counts in both bins for every parcel type. A [link to the preceding A episode](recording_guide.md#optional-link-between-a-and-b) is optional.

## 3. Register, review and prepare

Edit `scripts/scripts_config.py` and paste the Python entry below inside its existing `PREPARE_ACT_DATASETS["projects"]` dictionary. Replace the key, medium and bin to match your recording. This is a file edit; do not paste it into the terminal:

```python
"set01_poly_mailer_B_bin_0": {
    "policy_stage": "B",
    "medium": "poly_mailer",
    "bin_index": 0,
    "episode_len": 400,
    "train_ratio": 0.8,
    "camera_names": ["top", "left_wrist", "right_wrist"],
},
```

Register the other bin separately with `bin_index=1`. Choose recording limits from your actual episode lengths. Follow [dataset preparation](dataset_preparation.md) to review, accept and convert episodes in each project:

```bash
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT"
# After reviewing and accepting individual episodes:
python3 scripts/prepare_act_datasets.py --dataset-name "$PROJECT" --convert
```

## 4. Train

For a model that can run the robot now, train this bin's Dobot ACT checkpoint. Run the whole block below in the same Bash terminal: its first line sets `CHECKPOINT_DIR`, then the next command starts training. Choose a fresh directory for each run:

```bash
CHECKPOINT_DIR="./ckpt/act_${PROJECT}"
PYTHONPATH=. MPLBACKEND=Agg python3 ModelTrain/model_train.py \
  --task_name "$PROJECT" --ckpt_dir "$CHECKPOINT_DIR" \
  --batch_size 8 --num_steps 30000 --lr 2e-5 \
  --chunk_size 45 --kl_weight 10 --seed 0
```

Repeat for the other bin with its own project and checkpoint directory. See [Dobot ACT training](act_training.md) to add more demonstrations of the same task. Do not mix both bins in this trainer: it has no destination input to tell them apart.

For one B model that selects either bin, combine B projects using `policy_B_conditioned` in the [ACT/DP guide](act_dp_training.md). The dataset must include both bins. Before robot deployment becomes available for those models, use recorded episodes to check whether changing only the requested bin changes their predictions. The shared guide explains that check.

## 5. Run and evaluate the Dobot ACT model

Follow [inference setup](inference_evaluation.md#run-a-dobot-act-model), home both arms and place the parcel at staging. Select the checkpoint trained for the intended bin:

```bash
PYTHONPATH=. python3 experiments/run_inference.py \
  --task-name "$PROJECT" --checkpoint-dir "$CHECKPOINT_DIR" \
  --model-name policy_best.ckpt --show-img
```

Count success only if the right arm grasps the parcel, releases it inside the intended bin and returns home while the left stays home/closed. Wrong-bin placement and manual help are failures. Record results separately for each parcel type and bin using the [evaluation guide](inference_evaluation.md#record-the-result).

Automatic A-to-B switching and scanner-based checkpoint selection are not implemented. Running the two stages manually tests each stage; it does not demonstrate an autonomous full cycle.
