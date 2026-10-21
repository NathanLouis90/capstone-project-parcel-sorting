# Run and evaluate parcel cycles

Prepare [each terminal](../../terminal_commands.md) with `Xtrainer` activated.
Read the [runtime README](README.md) for arm selection, handoff, scan rotations,
checkpoint options, outcomes, retries, and log fields.

## Prerequisites

1. Teach and [commission all waypoints](../hardware/waypoints.md#before-running-automatic-cycles),
   including scan, bin, and receiving-return poses for both arms.
2. Select a fresh trained checkpoint matching the medium and backend.
3. Verify stationary reads on every candidate face, tool clearance, joint/cable
   limits, wrist slack, and grasp retention through the complete sweep.
4. Resolve the [partial-gripper handoff limitation](../recording/README.md#gripper-width-and-handoff)
   before relying on automatic operation with partial-width grasps.
5. Stay at the robot with immediate emergency-stop access during live operation.

## Software-only checks

Run each example separately. These checks need no server, leaders, cameras, or
scanner. Never use synthetic waypoints or smoke models as live assets.

### Simulate a successful cycle

```bash
python3 experiments/run_cycle.py --medium carton --dry-run \
  --fake-token DEST-B-S828608 --csv /tmp/carton-cycle.csv
```

Inspect the printed row and CSV. Expect exit status 0 for a successful outcome.
Use `--fake-read-after 2` to exercise a read after two rotations, or
`--fake-outcome drop` to exercise a physical-outcome log value in simulation.

### Simulate no read and one retry

```bash
python3 experiments/run_cycle.py --medium carton --dry-run \
  --retry-once --csv /tmp/carton-no-read.csv
```

Expect two linked `no_read` rows and exit status 2. Do not add a fake token for
this case. Keep all fake-scanner, fake-outcome, and automatic-retry options out
of live commands.

### Check a trained robomimic checkpoint

Replace `/path/to/model.pth` with an actual ACT or DP checkpoint matching the medium:

```bash
python3 experiments/robomimic_runner.py --medium poly_mailer \
  --checkpoint /path/to/model.pth --dry-run --steps 3
```

Check that three action predictions print. Do not treat this loading check as
proof of physical grasping or sorting performance.

## Terminal 1: prepare and start the live server

1. Stop the recorder and other motion clients.
2. Stop the robot server and [home explicitly](../hardware/homing.md#move-to-the-initial-pose).
3. Clear both paths and start with no parcel held; server startup cycles grippers.
4. Start the server:

```bash
python3 experiments/launch_nodes.py
```

Leave this process running. Keep standalone scanner readers stopped.

## Terminal 2: run one live parcel cycle

1. Prepare this terminal too. Keep the recorder stopped.
2. Select `envelope`, `poly_mailer`, or `carton` to match the physical parcel.
3. Replace the checkpoint placeholder below with a matching trained `.pth` file.
4. Confirm the local waypoint file has verified poses, routes, limits, and
   `commissioned: true` before running:

```bash
python3 experiments/run_cycle.py --medium poly_mailer --live \
  --backend robomimic --checkpoint /path/to/model.pth \
  --waypoints experiments/waypoints.local.yaml --label-face top
```

For vendor ACT, replace the backend/checkpoint pair with
`--backend vendor --checkpoint ckpt/poly_mailer_vendor`, using your actual
checkpoint directory. Keep `config.pkl`, `dataset_stats.pkl`, and the model
inside it. Add `--model-name policy_best.ckpt` only if you need to state the
default explicitly; choose another filename when appropriate.

Set `--label-face` to the known starting face, or omit it when unknown. Use
`top`/`bottom` for flat media and `top`/`bottom`/`front`/`rear` for cartons.
Choose `--csv PATH` if the default `cycle_logs/cycles.csv` is unsuitable.

## Outcomes and recovery

1. After placement, inspect the physical result. Press `s` for success, `g` for
   grasp failure, `d` for a dropped parcel, or `w` for the wrong bin.
2. On `no_read`, let the supervisor follow the commissioned receiving-return
   route. Do not choose a destination manually or guess a bin. Record `t` for
   `tilted_in_grip`, `l` for `label_occluded`, or Enter for `unknown` when prompted.
3. Reset the same parcel before pressing `r` for its single retry. After a second
   failure, stop and inspect. Do not restart the program to bypass the retry limit.
4. On a fault or interruption, keep clear and inspect the cause. The supervisor
   requests an emergency stop and does not release or home automatically.
   Use the [recovery procedure](../hardware/homing.md) before another cycle.
5. Use only physical trials to calculate success rates. Report retries separately
   and use held-out placements when comparing models.
