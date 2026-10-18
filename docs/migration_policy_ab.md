# Per-medium migration inventory

Baseline: `7b5c290`. This inventory was captured before implementation edits.
The approved design uses one pick-to-scan policy for each medium, learned flips for
flat media, scripted wrist scanning and taught joint paths for placement/recovery.

## Decisions and scope

- Preserve old code, guides, tests and configurations in `old_architecture_folder/`.
- Move existing datasets/checkpoints into ignored local archive directories without changing episode contents.
- Keep `AGENTS.md` uncommitted as requested. No existing user work is discarded.
- Teach joint waypoints per arm for common physical bin positions and receiving-area returns.
- Use operator outcome keys. Recover no-read parcels to receiving, allow one linked retry,
  and stop on faults before any operator-authorized recovery.
- Write only medium/label-face recording metadata. A compatibility reader preserves access to old episodes.
- Keep destination tokens and physical button names; they are unrelated to policy-stage names.
- Update curation invariants, FK orientation, and the explicitly named robomimic recipe generator where required.
- Hardware validation and production checkpoints remain prerequisites for live deployment.

## Planned actions by path

- `docs/`, README and old policy guides: archive original; rewrite current operating guidance.
- Recorder, metadata, preparation, configuration and tests: archive original; replace stage/destination behavior.
- Curation and review: archive original; adapt signatures and end-pose checks; preserve payload integrity checks.
- Inference and safety: archive original; medium selection and a shared validated motion loop.
- robomimic recipe generator: explicitly authorized change to per-medium observation recipes.
- Other vendor files: leave unchanged.
- Destination-swap diagnostic: retire into the archive.
- Dataset names: preserve unchanged under the local archive; create fresh medium projects.

## Every matching source line

Each row records a baseline hit. The action is determined by the path mapping above.
Archived text intentionally retains the original vocabulary. Legacy test fixtures
belong to the archive; new compatibility fixtures are isolated in the reader tests.

| Baseline file and line | Action | Original text |
| --- | --- | --- |
| `ModelTrain/constants.py:64` | archive and rewrite/adapt | 'policy_stage': project['policy_stage'], |
| `ModelTrain/detr/models/detr_vae.py:123` | keep vendor | binaries = F.one_hot(torch.multinomial(probs.view(-1, self.vq_dim), 1).squeeze(-1), self.vq_dim).view(-1, self.vq_class, self.vq_dim).float() |
| `ModelTrain/detr/models/latent_model.py:69` | keep vendor | samples_one_hot = F.one_hot(samples.long(), num_classes=self.output_dim).float() |
| `ModelTrain/detr/models/latent_model.py:70` | keep vendor | x = torch.cat([x, samples_one_hot[:, None, :]], dim=1) |
| `README.md:7` | archive and rewrite/adapt | Arrange the receiving area, barcode reading station, staging area and destination bins within the robot's working area. The following items support demonstration recording and parcel pick-and-place tasks. |
| `README.md:12` | archive and rewrite/adapt | \| DL envelopes \| Thin parcels used to demonstrate and evaluate envelope pickup, staging and sorting \| Dimensions, material and Shopee/Lazada link: to add \| |
| `README.md:13` | archive and rewrite/adapt | \| Poly mailer bags \| Used to record and test pickup, staging and sorting of poly mailer bags \| Dimensions, material and Shopee/Lazada link: to add \| |
| `README.md:14` | archive and rewrite/adapt | \| Carton boxes \| Rigid parcels used to demonstrate and evaluate box pickup, staging and sorting \| Dimensions, material and Shopee/Lazada link: to add \| |
| `README.md:15` | archive and rewrite/adapt | \| Storage bins (elevated platforms) \| Provide raised receiving and staging surfaces: parcels start at the receiving area and rest at staging between Policy A and Policy B \| Quantity, dimensions, height, placement and Shopee/Lazada link: to add \| |
| `README.md:50` | archive and rewrite/adapt | **Policy A moves a parcel from receiving to the scanner, then to staging.** Poly mailer bags and carton boxes use only the left arm. Envelopes use both arms: the left slides the envelope and returns home; the right then grabs it, presents the label and places it at staging with an edge overhanging. |
| `README.md:52` | archive and rewrite/adapt | **Policy B moves the staged parcel into bin 0 or bin 1 using only the right arm.** It is given the chosen bin at every step. Any unused arm stays home with its gripper closed. Both policies start and finish at home. |
| `README.md:93` | archive and rewrite/adapt | 6. **Start the recorder.** In terminal 2, activate the same environment, enter the repository root, and run \`python3 experiments/run_control.py --show-img\` with your chosen recording arguments. Choose the recorder command from the [Policy A](docs/guides/policy_a.md) or [Policy B](docs/guides/policy_b.md) guide; the [recording guide](docs/guides/recording_guide.md) explains button operation. |
| `README.md:99` | archive and rewrite/adapt | Follow the [Policy A guide](docs/guides/policy_a.md) or [Policy B guide](docs/guides/policy_b.md) from recording through evaluation. Each guide explains which arm to use, how to name recording folders, and which training route to choose. |
| `README.md:109` | archive and rewrite/adapt | The robot runner currently supports Dobot ACT checkpoints. Models trained through robomimic can be checked using recorded data, but cannot yet run the robot. Automatic switching from Policy A to Policy B is also not implemented. |
| `barcode_scanning/dataset_metadata.py:17` | archive and rewrite/adapt | if metadata.get('policy_stage') not in ('A', 'B'): |
| `barcode_scanning/dataset_metadata.py:34` | archive and rewrite/adapt | if metadata['policy_stage'] == 'B': |
| `barcode_scanning/dataset_metadata.py:38` | archive and rewrite/adapt | raise ValueError('Policy B requires a valid destination label') |
| `barcode_scanning/dataset_metadata.py:39` | archive and rewrite/adapt | if metadata.get('demonstrated_bin') != destination['bin_index']: |
| `barcode_scanning/dataset_metadata.py:40` | archive and rewrite/adapt | raise ValueError('Policy B demonstrated bin differs from its destination') |
| `barcode_scanning/dataset_metadata.py:48` | archive and rewrite/adapt | root.attrs['policy_stage'] = metadata['policy_stage'] |
| `barcode_scanning/dataset_metadata.py:56` | archive and rewrite/adapt | if metadata['policy_stage'] == 'B': |
| `barcode_scanning/recording.py:4` | archive and rewrite/adapt | still required to confirm staging and placement before demonstrations are used. |
| `barcode_scanning/recording.py:32` | archive and rewrite/adapt | def load_source_episode(path, medium, demonstrated_bin): |
| `barcode_scanning/recording.py:38` | archive and rewrite/adapt | if (metadata.get('policy_stage') != 'A' or not metadata.get('recording_complete') |
| `barcode_scanning/recording.py:40` | archive and rewrite/adapt | raise ValueError('Source must be a completed Policy A recording') |
| `barcode_scanning/recording.py:52` | archive and rewrite/adapt | if type(demonstrated_bin) is not int or demonstrated_bin != scan['bin_index']: |
| `barcode_scanning/recording.py:53` | archive and rewrite/adapt | raise ValueError('--demonstrated-bin must match scanned bin {}'.format(scan['bin_index'])) |
| `barcode_scanning/recording.py:57` | archive and rewrite/adapt | if type(demonstrated_bin) is not int or demonstrated_bin not in mapping.values(): |
| `barcode_scanning/recording.py:58` | archive and rewrite/adapt | raise ValueError('Choose --demonstrated-bin from the configured destination bins') |
| `barcode_scanning/recording.py:64` | archive and rewrite/adapt | def __init__(self, stage, medium, scan_window_s=30, source_episode=None, |
| `barcode_scanning/recording.py:65` | archive and rewrite/adapt | demonstrated_bin=None, window=None, capture_barcode=False): |
| `barcode_scanning/recording.py:73` | archive and rewrite/adapt | raise ValueError('Policy B labels its destination manually or inherits A; it does not capture scans') |
| `barcode_scanning/recording.py:81` | archive and rewrite/adapt | if source_episode is not None: |
| `barcode_scanning/recording.py:82` | archive and rewrite/adapt | self.source = load_source_episode(source_episode, medium, demonstrated_bin) |
| `barcode_scanning/recording.py:83` | archive and rewrite/adapt | elif type(demonstrated_bin) is not int or demonstrated_bin not in destination_mapping().values(): |
| `barcode_scanning/recording.py:84` | archive and rewrite/adapt | raise ValueError('Policy B requires a configured --demonstrated-bin, e.g. 0 or 1') |
| `barcode_scanning/recording.py:85` | archive and rewrite/adapt | elif source_episode is not None or demonstrated_bin is not None: |
| `barcode_scanning/recording.py:86` | archive and rewrite/adapt | raise ValueError('--source-episode and --demonstrated-bin apply only to Policy B') |
| `barcode_scanning/recording.py:87` | archive and rewrite/adapt | self.demonstrated_bin = demonstrated_bin |
| `barcode_scanning/recording.py:105` | archive and rewrite/adapt | 'policy_stage': self.stage, 'medium': self.medium, |
| `barcode_scanning/recording.py:110` | archive and rewrite/adapt | 'source_episode_id': None if self.source is None else self.source['episode_id'], |
| `barcode_scanning/recording.py:112` | archive and rewrite/adapt | 'demonstrated_bin': self.demonstrated_bin, |
| `barcode_scanning/recording.py:119` | archive and rewrite/adapt | 'bin_index': self.demonstrated_bin, |
| `barcode_scanning/recording.py:220` | archive and rewrite/adapt | return {'episode': str(episode_dir), 'policy_stage': metadata['policy_stage'], |
| `docs/guides/act_dp_training.md:3` | archive and rewrite/adapt | Use this route to compare ACT and Diffusion Policy, or to train one Policy B model that takes the chosen bin as an input. Both algorithms use the same camera images and joint states. Joint values are scaled in the same way, and the same recordings are reserved for validation instead of training. |
| `docs/guides/act_dp_training.md:5` | archive and rewrite/adapt | These models can currently be checked with recorded data only. To train a model that can run the robot now, use [Dobot ACT training](act_training.md). Start with the [Policy A](policy_a.md) or [Policy B](policy_b.md) guide to record and [prepare your data](dataset_preparation.md). |
| `docs/guides/act_dp_training.md:25` | archive and rewrite/adapt | \| \`policy_A_unified\` \| One A model from the chosen A projects, across parcel types \| |
| `docs/guides/act_dp_training.md:26` | archive and rewrite/adapt | \| \`policy_B_conditioned\` \| One B model from both bins; the chosen bin is an extra model input \| |
| `docs/guides/act_dp_training.md:27` | archive and rewrite/adapt | \| \`policy_A_poly_mailer\`, \`policy_A_carton\`, \`policy_A_envelope\` \| Optional A comparisons using just one parcel type \| |
| `docs/guides/act_dp_training.md:28` | archive and rewrite/adapt | \| \`policy_B_bin_0\`, \`policy_B_bin_1\` \| Optional B comparisons using only one bin, without a bin input \| |
| `docs/guides/act_dp_training.md:37` | archive and rewrite/adapt | RECIPE="policy_A_unified" |
| `docs/guides/act_dp_training.md:45` | archive and rewrite/adapt | For B, change the first line to \`RECIPE="policy_B_conditioned"\` and list B projects from both bins. Run this variable block first, then the conversion command in the **same terminal**. It only sets variables; it does not convert data or start training. Run the block again in a new terminal, or after changing \`DATASET_NAME\` so its derived paths update. |
| `docs/guides/act_dp_training.md:72` | archive and rewrite/adapt | --recipe policy_A_unified --projects datasets/your_recording_folder \ |
| `docs/guides/act_dp_training.md:81` | archive and rewrite/adapt | The converter combines accepted episodes, turns compressed camera images into RGB images, and keeps the joint states and demonstrated actions. B's bin input stays constant throughout an episode: \`[1, 0]\` for bin 0 or \`[0, 1]\` for bin 1. It refuses a conditioned-B dataset with only one bin. |
| `docs/guides/act_dp_training.md:112` | archive and rewrite/adapt | The configs select all three cameras and joint positions. Conditioned B adds the destination input. Validation uses scaling values measured from the training recordings, so validation data does not influence them. |
| `docs/guides/act_dp_training.md:133` | archive and rewrite/adapt | This check applies only to \`policy_B_conditioned\`. Replace the example checkpoint path with a saved \`.pth\` from either trained algorithm, then run the whole block in the same Bash terminal. The first line sets \`CHECKPOINT\`; the next command performs the check: |
| `docs/guides/act_training.md:9` | archive and rewrite/adapt | Follow the [Policy A guide](policy_a.md) or [Policy B guide](policy_b.md) to record, register and prepare a project. Any folder name and collection size are allowed. An optional naming pattern is \`<set_id>_<medium>_<policy_stage>\`, with \`_bin_<number>\` added for B. |
| `docs/guides/act_training.md:48` | archive and rewrite/adapt | Outputs include \`policy_best.ckpt\`, \`policy_last.ckpt\`, \`config.pkl\`, \`dataset_stats.pkl\` and loss plots. Keep the configuration and statistics with the checkpoint. A low validation loss does not prove physical task success. This trainer reads all HDF5 files in its training folder; if review rejects an already-converted episode, rebuild an accepted-only project before retraining. |
| `docs/guides/act_training.md:63` | archive and rewrite/adapt | ("policy_stage", "medium", "bin_index", "camera_names")) |
| `docs/guides/act_training.md:69` | archive and rewrite/adapt | "policy_stage": settings["policy_stage"], |
| `docs/guides/act_training.md:85` | archive and rewrite/adapt | For B, this trainer does not read the destination input. Train and select a separate checkpoint for each bin. Use robomimic when you need one B model that takes the chosen bin as an input. For the eventual A model across all three parcel types, follow the \`policy_A_unified\` workflow in the shared guide. |
| `docs/guides/barcode_scanning_guide.md:3` | archive and rewrite/adapt | This guide covers the dedicated USB HID scanner, destination labels, standalone testing, and optional barcode capture during a demonstration. For robot startup, Policy A/B recording arguments and button steps, see the [recording guide](recording_guide.md). |
| `docs/guides/barcode_scanning_guide.md:14` | archive and rewrite/adapt | - \`experiments/run_control.py\`: existing teleoperation recorder with optional \`--policy-stage A/B\` integration. |
| `docs/guides/barcode_scanning_guide.md:104` | archive and rewrite/adapt | ## 3. Optional barcode capture during Policy A |
| `docs/guides/barcode_scanning_guide.md:112` | archive and rewrite/adapt | --policy-stage A \ |
| `docs/guides/barcode_scanning_guide.md:135` | archive and rewrite/adapt | 7. Move to staging, lower and release the parcel, and retract the active arms to home. |
| `docs/guides/barcode_scanning_guide.md:137` | archive and rewrite/adapt | 9. Disable synchronization, support/lock the leaders, and confirm the followers are stationary. Leave the parcel at its actual staging pose if collecting the paired B episode next. |
| `docs/guides/barcode_scanning_guide.md:151` | archive and rewrite/adapt | The episode ID includes microseconds to prevent rapid start/stop folder collisions. The metadata records stage, medium, cycle ID, scan window(s), accepted token/bin/time, frame count, and completion state. Task success remains \`unreviewed\`: scan acceptance does not prove grasp or staging success. |
| `docs/guides/barcode_scanning_guide.md:162` | archive and rewrite/adapt | Expect stage A, medium carton, the accepted barcode/bin, and a nonzero matching frame count. Inspection does not prove physical grasping or staging success; review the images and conversion videos. |
| `docs/guides/barcode_scanning_guide.md:164` | archive and rewrite/adapt | Record A and each B bin in separate projects; combine them for unified A and conditioned B training with robomimic. The Dobot ACT trainer needs a separate model for each B bin because it does not read a destination input. Register their names in \`scripts/scripts_config.py\`, then validate and convert as described in the [dataset preparation guide](dataset_preparation.md). Existing HDF5 files are refused; mismatched raw frames are preserved. |
| `docs/guides/barcode_scanning_guide.md:176` | archive and rewrite/adapt | --policy-stage B \ |
| `docs/guides/barcode_scanning_guide.md:178` | archive and rewrite/adapt | --source-episode datasets/barcode_test_A/collect_data/A_EPISODE_ID \ |
| `docs/guides/barcode_scanning_guide.md:179` | archive and rewrite/adapt | --demonstrated-bin 0 |
| `docs/guides/barcode_scanning_guide.md:182` | archive and rewrite/adapt | For a source scanned to bin 1, use \`--demonstrated-bin 1\` and a separate project such as \`barcode_test_B_bin_1\`. A source with missing scans, interruption, wrong medium, mapping mismatch, zero recorded frames, or scanner failure is refused before recorder robot/camera startup. The bin argument must match A's scan. It records your intended placement, not an automatic measurement of actual placement. |
| `docs/guides/barcode_scanning_guide.md:198` | archive and rewrite/adapt | Keep destination mappings fixed between paired episodes and preserve metadata when copying recordings. Balance both bins for each medium and exclude interrupted, failed-scan and wrong-bin episodes from successful paired examples. A new A recording clears old scans; select the source episode belonging to the parcel actually on staging. |
| `docs/guides/barcode_scanning_guide.md:200` | archive and rewrite/adapt | The reader can be embedded in a future supervisor, but standalone capture does not run policies. A supervisor must select A, open a scan window, verify staging/retraction and the destination, then start B. It must reset policy action queues at transitions and handle failures; elapsed time alone does not prove stage completion. Destination-conditioned training and offline checking use robomimic-r2d2. The Dobot ACT robot runner requires explicit task/checkpoint selection; robomimic robot deployment and autonomous A/B handoff are not implemented. |
| `docs/guides/dataset_curation.md:163` | archive and rewrite/adapt | The exceptional folder is \`preliminary_carton_B/collect_data/20261015102831505618_update_policy\`. Its metadata still records \`episode_id: "20261015102831505618"\`, stage A, no demonstrated bin and no destination. Renaming a directory does not update its stage or episode ID. The counter reads metadata, so its A,B result is accurate. Metadata cannot establish which physical task was demonstrated; watch the recording before deciding how to repair or exclude it. Curation does not automatically relabel these files, and the ID mismatch must be resolved before normal review/transfer can accept that episode. |
| `docs/guides/dataset_curation.md:165` | archive and rewrite/adapt | Future carton recording commands must specify both \`--policy-stage A\` or \`B\` and \`--medium carton\`, plus the intended \`--demonstrated-bin\` for B. No recorder CLI changes are required. |
| `docs/guides/dataset_curation.md:167` | archive and rewrite/adapt | Follow-up correction on 17 October 2026: the operator confirmed that the exceptional episode demonstrates a carton placed into bin 0 using Policy B. Its metadata now records B/carton/manual bin 0, and its folder was restored to \`20261015102831505618\` to match the original episode ID. Original metadata is backed up in the project's \`.metadata_backups/\`; before/after metadata and file hashes are recorded in \`curation_log.jsonl\`. All 844 observation/image files are unchanged. The project has a stale marker for fresh rebuilding, and the episode remains unreviewed. Other preliminary carton episodes still require their recorded medium to be checked. |
| `docs/guides/dataset_curation.md:174` | archive and rewrite/adapt | --policy-stage B --medium carton --demonstrated-bin 0 |
| `docs/guides/dataset_curation.md:177` | archive and rewrite/adapt | For bin 1, change both the project suffix and \`--demonstrated-bin\` to \`1\`. Stop and restart the recorder to change stage, medium or bin. Recording-button presses do not change these settings. For Policy A, use \`--policy-stage A\`, an A project name, and omit \`--demonstrated-bin\`. |
| `docs/guides/dataset_curation.md:179` | archive and rewrite/adapt | For a saved metadata mistake, back up \`episode_metadata.json\` outside the active episode folders first. Correct \`policy_stage\`, \`medium\`, \`demonstrated_bin\`, the manual \`destination\` object (\`bin_index\`, \`source\`, correction-time \`recorded_at\`), and \`destination_resolved\` together. Preserve original timestamps, cycle ID, observations/images and review status, and keep the directory name equal to \`episode_id\`. Do not invent a scan or A-source pairing. Log the correction and mark previous conversions stale; if conversions already exist, rebuild into a fresh project rather than changing raw metadata alone and reusing those HDF5 files. |
| `docs/guides/dataset_curation.md:187` | archive and rewrite/adapt | \| \`policy_stage\`, \`medium\`, \`bin_index\`, \`camera_names\` or \`control_period_ms mismatch\` \| Select recordings of the same task/setup/rate; inspect recorded metadata rather than trusting folder names. \| |
| `docs/guides/dataset_preparation.md:3` | archive and rewrite/adapt | Use this guide after recording with [Policy A](policy_a.md) or [Policy B](policy_b.md). Run \`bash\` blocks in a Bash terminal from the repository root with \`Xtrainer\` activated. Replace example values, then run assignments and commands in order in that same terminal; repeat assignments in a new terminal. No robot connection is needed. |
| `docs/guides/dataset_preparation.md:13` | archive and rewrite/adapt | \| \`policy_stage\` \| \`A\` or \`B\`, matching the recorded task \| |
| `docs/guides/diffusion_policy_training.md:3` | archive and rewrite/adapt | Use [ACT and Diffusion Policy training](act_dp_training.md). It covers both algorithms, dataset combination and checking whether Policy B uses the requested bin. |
| `docs/guides/inference_evaluation.md:10` | archive and rewrite/adapt | Use the [Policy A guide](policy_a.md) or [Policy B guide](policy_b.md) for task-specific preparation and success criteria. Automatic switching between A and B is not implemented. |
| `docs/guides/inference_evaluation.md:16` | archive and rewrite/adapt | 3. Follow the [homing guide](robot_home_guide.md) to put both arms at home. Close both grippers. Place A's parcel at receiving or B's parcel at staging; an envelope at staging needs an overhanging edge. |
| `docs/guides/inference_evaluation.md:26` | archive and rewrite/adapt | --model-name policy_best.ckpt --show-img |
| `docs/guides/inference_evaluation.md:49` | archive and rewrite/adapt | \| A \| The parcel is picked up, the label is presented steadily, the parcel is released correctly at staging, and both arms return home. Envelopes must leave an overhanging edge. \| |
| `docs/guides/inference_evaluation.md:50` | archive and rewrite/adapt | \| B \| The parcel is grasped from staging, released inside the intended bin, and the right arm returns home while the left stays home/closed. \| |
| `docs/guides/inference_evaluation.md:57` | archive and rewrite/adapt | trial_id,checkpoint,accepted_recordings,training_episodes,validation_episodes,policy_stage,medium,intended_bin,scan_success,task_success,manual_help,duration_s,overruns,failure_reason |
| `docs/guides/policy_a.md:1` | archive and rewrite/adapt | # Policy A: receive, present the label, and stage |
| `docs/guides/policy_a.md:3` | archive and rewrite/adapt | Policy A moves a parcel from receiving to the barcode station, releases it at staging, and returns home. The intended final model handles poly mailer bags, carton boxes and envelopes. Current early tests use poly mailer bags; the other two parcel types will be added later. |
| `docs/guides/policy_a.md:30` | archive and rewrite/adapt | --project-name "$PROJECT" --policy-stage A --medium "$MEDIUM" \ |
| `docs/guides/policy_a.md:42` | archive and rewrite/adapt | "policy_stage": "A", |
| `docs/guides/policy_a.md:73` | archive and rewrite/adapt | For the final ACT/DP comparison, combine the A projects you want to include using \`policy_A_unified\` in the [ACT/DP guide](act_dp_training.md). Include all three parcel types once their data is ready. A dataset containing only poly mailers is an early test, not evidence that the model handles cartons or envelopes. Models trained through this route cannot yet run the robot. |
| `docs/guides/policy_a.md:82` | archive and rewrite/adapt | --model-name policy_best.ckpt --show-img |
| `docs/guides/policy_a.md:87` | archive and rewrite/adapt | Count success only if the parcel is picked up, its label is presented steadily, it is released correctly at staging, and both arms return home. For envelopes, require the overhanging edge. Measure barcode-read success separately when using the scanner. Log failures and any manual help, using the [evaluation guide](inference_evaluation.md#record-the-result). |
| `docs/guides/policy_b.md:1` | archive and rewrite/adapt | # Policy B: sort from staging into a bin |
| `docs/guides/policy_b.md:3` | archive and rewrite/adapt | Policy B uses only the right arm to pick up a staged parcel, release it into the chosen bin and return home. The left arm stays home with its gripper closed. Both arms and grippers start and finish at home/closed. |
| `docs/guides/policy_b.md:26` | archive and rewrite/adapt | Place the parcel at staging. Envelopes need an overhanging edge so the right gripper can grab them without sliding. The label must match the chosen bin: DEST-A for bin 0 or DEST-B for bin 1. |
| `docs/guides/policy_b.md:30` | archive and rewrite/adapt | --project-name "$PROJECT" --policy-stage B --medium "$MEDIUM" \ |
| `docs/guides/policy_b.md:31` | archive and rewrite/adapt | --demonstrated-bin "$BIN" --no-capture-barcode |
| `docs/guides/policy_b.md:44` | archive and rewrite/adapt | "policy_stage": "B", |
| `docs/guides/policy_b.md:75` | archive and rewrite/adapt | For one B model that selects either bin, combine B projects using \`policy_B_conditioned\` in the [ACT/DP guide](act_dp_training.md). The dataset must include both bins. Before robot deployment becomes available for those models, use recorded episodes to check whether changing only the requested bin changes their predictions. The shared guide explains that check. |
| `docs/guides/policy_b.md:79` | archive and rewrite/adapt | Follow [inference setup](inference_evaluation.md#run-a-dobot-act-model), home both arms and place the parcel at staging. Select the checkpoint trained for the intended bin: |
| `docs/guides/policy_b.md:84` | archive and rewrite/adapt | --model-name policy_best.ckpt --show-img |
| `docs/guides/recording_guide.md:3` | archive and rewrite/adapt | Use the [Policy A guide](policy_a.md) or [Policy B guide](policy_b.md) for the task, arm selection and recorder command. This page covers shared controls and optional links between episodes. Run Bash commands in a terminal at the repository root with Python 3.8 \`Xtrainer\` activated. Variable assignments are run in that terminal; configuration changes are edits to the named Python file. See [command examples](../../README.md#how-to-use-command-examples). |
| `docs/guides/recording_guide.md:16` | archive and rewrite/adapt | \| \`--policy-stage\` \| \`A\` or \`B\`; include it so recordings contain task details needed for preparation \| |
| `docs/guides/recording_guide.md:18` | archive and rewrite/adapt | \| \`--demonstrated-bin\` \| Chosen bin, \`0\` or \`1\`, for B; omit for A \| |
| `docs/guides/recording_guide.md:22` | archive and rewrite/adapt | \| \`--source-episode\` \| Optional path to the completed A episode preceding this B recording \| |
| `docs/guides/recording_guide.md:52` | archive and rewrite/adapt | You can record independent A and B episodes. Linking them is useful when B moves the same parcel from the pose A left at staging; it is not required for training. |
| `docs/guides/recording_guide.md:54` | archive and rewrite/adapt | Add \`--source-episode "$A_EPISODE"\` to B's full recorder command, after setting \`A_EPISODE\` to the actual A episode directory. Still supply \`--demonstrated-bin\`. A must be completed, nonempty and recorded with the same parcel type. If A saved a scanner read, B's chosen bin must match it. |
| `docs/parcel_sorting_design_notes.md:7` | archive and rewrite/adapt | - Policy A is one unified policy across envelopes, poly mailers and cartons. For mailers/cartons, only the left arm picks from receiving, presents the label, places at staging and returns home. The right arm remains home with its gripper closed. |
| `docs/parcel_sorting_design_notes.md:8` | archive and rewrite/adapt | - Envelope A uses both arms sequentially. The left arm slides an edge toward the right arm and returns fully home. After a short pause, the right arm tilts, grasps the edge, presents the label, places at staging with an overhanging edge and returns home. |
| `docs/parcel_sorting_design_notes.md:9` | archive and rewrite/adapt | - Policy B is one right-arm policy across all media and both bins. Destination is a constant one-hot observation: \`[1, 0]\` for bin 0 and \`[0, 1]\` for bin 1. The left arm stays home with its gripper closed. |
| `docs/parcel_sorting_design_notes.md:11` | archive and rewrite/adapt | - Recording remains one stage/bin per project, with \`--demonstrated-bin 0\` or \`1\` for B. Projects are combined during offline conversion. The recorder CLI is unchanged. |
| `docs/parcel_sorting_design_notes.md:16` | archive and rewrite/adapt | The current comparison targets 50 and 100 accepted demonstrations. Collection sizes and folder names remain optional. Reviewed preliminary episodes may replenish the main sets, and accepted set02 episodes may move into set01. Preliminary carton folders exist but their medium/stage metadata needs correction or exclusion after physical review before reuse. Report accepted-recording and actual training/validation counts separately. See the [Policy A guide](guides/policy_a.md), [Policy B guide](guides/policy_b.md) and [Dobot ACT guide](guides/act_training.md). |
| `docs/parcel_sorting_design_notes.md:22` | archive and rewrite/adapt | A read-only carton audit found five A episodes in \`preliminary_carton_A\` and four B plus one A in \`preliminary_carton_B\`. All ten record medium \`poly_mailer\`. The B folder's \`20261015102831505618_update_policy\` records stage A and an unsuffixed episode ID, with no destination. The episode counter correctly reports A,B from metadata. No recordings have been relabelled or moved; physical task identity requires video review. See the [curation guide](guides/dataset_curation.md) for commands and recovery choices. Automatic rollout recording is outside this curation change; inference behavior and the recorder CLI are unchanged. |
| `docs/parcel_sorting_design_notes.md:38` | archive and rewrite/adapt | 3. End A after parcel release at staging and approximately 1 s with both arms near home. Use a maximum-step timeout as backup, not proof of success. |
| `docs/parcel_sorting_design_notes.md:42` | archive and rewrite/adapt | 7. Run B with the fixed destination one-hot at every step; keep the left arm home and closed. |
| `docs/parcel_sorting_design_notes.md:63` | archive and rewrite/adapt | The proposal describes Policy A placing the item at a staging point and retracting after barcode presentation. Policy B then reacquires the item from staging. Both policies begin from a fixed home configuration. Two destination bins use a one-hot destination signal held constant throughout each Policy B episode. The media are a thin envelope, filled poly mailer, and small rigid carton. ACT and Diffusion Policy comparisons and a unified Policy A ablation are proposed; these are not confirmed implementation commitments. |
| `docs/parcel_sorting_design_notes.md:65` | archive and rewrite/adapt | The proposal mentions serial scanner integration. Actual reported scanner behaviour suggests USB HID keyboard mode, so serial availability must be verified rather than assumed. The staging step and exact policy handoff remain open to revision. |
| `docs/parcel_sorting_design_notes.md:75` | archive and rewrite/adapt | - \`ModelTrain/detr/models/detr_vae.py\` hardcodes a 14-dimensional state in its model builder. Destination conditioning requires corresponding dataset, loader, model, and inference changes, followed by training. |
| `docs/parcel_sorting_design_notes.md:86` | archive and rewrite/adapt | A supervisor should own each item cycle, select the Policy A model from a known medium selection, arm a scan window, validate the complete token against the configured mapping, and associate the accepted scan with the active cycle. Reject unknown or conflicting tokens. Deduplicate repeated scans within a cycle, but allow the same destination on successive items. A destination barcode alone cannot prove unique item identity. |
| `docs/parcel_sorting_design_notes.md:88` | archive and rewrite/adapt | With staging retained, start Policy B only after both a valid destination and a successful staging/retraction handoff. Convert bin 0 to \`[1, 0]\` and bin 1 to \`[0, 1]\`, freeze that signal for the episode, and reset model action buffers and episode state at policy transitions. Stop or use an explicitly designed recovery path on scan timeout or failed handoff; do not choose a default bin. |
| `docs/parcel_sorting_design_notes.md:90` | archive and rewrite/adapt | Store paired A/B episode IDs, medium, raw barcode, destination index, scan timing, mapping version, and per-stage outcomes in dataset metadata. Supply destination conditioning consistently during Policy B training and inference. Balance each medium across destinations, vary item poses, and test destination use with controlled destination swaps to detect visual shortcuts. |
| `docs/parcel_sorting_design_notes.md:92` | archive and rewrite/adapt | Open issues include scanner identity/mode/terminator, input permissions and stable device selection, presentation geometry and scan dwell, stage completion detection, medium selection, staging consistency, stale scans from nearby labels, reconnect handling, recovery behaviour, and access to editable training/inference sources. |
| `docs/parcel_sorting_design_notes.md:101` | archive and rewrite/adapt | \`run_control.py\` now accepts \`--policy-stage A/B\`, medium, scan-window settings, and an explicit source A episode / demonstrated bin for B. A scans are saved in atomic episode metadata; B inherits the source destination and cycle. The first B-button release now starts recording, and timestamp folders include microseconds. Conversion retains provenance and writes B's \`/observations/destination\`. Policy loaders/models and autonomous A/B supervision still need implementation. See the [recording guide](guides/recording_guide.md) for current commands and teleoperation steps, and the [barcode scanning guide](guides/barcode_scanning_guide.md) for scanner setup and scan-paired episodes. Earlier findings above describe the pre-integration state. |
| `docs/parcel_sorting_design_notes.md:110` | archive and rewrite/adapt | A/B recording now defaults to scanner capture disabled. A records acquisition, presentation, staging and retraction without requiring a barcode. B requires a configured \`--demonstrated-bin\`, stored explicitly as a manual destination; optional \`--source-episode\` maintains pairing with unscanned A. An A scan can still be collected with \`--capture-barcode\`, and scanner-paired B must agree with that scan. Conversion accepts unscanned A and manually labelled B, preserving B's constant destination observation. No scan is fabricated for manually labelled episodes. |
| `experiments/README.md:7` | archive and rewrite/adapt | Start with the main README's [software setup](../README.md#software-setup) and [quick startup](../README.md#quick-startup). Use the [Policy A guide](../docs/guides/policy_a.md) or [Policy B guide](../docs/guides/policy_b.md) for task-specific commands. |
| `experiments/experiments_config.py:34` | archive and rewrite/adapt | "policy_stage": None,  # "A", "B", or None for legacy recording. |
| `experiments/experiments_config.py:38` | archive and rewrite/adapt | "source_episode": None, |
| `experiments/experiments_config.py:39` | archive and rewrite/adapt | "demonstrated_bin": None,  # 0 or 1 for Policy B; None for Policy A. |
| `experiments/inference_safety.py:70` | archive and rewrite/adapt | if (metadata.get('policy_stage') not in ('A', 'B') |
| `experiments/inference_safety.py:72` | archive and rewrite/adapt | raise ValueError('Task requires policy_stage and medium for robot deployment: {}'.format(task)) |
| `experiments/inference_safety.py:73` | archive and rewrite/adapt | if metadata['policy_stage'] == 'B' and metadata.get('bin_index') not in (0, 1): |
| `experiments/run_control.py:39` | archive and rewrite/adapt | policy_stage: Optional[str] = RUN_CONTROL["policy_stage"] |
| `experiments/run_control.py:44` | archive and rewrite/adapt | source_episode: Optional[str] = RUN_CONTROL["source_episode"] |
| `experiments/run_control.py:45` | archive and rewrite/adapt | demonstrated_bin: Optional[int] = RUN_CONTROL["demonstrated_bin"] |
| `experiments/run_control.py:464` | archive and rewrite/adapt | if args.policy_stage is None: |
| `experiments/run_control.py:465` | archive and rewrite/adapt | if args.capture_barcode or any(value is not None for value in (args.medium, args.source_episode, args.demonstrated_bin, args.scanner_device)): |
| `experiments/run_control.py:466` | archive and rewrite/adapt | raise ValueError('Barcode recording options require --policy-stage A or B') |
| `experiments/run_control.py:469` | archive and rewrite/adapt | session = RecordingSession(args.policy_stage, args.medium, args.scan_window_s, |
| `experiments/run_control.py:470` | archive and rewrite/adapt | args.source_episode, args.demonstrated_bin, |
| `experiments/run_control.py:474` | archive and rewrite/adapt | if args.policy_stage == 'A' and args.capture_barcode: |
| `experiments/run_inference.py:42` | archive and rewrite/adapt | active = np.array([1, 1] if project['policy_stage'] == 'A' and project['medium'] == 'envelope' |
| `experiments/run_inference.py:43` | archive and rewrite/adapt | else [1, 0] if project['policy_stage'] == 'A' else [0, 1]) |
| `robomimic-r2d2/docs/modules/models.md:152` | keep vendor | By default, each modality network should reduce an input observation stream to a fixed-size vector. The output of the \`forward\` function of the \`ObservationEncoder\` is simply the concatenation of all the vectors. The order of concatenation is deterministic and is the the same as the order that the modalities are registered. \`ObservationGroupEncoder\` further supports encoding nested groups of observations, e.g., \`obs\`, \`goal\`, and \`subgoal\`. This allows constructing goal-conditioned and / or subgoal-conditioned policy models. |
| `robomimic-r2d2/docs/modules/models.md:173` | keep vendor | \`MIMO_MLP\` and \`RNN_MIMO_MLP\` serve as **the backbone for all policy and value network models** -- these models simple subclass a \`MIMO_MLP\` or \`RNN_MIMO_MLP\`, and adds specific input and output shapes. |
| `robomimic-r2d2/docs/modules/models.md:180` | keep vendor | - A basic policy network that predicts actions from observations. Can optionally be goal conditioned on future observations. |
| `robomimic-r2d2/docs/modules/models.md:192` | keep vendor | - A VAE that models a distribution of actions conditioned on observations. The VAE prior and decoder are used at test-time as the policy. |
| `robomimic-r2d2/docs/modules/models.md:197` | keep vendor | - A basic value network that predicts values from observations. Can optionally be goal conditioned on future observations. |
| `robomimic-r2d2/docs/modules/models.md:209` | keep vendor | This implementation supports learning conditional distributions as well (cVAE). The conditioning variable Y is specified through the \`condition_shapes\` argument, which is also a map between modalities (strings) and expected shapes. In this way, variables with multiple kinds of data (e.g. image and flat-dimensional) can jointly be conditioned on. By default, the decoder takes the conditioning variable Y as input. To force the decoder to reconstruct from just the latent, set \`decoder_is_conditioned\` to False (in this case, the prior must be conditioned). |
| `robomimic-r2d2/docs/modules/models.md:211` | keep vendor | The implementation also supports learning expressive priors instead of using the usual N(0, 1) prior. There are three kinds of priors supported - Gaussian, Gaussian Mixture Model (GMM), and Categorical. For each prior, the parameters can be learned as independent parameters, or be learned as functions of the conditioning variable Y (by setting \`prior_is_conditioned\`). |
| `robomimic-r2d2/docs/modules/models.md:214` | keep vendor | - A class that holds functionality for learning both unimodal Gaussian priors and multimodal Gaussian Mixture Model priors for use in VAEs. Supports learnable priors, learnable / fixed mixture weights for GMM, and observation-conditioned priors, |
| `robomimic-r2d2/docs/tutorials/custom_algorithms.md:94` | keep vendor | class TD3_BC(PolicyAlgo, ValueAlgo): |
| `robomimic-r2d2/docs/tutorials/custom_algorithms.md:175` | keep vendor | info = PolicyAlgo.train_on_batch(self, batch, epoch, validate=validate) |
| `robomimic-r2d2/docs/tutorials/custom_algorithms.md:347` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/examples/notebooks/run_policy.ipynb:10` | keep vendor | "This notebook will provide examples on how to run a trained policy and visualize the rollout." |
| `robomimic-r2d2/robomimic/algo/__init__.py:1` | keep vendor | from robomimic.algo.algo import register_algo_factory_func, algo_name_to_factory_func, algo_factory, Algo, PolicyAlgo, ValueAlgo, PlannerAlgo, HierarchicalAlgo, RolloutPolicy |
| `robomimic-r2d2/robomimic/algo/act.py:13` | keep vendor | from robomimic.algo import register_algo_factory_func, PolicyAlgo |
| `robomimic-r2d2/robomimic/algo/act.py:162` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/act.py:231` | keep vendor | log = PolicyAlgo.log_info(self, info) |
| `robomimic-r2d2/robomimic/algo/algo.py:330` | keep vendor | class PolicyAlgo(Algo): |
| `robomimic-r2d2/robomimic/algo/algo.py:336` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/algo.py:519` | keep vendor | conditioned on current observations and potential goal observations. |
| `robomimic-r2d2/robomimic/algo/algo.py:551` | keep vendor | and (2) subgoal-conditioned policy learning. |
| `robomimic-r2d2/robomimic/algo/algo.py:555` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/bc.py:20` | keep vendor | from robomimic.algo import register_algo_factory_func, PolicyAlgo |
| `robomimic-r2d2/robomimic/algo/bc.py:77` | keep vendor | class BC(PolicyAlgo): |
| `robomimic-r2d2/robomimic/algo/bc.py:240` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/bc.py:338` | keep vendor | log = PolicyAlgo.log_info(self, info) |
| `robomimic-r2d2/robomimic/algo/bc.py:469` | keep vendor | log = PolicyAlgo.log_info(self, info) |
| `robomimic-r2d2/robomimic/algo/bc.py:539` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/bc.py:668` | keep vendor | log = PolicyAlgo.log_info(self, info) |
| `robomimic-r2d2/robomimic/algo/bc.py:770` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/bc.py:804` | keep vendor | if self.algo_config.language_conditioned: |
| `robomimic-r2d2/robomimic/algo/bc.py:894` | keep vendor | log = PolicyAlgo.log_info(self, info) |
| `robomimic-r2d2/robomimic/algo/bcq.py:21` | keep vendor | from robomimic.algo import register_algo_factory_func, PolicyAlgo, ValueAlgo |
| `robomimic-r2d2/robomimic/algo/bcq.py:44` | keep vendor | class BCQ(PolicyAlgo, ValueAlgo): |
| `robomimic-r2d2/robomimic/algo/bcq.py:50` | keep vendor | PolicyAlgo.__init__(self, **kwargs) |
| `robomimic-r2d2/robomimic/algo/bcq.py:555` | keep vendor | info = PolicyAlgo.train_on_batch(self, batch, epoch, validate=validate) |
| `robomimic-r2d2/robomimic/algo/bcq.py:785` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/cql.py:20` | keep vendor | from robomimic.algo import register_algo_factory_func, ValueAlgo, PolicyAlgo |
| `robomimic-r2d2/robomimic/algo/cql.py:38` | keep vendor | class CQL(PolicyAlgo, ValueAlgo): |
| `robomimic-r2d2/robomimic/algo/cql.py:285` | keep vendor | # Sample actions from policy and get log probs |
| `robomimic-r2d2/robomimic/algo/cql.py:340` | keep vendor | sampled from the learned policy at states s and s', respectively; a~ corresponding to uniformly random |
| `robomimic-r2d2/robomimic/algo/cql.py:360` | keep vendor | learned policy and a uniform distribution such that the first term in the CQL loss corresponds to the |
| `robomimic-r2d2/robomimic/algo/cql.py:363` | keep vendor | For stability, we importance sample actions over random actions and from the current policy at s, s'. |
| `robomimic-r2d2/robomimic/algo/cql.py:641` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/diffusion_policy.py:22` | keep vendor | from robomimic.algo import register_algo_factory_func, PolicyAlgo |
| `robomimic-r2d2/robomimic/algo/diffusion_policy.py:49` | keep vendor | class DiffusionPolicyUNet(PolicyAlgo): |
| `robomimic-r2d2/robomimic/algo/diffusion_policy.py:54` | keep vendor | if self.algo_config.language_conditioned: |
| `robomimic-r2d2/robomimic/algo/diffusion_policy.py:279` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/gl.py:245` | keep vendor | Get policy action outputs. Assumes one input observation (first dimension should be 1). |
| `robomimic-r2d2/robomimic/algo/hbc.py:4` | keep vendor | an actor model is conditioned on the subgoals to try and |
| `robomimic-r2d2/robomimic/algo/hbc.py:35` | keep vendor | return HBC, dict(policy_algo_class=pol_cls, planner_algo_class=plan_cls) |
| `robomimic-r2d2/robomimic/algo/hbc.py:45` | keep vendor | policy_algo_class, |
| `robomimic-r2d2/robomimic/algo/hbc.py:57` | keep vendor | policy_algo_class (Algo class): algo class for the policy |
| `robomimic-r2d2/robomimic/algo/hbc.py:120` | keep vendor | self.actor = policy_algo_class( |
| `robomimic-r2d2/robomimic/algo/hbc.py:304` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/iql.py:18` | keep vendor | from robomimic.algo import register_algo_factory_func, ValueAlgo, PolicyAlgo |
| `robomimic-r2d2/robomimic/algo/iql.py:36` | keep vendor | class IQL(PolicyAlgo, ValueAlgo): |
| `robomimic-r2d2/robomimic/algo/iql.py:417` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/algo/iris.py:31` | keep vendor | return IRIS, dict(policy_algo_class=pol_cls, planner_algo_class=plan_cls, value_algo_class=value_cls) |
| `robomimic-r2d2/robomimic/algo/iris.py:42` | keep vendor | policy_algo_class, |
| `robomimic-r2d2/robomimic/algo/iris.py:54` | keep vendor | policy_algo_class (Algo class): algo class for the policy |
| `robomimic-r2d2/robomimic/algo/iris.py:116` | keep vendor | self.actor = policy_algo_class( |
| `robomimic-r2d2/robomimic/algo/td3_bc.py:27` | keep vendor | from robomimic.algo import register_algo_factory_func, PolicyAlgo, ValueAlgo |
| `robomimic-r2d2/robomimic/algo/td3_bc.py:46` | keep vendor | class TD3_BC(PolicyAlgo, ValueAlgo): |
| `robomimic-r2d2/robomimic/algo/td3_bc.py:52` | keep vendor | PolicyAlgo.__init__(self, **kwargs) |
| `robomimic-r2d2/robomimic/algo/td3_bc.py:381` | keep vendor | info = PolicyAlgo.train_on_batch(self, batch, epoch, validate=validate) |
| `robomimic-r2d2/robomimic/algo/td3_bc.py:524` | keep vendor | Get policy action outputs. |
| `robomimic-r2d2/robomimic/config/base_config.py:334` | keep vendor | # whether the agent is goal-conditioned |
| `robomimic-r2d2/robomimic/config/bc_config.py:64` | keep vendor | self.algo.vae.decoder.is_conditioned = True                         # whether decoder should condition on observation |
| `robomimic-r2d2/robomimic/config/bc_config.py:69` | keep vendor | self.algo.vae.prior.is_conditioned = False                          # whether to condition prior on observations |
| `robomimic-r2d2/robomimic/config/bc_config.py:82` | keep vendor | self.algo.vae.prior_layer_dims = (300, 400)                         # prior MLP layer dimensions (if learning conditioned prior) |
| `robomimic-r2d2/robomimic/config/bc_config.py:110` | keep vendor | self.algo.language_conditioned = False                      # whether policy is language conditioned |
| `robomimic-r2d2/robomimic/config/diffusion_policy_config.py:2` | keep vendor | Config for Diffusion Policy algorithm. |
| `robomimic-r2d2/robomimic/config/diffusion_policy_config.py:59` | keep vendor | self.algo.language_conditioned = False                      # whether policy is language conditioned |
| `robomimic-r2d2/robomimic/config/gl_config.py:39` | keep vendor | self.algo.vae.decoder.is_conditioned = True                         # whether decoder should condition on observation |
| `robomimic-r2d2/robomimic/config/gl_config.py:44` | keep vendor | self.algo.vae.prior.is_conditioned = False                          # whether to condition prior on observations |
| `robomimic-r2d2/robomimic/config/gl_config.py:57` | keep vendor | self.algo.vae.prior_layer_dims = (300, 400)                         # prior MLP layer dimensions (if learning conditioned prior) |
| `robomimic-r2d2/robomimic/exps/templates/bc.json:109` | keep vendor | "is_conditioned": true, |
| `robomimic-r2d2/robomimic/exps/templates/bc.json:114` | keep vendor | "is_conditioned": false, |
| `robomimic-r2d2/robomimic/exps/templates/bcq.json:143` | keep vendor | "is_conditioned": true, |
| `robomimic-r2d2/robomimic/exps/templates/bcq.json:148` | keep vendor | "is_conditioned": false, |
| `robomimic-r2d2/robomimic/exps/templates/gl.json:89` | keep vendor | "is_conditioned": true, |
| `robomimic-r2d2/robomimic/exps/templates/gl.json:94` | keep vendor | "is_conditioned": false, |
| `robomimic-r2d2/robomimic/exps/templates/hbc.json:100` | keep vendor | "is_conditioned": true, |
| `robomimic-r2d2/robomimic/exps/templates/hbc.json:105` | keep vendor | "is_conditioned": false, |
| `robomimic-r2d2/robomimic/exps/templates/iris.json:101` | keep vendor | "is_conditioned": true, |
| `robomimic-r2d2/robomimic/exps/templates/iris.json:106` | keep vendor | "is_conditioned": false, |
| `robomimic-r2d2/robomimic/exps/templates/iris.json:211` | keep vendor | "is_conditioned": true, |
| `robomimic-r2d2/robomimic/exps/templates/iris.json:216` | keep vendor | "is_conditioned": false, |
| `robomimic-r2d2/robomimic/models/policy_nets.py:29` | keep vendor | Can optionally be goal conditioned on future observations. |
| `robomimic-r2d2/robomimic/models/policy_nets.py:76` | keep vendor | self._is_goal_conditioned = False |
| `robomimic-r2d2/robomimic/models/policy_nets.py:79` | keep vendor | self._is_goal_conditioned = True |
| `robomimic-r2d2/robomimic/models/policy_nets.py:625` | keep vendor | self._is_goal_conditioned = False |
| `robomimic-r2d2/robomimic/models/policy_nets.py:628` | keep vendor | self._is_goal_conditioned = True |
| `robomimic-r2d2/robomimic/models/policy_nets.py:681` | keep vendor | if self._is_goal_conditioned: |
| `robomimic-r2d2/robomimic/models/policy_nets.py:847` | keep vendor | if self._is_goal_conditioned: |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1055` | keep vendor | self._is_goal_conditioned = False |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1058` | keep vendor | self._is_goal_conditioned = True |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1112` | keep vendor | if self._is_goal_conditioned: |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1270` | keep vendor | if self._is_goal_conditioned: |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1338` | keep vendor | A VAE that models a distribution of actions conditioned on observations. |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1349` | keep vendor | decoder_is_conditioned=True, |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1353` | keep vendor | prior_is_conditioned=False, |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1409` | keep vendor | decoder_is_conditioned=decoder_is_conditioned, |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1415` | keep vendor | prior_is_conditioned=prior_is_conditioned, |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1455` | keep vendor | batches. Only needs to be provided if @decoder_is_conditioned |
| `robomimic-r2d2/robomimic/models/policy_nets.py:1483` | keep vendor | batches. Only needs to be provided if @prior_is_conditioned. |
| `robomimic-r2d2/robomimic/models/vae_nets.py:31` | keep vendor | decoder_is_conditioned=vae_config.decoder.is_conditioned, |
| `robomimic-r2d2/robomimic/models/vae_nets.py:35` | keep vendor | prior_is_conditioned=vae_config.prior.is_conditioned, |
| `robomimic-r2d2/robomimic/models/vae_nets.py:653` | keep vendor | # sample one-hot latents from categorical distribution |
| `robomimic-r2d2/robomimic/models/vae_nets.py:655` | keep vendor | z = TensorUtils.to_one_hot(dist.sample(), num_class=self.categorical_dim) |
| `robomimic-r2d2/robomimic/models/vae_nets.py:663` | keep vendor | # sample one-hot latents from uniform categorical distribution for each latent dimension |
| `robomimic-r2d2/robomimic/models/vae_nets.py:666` | keep vendor | z = TensorUtils.to_one_hot(dist_samples, num_class=self.categorical_dim) |
| `robomimic-r2d2/robomimic/models/vae_nets.py:764` | keep vendor | jointly be conditioned on. By default, the decoder takes the conditioning |
| `robomimic-r2d2/robomimic/models/vae_nets.py:766` | keep vendor | set @decoder_is_conditioned to False (in this case, the prior must be conditioned). |
| `robomimic-r2d2/robomimic/models/vae_nets.py:772` | keep vendor | variable Y (by setting @prior_is_conditioned). |
| `robomimic-r2d2/robomimic/models/vae_nets.py:783` | keep vendor | decoder_is_conditioned=True, |
| `robomimic-r2d2/robomimic/models/vae_nets.py:790` | keep vendor | prior_is_conditioned=False, |
| `robomimic-r2d2/robomimic/models/vae_nets.py:828` | keep vendor | decoder_is_conditioned (bool): whether to condition the decoder |
| `robomimic-r2d2/robomimic/models/vae_nets.py:855` | keep vendor | If @prior_is_conditioned is True, a global set of parameters |
| `robomimic-r2d2/robomimic/models/vae_nets.py:862` | keep vendor | prior_is_conditioned (bool): whether to condition the prior |
| `robomimic-r2d2/robomimic/models/vae_nets.py:869` | keep vendor | input (i.e. when @prior_learn and @prior_is_conditioned are set to True, |
| `robomimic-r2d2/robomimic/models/vae_nets.py:890` | keep vendor | and will be "one-hot" in the latter dimension. Only used if |
| `robomimic-r2d2/robomimic/models/vae_nets.py:938` | keep vendor | self.decoder_is_conditioned = decoder_is_conditioned |
| `robomimic-r2d2/robomimic/models/vae_nets.py:939` | keep vendor | self.prior_is_conditioned = prior_is_conditioned |
| `robomimic-r2d2/robomimic/models/vae_nets.py:940` | keep vendor | assert self.decoder_is_conditioned or self.prior_is_conditioned, \ |
| `robomimic-r2d2/robomimic/models/vae_nets.py:941` | keep vendor | "cVAE must be conditioned in decoder and/or prior" |
| `robomimic-r2d2/robomimic/models/vae_nets.py:942` | keep vendor | if self.prior_is_conditioned: |
| `robomimic-r2d2/robomimic/models/vae_nets.py:946` | keep vendor | self._is_goal_conditioned = False |
| `robomimic-r2d2/robomimic/models/vae_nets.py:951` | keep vendor | self._is_goal_conditioned = True |
| `robomimic-r2d2/robomimic/models/vae_nets.py:1012` | keep vendor | # encoder takes "input" dictionary and possibly "condition" (if cVAE) and "goal" (if goal-conditioned) |
| `robomimic-r2d2/robomimic/models/vae_nets.py:1017` | keep vendor | if self._is_goal_conditioned: |
| `robomimic-r2d2/robomimic/models/vae_nets.py:1043` | keep vendor | # decoder takes latent (included as "input" observation group) and possibly "condition" (if cVAE) and "goal" (if goal-conditioned) |
| `robomimic-r2d2/robomimic/models/vae_nets.py:1051` | keep vendor | if self._is_goal_conditioned: |
| `robomimic-r2d2/robomimic/models/vae_nets.py:1066` | keep vendor | # prior possibly takes "condition" (if cVAE) and "goal" (if goal-conditioned) |
| `robomimic-r2d2/robomimic/models/vae_nets.py:1068` | keep vendor | if self._is_cvae and self.prior_is_conditioned: |
| `robomimic-r2d2/robomimic/models/vae_nets.py:1070` | keep vendor | if self._is_goal_conditioned: |
| `robomimic-r2d2/robomimic/models/value_nets.py:23` | keep vendor | Can optionally be goal conditioned on future observations. |
| `robomimic-r2d2/robomimic/models/value_nets.py:77` | keep vendor | self._is_goal_conditioned = False |
| `robomimic-r2d2/robomimic/models/value_nets.py:80` | keep vendor | self._is_goal_conditioned = True |
| `robomimic-r2d2/robomimic/models/value_nets.py:132` | keep vendor | and actions. Can optionally be goal conditioned on future observations. |
| `robomimic-r2d2/robomimic/scripts/config_gen/bc_xfmr_gen.py:65` | keep vendor | key="algo.language_conditioned", |
| `robomimic-r2d2/robomimic/scripts/config_gen/diffusion_gen.py:142` | keep vendor | key="algo.language_conditioned", |
| `robomimic-r2d2/robomimic/scripts/config_gen/parcel_sorting_gen.py:22` | keep vendor; generator explicitly adapted | conditioned = ROBOMIMIC['recipes'][recipe_name]['destination'] |
| `robomimic-r2d2/robomimic/scripts/config_gen/parcel_sorting_gen.py:63` | keep vendor; generator explicitly adapted | 'observation.modalities.obs.low_dim': ['qpos'] + (['destination'] if conditioned else []), |
| `robomimic-r2d2/robomimic/scripts/generate_paper_configs.py:502` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = True |
| `robomimic-r2d2/robomimic/scripts/generate_paper_configs.py:602` | keep vendor | config.algo.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/robomimic/scripts/generate_paper_configs.py:655` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/robomimic/utils/tensor_utils.py:412` | keep vendor | def to_one_hot_single(tensor, num_class): |
| `robomimic-r2d2/robomimic/utils/tensor_utils.py:414` | keep vendor | Convert tensor to one-hot representation, assuming a certain number of total class labels. |
| `robomimic-r2d2/robomimic/utils/tensor_utils.py:421` | keep vendor | x (torch.Tensor): tensor containing one-hot representation of labels |
| `robomimic-r2d2/robomimic/utils/tensor_utils.py:428` | keep vendor | def to_one_hot(tensor, num_class): |
| `robomimic-r2d2/robomimic/utils/tensor_utils.py:430` | keep vendor | Convert all tensors in nested dictionary or list or tuple to one-hot representation, |
| `robomimic-r2d2/robomimic/utils/tensor_utils.py:440` | keep vendor | return map_tensor(tensor, func=lambda x, nc=num_class: to_one_hot_single(x, nc)) |
| `robomimic-r2d2/robomimic/utils/test_utils.py:207` | keep vendor | # get policy and env from checkpoint |
| `robomimic-r2d2/robomimic/utils/test_utils.py:223` | keep vendor | policy and environment from the checkpoint, and run an evaluation rollout. Returns |
| `robomimic-r2d2/robomimic/utils/torch_utils.py:362` | keep vendor | # forall i; we pick the best-conditioned one (with the largest denominator) |
| `robomimic-r2d2/robomimic/utils/torch_utils.py:365` | keep vendor | F.one_hot(q_abs.argmax(dim=-1), num_classes=4) > 0.5, : |
| `robomimic-r2d2/robomimic/utils/train_utils.py:263` | keep vendor | use_goals (bool): if True, agent is goal-conditioned, so provide goal observations from env |
| `robomimic-r2d2/robomimic/utils/train_utils.py:475` | keep vendor | use_goals (bool): if True, agent is goal-conditioned, so provide goal observations from env |
| `robomimic-r2d2/tests/test_bc.py:111` | keep vendor | config.algo.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bc.py:120` | keep vendor | config.algo.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bc.py:131` | keep vendor | config.algo.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_bc.py:142` | keep vendor | config.algo.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bc.py:154` | keep vendor | config.algo.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bc.py:166` | keep vendor | config.algo.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_bc.py:178` | keep vendor | config.algo.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_bc.py:190` | keep vendor | config.algo.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bc.py:201` | keep vendor | config.algo.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bc.py:212` | keep vendor | config.algo.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_bcq.py:113` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bcq.py:122` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bcq.py:133` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_bcq.py:144` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bcq.py:156` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bcq.py:168` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_bcq.py:180` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_bcq.py:192` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bcq.py:203` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_bcq.py:214` | keep vendor | config.algo.action_sampler.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_hbc.py:59` | keep vendor | config.algo.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_hbc.py:68` | keep vendor | config.algo.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_hbc.py:79` | keep vendor | config.algo.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_hbc.py:90` | keep vendor | config.algo.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_hbc.py:102` | keep vendor | config.algo.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_hbc.py:114` | keep vendor | config.algo.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_hbc.py:126` | keep vendor | config.algo.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_hbc.py:138` | keep vendor | config.algo.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_hbc.py:149` | keep vendor | config.algo.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_hbc.py:160` | keep vendor | config.algo.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_iris.py:41` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:44` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:68` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:79` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_iris.py:90` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:102` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:114` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_iris.py:126` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_iris.py:138` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:149` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:160` | keep vendor | config.algo.value_planner.planner.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_iris.py:186` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:197` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_iris.py:208` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:220` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:232` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_iris.py:244` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = True |
| `robomimic-r2d2/tests/test_iris.py:256` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:267` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = False |
| `robomimic-r2d2/tests/test_iris.py:278` | keep vendor | config.algo.value_planner.value.action_sampler.vae.prior.is_conditioned = True |
| `scripts/README.md:7` | archive and rewrite/adapt | For complete task workflows, use the [Policy A guide](../docs/guides/policy_a.md) or [Policy B guide](../docs/guides/policy_b.md). |
| `scripts/README.md:52` | archive and rewrite/adapt | \| \`policy_stage\`, \`medium\`, \`bin_index\` \| Task, parcel type and destination recorded in the episode details \| |
| `scripts/check_destination_swap.py:88` | archive and rewrite/adapt | raise ValueError('Checkpoint is not destination-conditioned B') |
| `scripts/check_destination_swap.py:90` | archive and rewrite/adapt | if source['data'].attrs['recipe'] != 'policy_B_conditioned': |
| `scripts/check_destination_swap.py:91` | archive and rewrite/adapt | raise ValueError('Dataset must use policy_B_conditioned') |
| `scripts/convert_to_robomimic.py:36` | archive and rewrite/adapt | stage = source.attrs.get('policy_stage') |
| `scripts/convert_to_robomimic.py:84` | archive and rewrite/adapt | raise ValueError('Conditioned B requires both bins') |
| `scripts/convert_to_robomimic.py:174` | archive and rewrite/adapt | demo.attrs['source_episode'] = entry['id'] |
| `scripts/count_episodes.py:24` | archive and rewrite/adapt | stage = metadata.get('policy_stage') |
| `scripts/count_episodes.py:76` | archive and rewrite/adapt | episode.name, metadata.get('policy_stage'), metadata.get('medium'), |
| `scripts/curate_datasets.py:99` | archive and rewrite/adapt | if m.get('policy_stage') not in ('A', 'B') or m.get('medium') not in ('poly_mailer', 'carton', 'envelope'): |
| `scripts/curate_datasets.py:100` | archive and rewrite/adapt | raise ValueError('Missing policy_stage or medium: {}'.format(episode)) |
| `scripts/curate_datasets.py:120` | archive and rewrite/adapt | bin_index = destination.get('bin_index') if m['policy_stage'] == 'B' else None |
| `scripts/curate_datasets.py:121` | archive and rewrite/adapt | if m['policy_stage'] == 'B' and (type(bin_index) is not int or bin_index not in (0, 1)): |
| `scripts/curate_datasets.py:123` | archive and rewrite/adapt | return dict(policy_stage=m['policy_stage'], medium=m['medium'], bin_index=bin_index, |
| `scripts/curate_datasets.py:128` | archive and rewrite/adapt | for key in ('policy_stage', 'medium', 'bin_index', 'camera_names', 'control_period_ms'): |
| `scripts/curate_datasets.py:281` | archive and rewrite/adapt | plan.warnings.add('Policy B {} keeps source_metadata_path {}; A moves to {}. ' |
| `scripts/curate_datasets.py:287` | archive and rewrite/adapt | plan.warnings.add('{}: Policy B source link stays unchanged: {}'.format(op.source.name, m['source_metadata_path'])) |
| `scripts/curate_datasets.py:424` | archive and rewrite/adapt | details['stage={}, medium={}, bin={}'.format(m.get('policy_stage'), m.get('medium'), |
| `scripts/curate_datasets.py:430` | archive and rewrite/adapt | for field in ('policy_stage', 'medium'): |
| `scripts/dataset_checks.py:22` | archive and rewrite/adapt | stage, medium = metadata['policy_stage'], metadata['medium'] |
| `scripts/prepare_act_datasets.py:78` | archive and rewrite/adapt | expected_stage = project['policy_stage'] |
| `scripts/prepare_act_datasets.py:105` | archive and rewrite/adapt | if (report['policy_stage'] != expected_stage |
| `scripts/review_episodes.py:55` | archive and rewrite/adapt | for key in ('episode_id', 'cycle_id', 'policy_stage', 'medium'): |
| `scripts/review_episodes.py:71` | archive and rewrite/adapt | if metadata['policy_stage'] == 'B': |
| `scripts/scripts_config.py:34` | archive and rewrite/adapt | "policy_stage": "A", |
| `scripts/scripts_config.py:42` | archive and rewrite/adapt | "policy_stage": "B", |
| `scripts/scripts_config.py:50` | archive and rewrite/adapt | "policy_stage": "B", |
| `scripts/scripts_config.py:70` | archive and rewrite/adapt | "policy_stage": _stage, "medium": _medium, "bin_index": _bin, |
| `scripts/scripts_config.py:77` | archive and rewrite/adapt | "policy_stage": _stage, "medium": _medium, |
| `scripts/scripts_config.py:174` | archive and rewrite/adapt | "policy_A_unified": {"stage": "A", "medium": None, "bin": None, "destination": False}, |
| `scripts/scripts_config.py:175` | archive and rewrite/adapt | "policy_B_conditioned": {"stage": "B", "medium": None, "bin": None, "destination": True}, |
| `scripts/scripts_config.py:176` | archive and rewrite/adapt | "policy_A_envelope": {"stage": "A", "medium": "envelope", "bin": None, "destination": False}, |
| `scripts/scripts_config.py:177` | archive and rewrite/adapt | "policy_A_poly_mailer": {"stage": "A", "medium": "poly_mailer", "bin": None, "destination": False}, |
| `scripts/scripts_config.py:178` | archive and rewrite/adapt | "policy_A_carton": {"stage": "A", "medium": "carton", "bin": None, "destination": False}, |
| `scripts/scripts_config.py:179` | archive and rewrite/adapt | "policy_B_bin_0": {"stage": "B", "medium": None, "bin": 0, "destination": False}, |
| `scripts/scripts_config.py:180` | archive and rewrite/adapt | "policy_B_bin_1": {"stage": "B", "medium": None, "bin": 1, "destination": False}, |
| `tests/test_act_checkpoint.py:20` | archive and rewrite/adapt | (directory / 'policy_best.ckpt').touch() |
| `tests/test_act_checkpoint.py:47` | archive and rewrite/adapt | assert Path(weights).resolve() == directory / 'policy_best.ckpt' |
| `tests/test_act_checkpoint.py:58` | archive and rewrite/adapt | model = load_act_checkpoint(directory, 'policy_best.ckpt', 'parcel') |
| `tests/test_act_checkpoint.py:70` | archive and rewrite/adapt | load_act_checkpoint(directory, 'policy_best.ckpt', 'another_task') |
| `tests/test_act_checkpoint.py:73` | archive and rewrite/adapt | @pytest.mark.parametrize('missing', ['config.pkl', 'dataset_stats.pkl', 'policy_best.ckpt']) |
| `tests/test_act_checkpoint.py:78` | archive and rewrite/adapt | load_act_checkpoint(directory, 'policy_best.ckpt', 'parcel') |
| `tests/test_barcode_scanner.py:17` | archive and rewrite/adapt | from barcode_scanning.recording import RecordingSession, load_source_episode |
| `tests/test_barcode_scanner.py:178` | archive and rewrite/adapt | b = RecordingSession('B', 'carton', source_episode=source, demonstrated_bin=1) |
| `tests/test_barcode_scanner.py:185` | archive and rewrite/adapt | self.assertEqual(b_data['source_episode_id'], 'A') |
| `tests/test_barcode_scanner.py:202` | archive and rewrite/adapt | b = RecordingSession('B', 'carton', demonstrated_bin=0) |
| `tests/test_barcode_scanner.py:219` | archive and rewrite/adapt | b = RecordingSession('B', 'carton', source_episode=self.root / 'manual-A', demonstrated_bin=1) |
| `tests/test_barcode_scanner.py:229` | archive and rewrite/adapt | RecordingSession('B', 'carton', demonstrated_bin=index) |
| `tests/test_barcode_scanner.py:233` | archive and rewrite/adapt | RecordingSession('B', 'carton', source_episode=self.source(), demonstrated_bin=0) |
| `tests/test_barcode_scanner.py:237` | archive and rewrite/adapt | RecordingSession('B', 'envelope', source_episode=self.source(), demonstrated_bin=1) |
| `tests/test_barcode_scanner.py:245` | archive and rewrite/adapt | load_source_episode(self.root / 'A', 'carton', 1) |
| `tests/test_barcode_scanner.py:252` | archive and rewrite/adapt | load_source_episode(self.root / 'A', 'carton', 1) |
| `tests/test_barcode_scanner.py:278` | archive and rewrite/adapt | load_source_episode(self.root / 'A', 'carton', 0) |
| `tests/test_barcode_scanner.py:282` | archive and rewrite/adapt | b = RecordingSession('B', 'carton', source_episode=source, demonstrated_bin=1) |
| `tests/test_barcode_scanner.py:290` | archive and rewrite/adapt | self.assertEqual(file.attrs['policy_stage'], 'B') |
| `tests/test_barcode_scanner.py:360` | archive and rewrite/adapt | args = types.SimpleNamespace(policy_stage=stage, capture_barcode=False, medium='carton', |
| `tests/test_barcode_scanner.py:361` | archive and rewrite/adapt | scan_window_s=30, source_episode=None, |
| `tests/test_barcode_scanner.py:362` | archive and rewrite/adapt | demonstrated_bin=bin_index, scanner_device=None) |
| `tests/test_dataset_checks.py:10` | archive and rewrite/adapt | return np.tile(home, (25, 1)), dict(policy_stage=stage, medium=medium, |
| `tests/test_dataset_curation.py:18` | archive and rewrite/adapt | return dict(policy_stage=stage, medium=medium, bin_index=bin_index, |
| `tests/test_dataset_curation.py:30` | archive and rewrite/adapt | frame_count=frames, review_status=status, policy_stage=stage, medium=medium, |
| `tests/test_dataset_curation.py:34` | archive and rewrite/adapt | control_period_ms=period, demonstrated_bin=bin_index, |
| `tests/test_dataset_curation.py:149` | archive and rewrite/adapt | ('policy_stage', 'B'), ('medium', 'carton'), ('bin_index', 1), |
| `tests/test_episode_review.py:20` | archive and rewrite/adapt | session = RecordingSession(stage, 'poly_mailer', demonstrated_bin=bin_index) |
| `tests/test_inference_safety.py:96` | archive and rewrite/adapt | combined = {'combined': {'policy_stage': 'A', 'medium': 'poly_mailer', 'bin_index': None}} |
| `tests/test_inference_safety.py:102` | archive and rewrite/adapt | projects = {'parcel': {'policy_stage': 'B', 'medium': 'carton', 'bin_index': 1}} |
| `tests/test_inference_safety.py:106` | archive and rewrite/adapt | @pytest.mark.parametrize('metadata', [{}, {'policy_stage': 'A', 'medium': 'unknown'}, |
| `tests/test_inference_safety.py:107` | archive and rewrite/adapt | {'policy_stage': 'B', 'medium': 'poly_mailer', 'bin_index': None}]) |
| `tests/test_preparation_review.py:37` | archive and rewrite/adapt | monkeypatch.setattr(prepare, 'PROJECTS', {'A': dict(policy_stage='A', medium='poly_mailer', |
| `tests/test_preparation_review.py:66` | archive and rewrite/adapt | monkeypatch.setattr(prepare, 'PROJECTS', {'A': dict(policy_stage='A', medium='poly_mailer', |
| `tests/test_robomimic_parcels.py:22` | archive and rewrite/adapt | source.attrs['policy_stage'] = stage |
| `tests/test_robomimic_parcels.py:46` | archive and rewrite/adapt | def test_conditioned_conversion_rgb_provenance_and_split(tmp_path): |
| `tests/test_robomimic_parcels.py:50` | archive and rewrite/adapt | split = convert(sources, 'policy_B_conditioned', output, split_file) |
| `tests/test_robomimic_parcels.py:57` | archive and rewrite/adapt | assert demo.attrs['policy_stage'] == 'B' |
| `tests/test_robomimic_parcels.py:66` | archive and rewrite/adapt | convert(sources, 'policy_B_conditioned', output, split_file) |
| `tests/test_robomimic_parcels.py:69` | archive and rewrite/adapt | def test_conditioned_dataset_requires_both_bins(tmp_path): |
| `tests/test_robomimic_parcels.py:74` | archive and rewrite/adapt | convert([project], 'policy_B_conditioned', tmp_path / 'B.h5', tmp_path / 'split.json') |
| `tests/test_robomimic_parcels.py:82` | archive and rewrite/adapt | convert(sources, 'policy_B_conditioned', tmp_path / 'B.h5', tmp_path / 'split.json') |
| `tests/test_robomimic_parcels.py:89` | archive and rewrite/adapt | convert([project], 'policy_A_unified', tmp_path / 'A.h5', tmp_path / 'split.json') |
| `tests/test_robomimic_parcels.py:96` | archive and rewrite/adapt | convert(sources, 'policy_B_conditioned', tmp_path / 'B.h5', split_file) |
| `tests/test_robomimic_parcels.py:100` | archive and rewrite/adapt | convert(sources, 'policy_B_conditioned', tmp_path / 'B2.h5', split_file) |
| `tests/test_robomimic_parcels.py:107` | archive and rewrite/adapt | split = convert(sources, 'policy_B_conditioned', tmp_path / 'B.h5', tmp_path / 'split.json') |
| `tests/test_robomimic_parcels.py:116` | archive and rewrite/adapt | convert(sources, 'policy_B_conditioned', output, split_file) |
| `tests/test_robomimic_parcels.py:158` | archive and rewrite/adapt | convert(sources, 'policy_B_conditioned', tmp_path / 'B.h5', tmp_path / 'split.json') |

## Existing local artifact directories

- `datasets/preliminary_carton_A`: move intact to `old_architecture_folder/datasets/`.
- `datasets/preliminary_carton_B`: move intact to `old_architecture_folder/datasets/`.
- `datasets/preliminary_envelope_A`: move intact to `old_architecture_folder/datasets/`.
- `datasets/preliminary_envelope_B`: move intact to `old_architecture_folder/datasets/`.
- `datasets/preliminary_poly_mailer_A`: move intact to `old_architecture_folder/datasets/`.
- `datasets/preliminary_poly_mailer_B`: move intact to `old_architecture_folder/datasets/`.
- `datasets/set01_poly_mailer_A`: move intact to `old_architecture_folder/datasets/`.
- `datasets/set01_poly_mailer_B_bin_0`: move intact to `old_architecture_folder/datasets/`.
- `datasets/set01_poly_mailer_B_bin_1`: move intact to `old_architecture_folder/datasets/`.
- `datasets/set02_poly_mailer_A`: move intact to `old_architecture_folder/datasets/`.
- `datasets/set02_poly_mailer_B_bin_0`: move intact to `old_architecture_folder/datasets/`.
- `datasets/set02_poly_mailer_B_bin_1`: move intact to `old_architecture_folder/datasets/`.
- `datasets/training`: move intact to `old_architecture_folder/datasets/`.
- `ckpt/act_poly_mailer_25_A`: move intact to `old_architecture_folder/ckpt/`.
