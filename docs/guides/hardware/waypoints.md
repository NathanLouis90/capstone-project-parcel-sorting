# Save robot positions using the leader arms

A **waypoint** is a saved posture of a follower: the actual robot arm that holds
the parcel. Use the smaller leader handles to position that arm, pause following,
then save its current six joint angles. Direct hand-guiding of the follower is
not required for this workflow.

## What do the names mean?

Both arms use the same barcode scanner. `left` and `right` identify the follower
arm whose position you save.

| Name | Arm | Position to teach |
| --- | --- | --- |
| `scan_left` | Left | Hold the parcel above the scanner, within reading range and with room to rotate the wrist. Used for mailers and cartons. |
| `scan_right` | Right | Hold the parcel above the same scanner using the right arm. Used for envelopes. |
| `drop_bin0_left` / `drop_bin0_right` | Named arm | Hold the parcel over the release point inside bin 0. |
| `drop_bin1_left` / `drop_bin1_right` | Named arm | Hold the parcel over the release point inside bin 1. |
| `drop_receiving_left` / `drop_receiving_right` | Named arm | Hold the parcel a few centimetres above the receiving surface for a no-read return. |

The two bin locations must be reachable by both arms. Save a separate joint
posture for each arm, even when both will release parcels at the same location.
Keep the other follower at home when saving a position.

`teach_waypoints.py --name scan_left` means **save where the left arm is now**.
It does not move the arm to the scanner, open the gripper, or enable following.

## Before starting

Complete the repository README's device setup and calibration. Position the
leaders at their calibrated starting posture using
`PYTHONPATH=. python3 scripts/3_just_buttonA.py` if needed, then stop that helper
with Ctrl+C before starting teleoperation. The helper only controls the leaders;
it does not make the followers track them.

**Startup cycles the grippers, and teleoperation startup moves both followers to
home. Start with no parcel held, both arm paths clear, and emergency-stop access.**
Use one server and one teleoperation process. If they are already running, reuse
them instead of starting additional copies.

## Use three terminals

In **each terminal**, activate the environment and enter the repository:

```bash
conda activate Xtrainer
cd /home/adiel/dobot_xtrainer
```

### Terminal 1: start the robot server

```bash
python3 experiments/launch_nodes.py
```

Leave this terminal running throughout teaching. It provides the robot feedback
that the other two programs read.

### Terminal 2: start leader control

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face bottom \
  --project-name waypoint_setup --show-img
```

Wait for initialization and the `Ok, let's start` message before moving the
leaders. This script performs the usual startup homing.

These required medium/face flags supply recording metadata. In this teaching
session, either leader can control its corresponding follower. **Do not press
the green recording buttons.** No demonstration is recorded unless recording
is started; `waypoint_setup` keeps any accidental recording separate from the
training collections.

To position the left follower at the scanner:

1. Keep the left leader near the follower's starting posture.
2. Long-press its yellow button for about two seconds to enable following.
   Wait for alignment to finish.
3. Support the leader handle and short-press yellow to unlock it.
4. Move the leader slowly until the left follower holds a parcel at the intended
   scanning position. Check reading range, clearance and room for wrist rotation.
5. Hold the leader still and short-press yellow to lock it again.
6. Long-press yellow to disable following. Terminal 2 should print
   `ButtonA: [0] stop servo`. Disable following on the right arm too if it was
   enabled; its message uses `[1]`.
7. Keep both followers still for about one second before saving.

Keep Terminal 2 open, with following disabled on both arms. Pausing this way
lets you save and reposition repeatedly without restarting the program.
**Restarting `run_control.py` runs startup homing again.**

### Terminal 3: save the current position

With the left arm still at the scanner and both arms' following disabled, run:

```bash
python3 experiments/teach_waypoints.py --name scan_left
```

Expect `Saved scan_left; review limits and routes before commissioning`.
The command reads follower feedback only. The parcel remains held where you
positioned it.

To teach another position, return to Terminal 2. Enable following with a long
yellow press, wait for alignment, unlock the relevant leader, then guide its
follower. Lock the leader, disable following on both arms and wait again before
running the matching save command in Terminal 3.

Before switching arms, use teleoperation to release the parcel safely and return
the previously used follower home. Keep its following disabled while positioning
the other arm.

For example, **first position the right follower above the scanner**, then save:

```bash
python3 experiments/teach_waypoints.py --name scan_right
```

**First position the left follower over bin 0's release point**, then save:

```bash
python3 experiments/teach_waypoints.py --name drop_bin0_left
```

Reposition before each save. Running all the save commands at one posture would
store that same posture under different names. Save all eight names in the table.
The capture tool records joint angles only; it does not release the parcel.
Release it under teleoperation before ending the teaching session.

## Where positions are saved

The default file is `experiments/waypoints.local.yaml`. It is local and excluded
from Git. Each pose contains six angles in radians. Existing names are protected;
to replace a pose deliberately, reposition the arm and add `--overwrite`:

```bash
python3 experiments/teach_waypoints.py --name scan_left --overwrite
```

`Stop moving the follower before capture` means the sampled angles changed too
much. Keep following disabled, wait for the arm to settle, then retry.
A connection timeout usually means Terminal 1 is stopped or its host/port differs
from `LAUNCH_NODES` in `experiments/experiments_config.py`.

## Before running automatic cycles

Saving the positions does not finish hardware setup. Keep `commissioned: false`
until the revised layout and all paths have been checked. Each save sets it back
to `false`.

In the saved file, configure:

- `joint_limits_rad`: 12 verified min/max pairs, left J1–J6 followed by right
  J1–J6. Include wrist cable limits; the tool does not invent them.
- `rotation_direction`: `left` and `right`, each `1` or `-1`, for the chosen sweep
  direction. Check stationary scanner reads, wrist travel and cable slack.
- `routes`: optional lists of intermediate poses when a direct joint movement
  could hit the scanner, parcel, another arm or a bin rim.

Teach intermediate poses the same way, using names ending in `_left` or `_right`.
For example, a `drop_bin0_left` route lists poses visited before that drop point;
a `home_left` route lists poses visited before home. Routes must be clear from
every possible final scan rotation, including a read between nominal face angles.
An intermediate lift may be needed before unwinding the wrist.

Verify receiving-return release heights and all approach/retreat paths before
setting `commissioned: true`. Runtime checks constrain joint increments and jaw
positions; they do not prove parcel clearance or grasp retention.

For software checks without robot movement:

```bash
python3 experiments/teach_waypoints.py --dry-run --output /tmp/example-waypoints.yaml
python3 experiments/scripted_motion.py --dry-run
```

For `teach_waypoints.py`, `--dry-run` writes example poses without reading an
arm; `--output /tmp/example-waypoints.yaml` selects the file to create. For
`scripted_motion.py`, `--dry-run` exercises a simulated joint stream and sends
no hardware commands. These are separate programs with different outputs.

The generated example poses are simulation-only and uncommissioned. Do not use
them as live robot positions.
