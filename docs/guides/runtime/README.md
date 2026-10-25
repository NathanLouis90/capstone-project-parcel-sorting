# Runtime: meaning and behavior

Use [cycle execution and evaluation](evaluation.md) for software checks, live
startup, outcome entry, retries, and recovery. This README describes the current
implementation, including assumptions that are not automatic perception.

## Holding-arm selection

The operator selects `--medium`. `MEDIA` in `experiments/experiments_config.py`
then supplies the expected holding arm and active policy arms:

| Medium | Policy arms during pickup | Expected arm at scan/drop |
| --- | --- | --- |
| Envelope | Both; left can slide/assist and right grasps | Right |
| Poly mailer | Both; left flips on the platform when needed, right grasps a corner | Right |
| Carton | Left; right stays home | Left |

The current code does not infer parcel type or the holding arm from cameras or
grasp sensors. Selecting a different carrier at runtime based on which scan
pose is reached is a possible future change; it has not been implemented. Both
arms may participate in envelope and mailer pickup, but the left must return
home before the right-arm scan handoff. The mailer platform flip is learned
from demonstrations; it is not a scripted platform trajectory. Use newly
trained checkpoints for this right-arm mailer workflow. Existing left-arm
mailer checkpoints do not match it.

## Policy handoff and scanning

The supervisor begins at home and requests learned actions until the configured
holding arm reaches its scan pose. The shared handoff check compares forward-
kinematics position and orientation, requires the other arm home, and requires
at least 0.5 seconds of settled joints. Both gripper commands must currently be
near 1.0. That [partial-grasp limitation](../recording/README.md#gripper-width-and-handoff)
can reject a securely held parcel and is not a physical grasp detector.

Once handoff succeeds, learned action requests stop and a fresh scanner window
is armed for the cycle. The supervisor holds the initial face still, then rotates
J6 only if there is no accepted read:

| Medium | Backup rotations |
| --- | --- |
| Envelope or mailer | At most one 180° rotation |
| Carton | At most three 90° rotations |

The first valid mapped token chooses the bin. Stale, partial, unknown, or
unmapped data cannot select a destination. Device failures are faults; exhausting
a healthy scan sweep without a mapped token is `no_read`.

## Drop routes and return paths

The medium chooses the arm; the barcode chooses bin 0 or bin 1. The selected
route is therefore a name such as `drop_bin0_left` or `drop_bin1_right`. Each
arm needs its own six-joint posture even when both use the same physical bin.
Release and homing are scripted, preserving the holding command until release.

A no-read cycle follows `drop_receiving_left` or `drop_receiving_right`, releases
a few centimetres above receiving at the taught height, and returns home. It
never guesses a destination. Both arms' poses/routes and verified joint/cable
limits belong in the commissioned local waypoint file.

## Outcomes, retries, and faults

Physical outcomes are operator-entered: `success`, `grasp_fail`, `drop`, or
`wrong_bin`. A gripper command or completed path does not prove physical success.
Optional no-read causes are `tilted_in_grip`, `label_occluded`, or `unknown`.

One operator-requested retry is allowed after resetting the same parcel. It
creates a new CSV row whose `retry_of` points to the original cycle. A second
failure stops for the operator. Restarting a program does not identify parcels
or reset a real parcel's retry history automatically.

Faults and interruptions stop further motion commands and request both
controllers' emergency stop. The cycle logs `fault`; it does not release or home
automatically. Network requests are not a substitute for physical emergency-stop
access or the installation's recovery procedure.

Controller status and network stop requests go through `launch_nodes.py`, which
owns each controller's single dashboard connection on port 29999. Stops use a
separate ZMQ request socket, but still depend on a responsive launcher and
controller connection. Restart the launcher after updating its status/stop
interface, with empty grippers and all motion clients stopped. Do not open a
standalone dashboard client alongside it.

## Runtime options

### Simulation

| Argument | Meaning |
| --- | --- |
| `--medium carton` | Use the carton cycle, with the left holding arm and up to three 90° scan rotations. Other choices are `envelope` and `poly_mailer`. |
| `--dry-run` | Simulate the robot and scanner. With no checkpoint, use a simulated policy; no model is trained or loaded. |
| `--fake-token DEST-B-S828608` | Supply a simulated valid barcode for bin 1, Punggol. `DEST-A-S138683` selects bin 0, Dover. |
| `--csv /tmp/carton-cycle.csv` | Append the result to this output CSV and print the cycle row in the terminal. Choose another path to keep runs separate. |

`--fake-read-after 2` delays the simulated read until two completed rotations.
`--fake-outcome` accepts `success`, `grasp_fail`, `drop`, and `wrong_bin` as
simulated operator outcomes. Fake values are not physical evaluation data.
A successful final outcome exits with status 0.

Omitting `--fake-token` produces empty scan windows. `--retry-once` simulates the
single permitted retry and yields two linked no-read rows; the final failure
returns exit status 2. Unknown fake tokens never select bins. Fake-scanner,
fake-outcome, and automatic-retry controls are restricted to software checks.
With no checkpoint, a cycle dry run uses a simulated policy and loads/trains no
model. Software-only examples need no hardware services.

### Standalone checkpoint checks

| Argument | Meaning |
| --- | --- |
| `--medium poly_mailer` | Require a checkpoint trained for this medium. |
| `--checkpoint /path/to/model.pth` | Replace the placeholder with an actual ACT or DP `.pth` file saved by robomimic. |
| `--dry-run` | Required for this standalone runner. Load on CPU and use synthetic observations without opening hardware. |
| `--steps 3` | Request and print three action predictions. This does not run three parcel cycles. |

This check confirms loading and prediction, not physical task performance.
Smoke models and synthetic waypoints are not live assets.

### Live cycles

| Argument | Meaning |
| --- | --- |
| `--medium poly_mailer` | Select the parcel workflow and require a matching trained model. |
| `--live` | Open hardware and execute motion. Use exactly one of `--live` or `--dry-run`. |
| `--backend robomimic` | Load ACT/DP in robomimic format. The other backend is `vendor`, which is the default. |
| `--checkpoint /path/to/model.pth` | Replace with the actual trained robomimic checkpoint file. It must match the selected medium. |
| `--waypoints experiments/waypoints.local.yaml` | Load your taught poses, routes, verified limits, and `commissioned: true` setting. This is also the default waypoint path. |
| `--label-face top` | Optional ground-truth evaluation metadata describing the label's starting face. Omit if unknown; never a policy observation. |
| `--csv cycle_logs/cycles.csv` | Optional output CSV; this is the default location when the option is omitted. Rows are appended. |

Exactly one of `--live` or `--dry-run` is required. The default backend is
`vendor`. Vendor checkpoints are directories containing `config.pkl`,
`dataset_stats.pkl`, and the model; `--model-name policy_best.ckpt` is the default
model filename. Robomimic checkpoints are `.pth` files. The selected model must
match the medium, and smoke checkpoints are refused for live operation.

`--label-face` is optional ground-truth evaluation metadata. It supports
`top`/`bottom` for flat media and `top`/`bottom`/`front`/`rear` for cartons, and
stays blank when unknown. Scanner reads cannot infer the originally labelled
face. It is never a policy input.

## Logs and evaluation

The default `cycle_logs/cycles.csv` appends cycle IDs, retry links, medium,
policy type, label face, rotations, token/bin, outcome, optional cause/fault
detail, phase and total times, the dry-run marker, and control overruns. Operator
decision time is excluded. Success rates use physical trials only; simulations
and retries are distinguished from first attempts.

Learned and scripted actions use the paced control loop and shared action checks.
Those checks constrain commands, not parcel clearance, contact force, or grasp
retention. Commissioned routes and physical evaluation remain necessary.
