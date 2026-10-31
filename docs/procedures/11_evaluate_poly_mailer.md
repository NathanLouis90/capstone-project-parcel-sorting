# Evaluate the poly-mailer models

The evaluation workbook holds 100 scored trials for each of `dp_poly_mailer_v1.0` and `act_poly_mailer_v1.1`, and each model has its own cycle log.

## Before you start

- You have completed [Run parcel cycles](10_run_cycles.md) once, including an unscored live cycle.
- The workbook `poly_mailer_model_evaluation.xlsx` is open with one sheet per model:

  | Sheet | Checkpoint | Epoch | ACT rollout settings |
  | --- | --- | ---: | --- |
  | act_v1.1 | `ckpt/act_poly_mailer_v1.1/best.pth` | 895 | Ensembling on, coefficient `0.01` |
  | dp_v1.0 | `ckpt/dp_poly_mailer_v1.0/best.pth` | 975 | Saved DP settings |

- Every trial uses the same parcel, filling, label, platform, scanner, cameras, lighting, starting arm positions, and starting gripper state. Run any unscored setup checks first, then freeze these conditions.
- Leave the checkpoints and `config/settings.py` unchanged until all trials are done. This keeps the 20 s rollout timeout and 1 s stationary scan window fixed.
- A separate video source is recording. It must not use the robot's three cameras.
- Two terminals are prepared, the robot server is running in Terminal 1 ([Run parcel cycles](10_run_cycles.md), steps 4 and 5), and the emergency stop is within reach.

## Steps

1. Print today's date and time zone, then enter it in the workbook with the model, checkpoint, and rollout settings.
   ```bash
   date '+%Y-%m-%d %Z'
   ```
   Expect: for example `2026-11-01 +08`.

2. Check that both models load. These checks do not count as trials.
   ```bash
   python3 evaluation/check_checkpoint.py --medium poly_mailer --checkpoint ckpt/act_poly_mailer_v1.1/best.pth --steps 5 --act-temporal-ensemble --act-ensemble-coefficient 0.01
   python3 evaluation/check_checkpoint.py --medium poly_mailer --checkpoint ckpt/dp_poly_mailer_v1.0/best.pth --steps 5
   ```
   Expect: `ACT rollout settings: {"chunk_length": 16, "coefficient": 0.01, "query_frequency": 1, "temporal_ensemble": true}` for ACT only, then five predictions and `Checkpoint stepped without hardware; predictions were not sent to a robot` for each model.

3. Check each model's training recordings against the rollout joint bounds.
   ```bash
   python3 tools/check_rollout_compatibility.py --checkpoint ckpt/act_poly_mailer_v1.1/best.pth
   python3 tools/check_rollout_compatibility.py --checkpoint ckpt/dp_poly_mailer_v1.0/best.pth
   ```
   Expect: `"compatible_joint_gaps": true` and all `violations` equal to `0` in each report.

4. Set up the next trial row from the workbook: zone, orientation, and label face. Arms must be home with both grippers open. A completed cycle leaves them like that. Then set the label face in Terminal 2 (`top` or `bottom`).
   ```bash
   label_face=top
   ```
   Expect: no output.

5. Start the video, then run the command for the sheet you are filling. Run it once per trial.
   **The right arm starts moving as soon as the model has loaded. Keep the emergency stop within reach.**
   ```bash
   python3 evaluation/run_cycle.py --medium poly_mailer --live --checkpoint ckpt/act_poly_mailer_v1.1/best.pth --act-temporal-ensemble --act-ensemble-coefficient 0.01 --label-face "$label_face" --csv cycle_logs/act_v1.1.csv
   ```
   For dp_v1.0, run this instead:
   ```bash
   python3 evaluation/run_cycle.py --medium poly_mailer --live --checkpoint ckpt/dp_poly_mailer_v1.0/best.pth --label-face "$label_face" --csv cycle_logs/dp_v1.0.csv
   ```
   Expect: the arm picks, scans, places in a bin or back at receiving, returns home, and asks for the outcome.

6. Answer the prompts: `s`, `g`, `d`, or `w` for the physical outcome. If there was no read, enter the cause (`t`, `l`, or Enter). At the retry prompt, press any key except `r` (the protocol allows one attempt per trial), then any key at `Cycle stopped`.
   Expect: the attempt's JSON row is printed and appended to the model's CSV.

7. Score the trial in the workbook straight away, using the video and the printed row (rules below). Write the trial ID next to the row's `cycle_id`.
   Expect: the row is filled up to its first failed stage.

8. Repeat steps 4 to 7 for all 100 trials on each sheet, in the order the workbook lists them.

The first trials are:

| Trial | Zone | Orientation | Label |
| --- | --- | ---: | --- |
| T001 | bottom_left | 45° | top |
| T002 | top_right | 45° | bottom |
| T003 | bottom_center | 0° | top |

## Scoring rules

- Fill the stages from left to right. Mark the first failed required stage `N` and leave the later stages blank.
- A top-label trial needs a successful platform flip. Leave `Flipped` blank for bottom-label trials.
- Count every autonomous grasp attempt. A trial can still succeed after more than one attempt.
- Any intervention during the rollout counts as a failure, including stopping the program.
- If the arm stalls, or the cycle faults with `Pick-to-scan handoff timeout`, mark the current stage `N` and select `Stalled / timeout`.
- The primary result is pick-to-scan success: a fresh read in the initial stationary window. In the row, that is a non-empty `token` with `rotations_to_read` equal to `0`. Record a read after a rotation as a backup read, not a primary success.
- The cycle's `outcome: success` includes bin placement. It does not replace the workbook's pick-to-scan result.
- Take presentation time from the video, starting at the first robot motion. `t_pick_s` in the CSV starts after model warmup.
- Redo a trial only for a genuine setup error, and explain it in `Remarks`.
- Do not edit the calculated cells.
- Report first-grasp success, stage rates, interventions, and presentation time separately from the primary rate.

See [runtime limitations](../reference/runtime.md#limitations) for how the cycle differs from the workbook protocol.

## If something goes wrong

- The cycle faults: do not score past the failed stage. Recover with [home and recover](home_and_recover.md), restart the server with empty grippers, then continue with the next trial.
- A model's command fails with `Checkpoint medium differs from requested medium` or `Missing checkpoint`: check the path in the table above. Do not substitute another checkpoint during the experiment.
- `Cycle CSV columns differ; select a new log file`: use a new `--csv` name for that model and note it in the workbook.
- The scanner reports a failure (`Scanner failure: ...`): stop any other scanner program and check the scanner with [labels and scanner](03_labels_and_scanner.md) before continuing.
