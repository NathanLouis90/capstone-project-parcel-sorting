# Run and evaluate parcel cycles

## Prerequisites

Teach and commission the [joint waypoints](../hardware/waypoints.md), including receiving
returns for both arms. Train fresh checkpoints. Verify scanner reads at rest
and throughout the candidate-face sequence, tool clearance, joint limits,
cable slack and grasp retention. Stay at the robot with emergency-stop access.

## Software-only checks

```bash
python3 experiments/run_cycle.py --medium carton --dry-run \
  --fake-token DEST-B-S828608 --csv /tmp/carton-cycle.csv
python3 experiments/run_cycle.py --medium carton --dry-run \
  --retry-once --csv /tmp/carton-no-read.csv
python3 experiments/robomimic_runner.py --medium poly_mailer \
  --checkpoint /path/to/model.pth --dry-run --steps 3
```

No token tests recovery; unknown tokens never select a bin. The no-read command
returns exit status 2. Synthetic waypoints and smoke models are not live assets.
The standalone runner prints predictions without commanding a robot.

## Live cycle

Start `python3 experiments/launch_nodes.py` in another terminal. Home explicitly
using the [home guide](../hardware/homing.md). Select the medium manually:

```bash
python3 experiments/run_cycle.py --medium poly_mailer --live \
  --backend robomimic --checkpoint /path/to/model.pth \
  --waypoints experiments/waypoints.local.yaml --label-face top
```

For vendor ACT, use `--backend vendor --checkpoint ckpt/poly_mailer_vendor`.
The checkpoint argument is a directory for vendor ACT and a file for robomimic.
Label face is optional evaluation metadata and never a policy observation.

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
