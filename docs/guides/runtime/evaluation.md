# Run and evaluate parcel cycles

Run from the repository root with `Xtrainer` activated in every terminal.
See [terminal setup](../../terminal_commands.md). The medium is selected manually.

## Prerequisites

Teach and commission the [joint waypoints](../hardware/waypoints.md), including receiving
returns for both arms. Train fresh checkpoints. Verify scanner reads at rest
and throughout the candidate-face sequence, tool clearance, joint limits,
cable slack and grasp retention. Stay at the robot with emergency-stop access.

## Software-only checks

These checks need no server, leader arms, cameras, or scanner. Run each example
separately; they test different outcomes.

### Simulate a successful cycle

```bash
python3 experiments/run_cycle.py --medium carton --dry-run \
  --fake-token DEST-B-S828608 --csv /tmp/carton-cycle.csv
```

| Argument | Meaning |
| --- | --- |
| `--medium carton` | Use the carton cycle, with the left holding arm and up to three 90° scan rotations. Other choices are `envelope` and `poly_mailer`. |
| `--dry-run` | Simulate the robot and scanner. With no checkpoint, use a simulated policy; no model is trained or loaded. |
| `--fake-token DEST-B-S828608` | Supply a simulated valid barcode for bin 1, Punggol. `DEST-A-S138683` selects bin 0, Dover. |
| `--csv /tmp/carton-cycle.csv` | Append the result to this output CSV and print the cycle row in the terminal. Choose another path to keep runs separate. |

Optional `--fake-read-after 2` with a valid fake token delays the read until two
scan rotations have completed. Optional `--fake-outcome drop` records a simulated
physical outcome; choices are `success`, `grasp_fail`, `drop`, and `wrong_bin`.
These fake values are for software checks, not physical evaluation. A successful
final outcome returns exit status 0.

### Simulate no read and one retry

```bash
python3 experiments/run_cycle.py --medium carton --dry-run \
  --retry-once --csv /tmp/carton-no-read.csv
```

`--medium`, `--dry-run`, and `--csv` have the meanings above. Omitting
`--fake-token` makes every scan window empty. `--retry-once` automatically
simulates the one permitted retry, producing two linked `no_read` rows.
The final failure returns exit status 2; that is the expected result of this
check. Unknown tokens also never select a bin. Live retries require operator
input; this switch does not enable unattended retries on hardware.

### Check a trained robomimic checkpoint

```bash
python3 experiments/robomimic_runner.py --medium poly_mailer \
  --checkpoint /path/to/model.pth --dry-run --steps 3
```

| Argument | Meaning |
| --- | --- |
| `--medium poly_mailer` | Require a checkpoint trained for this medium. |
| `--checkpoint /path/to/model.pth` | Replace the placeholder with an actual ACT or DP `.pth` file saved by robomimic. |
| `--dry-run` | Required for this standalone runner. Load on CPU and use synthetic observations without opening hardware. |
| `--steps 3` | Request and print three action predictions. This does not run three parcel cycles. |

Synthetic waypoints and smoke models are not live assets. This checkpoint check
confirms loading and prediction only, not grasping or sorting performance.

## Terminal 1: prepare and start the live server

Stop the recorder and other motion clients. Home explicitly using the
[home guide](../hardware/homing.md), which requires the robot server stopped
before motion. After homing and checking clearance, start the server:

```bash
python3 experiments/launch_nodes.py
```

This starts the follower/gripper server with its configured addresses and port;
there are no arguments in this example. Startup cycles the grippers. Leave it
running. Keep standalone scanner readers stopped so the supervisor can own the
scanner exclusively.

## Terminal 2: run one live parcel cycle

Activate `Xtrainer` and enter the repository root in this terminal as well:

```bash
python3 experiments/run_cycle.py --medium poly_mailer --live \
  --backend robomimic --checkpoint /path/to/model.pth \
  --waypoints experiments/waypoints.local.yaml --label-face top
```

| Argument | Meaning |
| --- | --- |
| `--medium poly_mailer` | Select the parcel workflow and require a matching trained model. |
| `--live` | Open hardware and execute motion. Use exactly one of `--live` or `--dry-run`. |
| `--backend robomimic` | Load ACT/DP in robomimic format. The other backend is `vendor`, which is the default. |
| `--checkpoint /path/to/model.pth` | Replace with the actual trained robomimic checkpoint file. It must match the selected medium. |
| `--waypoints experiments/waypoints.local.yaml` | Load your taught poses, routes, verified limits, and `commissioned: true` setting. This is also the default waypoint path. |
| `--label-face top` | Optional ground-truth evaluation metadata describing the label's starting face. Omit if unknown; never a policy observation. |
| `--csv cycle_logs/cycles.csv` | Optional output CSV; this is the default location when the option is omitted. Rows are appended. |

For vendor ACT, replace the backend/checkpoint pair with
`--backend vendor --checkpoint ckpt/poly_mailer_vendor`. Here `--checkpoint`
names a directory containing `config.pkl`, `dataset_stats.pkl`, and the model.
Optional `--model-name policy_best.ckpt` selects the filename inside it; that is
the default. Robomimic uses a `.pth` file, not the vendor directory.
Choose `top`/`bottom` for flat-media label metadata, or
`top`/`bottom`/`front`/`rear` for cartons. Keep all fake scanner/outcome and
automatic-retry options for software checks.

The supervisor stops requesting policy steps after the scan-pose handoff.
It checks the initial face, then stops the sweep at the first valid read.
Flat media allow one 180° backup; cartons allow three 90° steps. A mapped token
selects a taught bin path for the holding arm. Release and home are scripted.

## Outcomes and recovery

After placement, press `s` for `success`, `g` for `grasp_fail`, `d` for `drop`,
or `w` for `wrong_bin`. The software never infers these physical outcomes from
the gripper command or a completed motion.

On `no_read`, never guess a bin: return along the holding arm's taught receiving
path, release a few centimetres above the surface, and return home. Optionally
record `t` for `tilted_in_grip`, `l` for `label_occluded`, or Enter for `unknown`.
Press `r` only after resetting the same parcel to request its single retry.
The retry is a new CSV row with `retry_of` pointing to the original cycle.
A second failure stops and waits for the operator. Restarting a program does
not identify parcels automatically; do not use a restart to bypass this limit.

On a fault or interruption, the supervisor stops issuing motion and requests
both controllers' emergency stop. It logs `fault` and waits for inspection.
It never releases or homes automatically after a fault. Clear its cause and
recover manually using the home guide before starting another cycle.

CSV logs in `cycle_logs/cycles.csv` include IDs, retry link, medium, policy type,
label face, rotations, token/bin, outcome, optional cause/fault detail, phase
and total times, dry-run marker and control overruns. Operator decision time
is excluded. Use only physical trials for success rates and report retries
separately. Missing ground truth leaves label face blank; the scanner cannot
infer which face was originally labelled.
