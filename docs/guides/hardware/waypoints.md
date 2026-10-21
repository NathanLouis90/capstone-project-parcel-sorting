# Teach scan, drop, and receiving-return waypoints

Read the [hardware README](README.md#waypoint-names-and-arm-selection) for pose
meanings, arm selection, saved data, and commissioning settings.

## Before starting

1. Complete the repository's device setup and preserve existing calibration.
   Check physical fixture positions against the
   [shared layout reference](README.md#workspace-layout-and-coordinate-frame)
   before teaching poses. Teach scan and release heights on the installation;
   the listed item centres are not Cartesian gripper targets.
2. If necessary, position and lock the leaders with
   `PYTHONPATH=. python3 scripts/3_just_buttonA.py`, then stop that helper with Ctrl+C.
3. Start with no parcel held. Clear both follower paths and keep emergency-stop
   access. Server startup cycles grippers; teleoperation startup homes both arms.
4. Reuse an existing server and teleoperation session if they are already running.
   Do not start competing command clients or restart teleoperation while holding
   a parcel.

## Use three terminals

Prepare [each terminal](../../terminal_commands.md):

```bash
conda activate Xtrainer
cd /home/adiel/dobot_xtrainer
```

### Terminal 1: start the robot server

```bash
python3 experiments/launch_nodes.py
```

Leave this process running throughout teaching.

### Terminal 2: start leader control

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face bottom \
  --project-name waypoint_setup --show-img
```

Wait for `Ok, let's start`. **Do not press green while teaching waypoints.**
Use the relevant leader to position its follower:

1. Keep the leader near its follower's starting posture.
2. Long-press yellow for about two seconds, release, and wait for alignment.
3. Support the leader and short-press yellow to unlock it.
4. Move slowly to the intended waypoint. Keep the other follower home.
5. Hold still and short-press yellow to lock the leader.
6. Long-press yellow to disable following. Disable following on the other arm too.
   Check for `ButtonA: [0] stop servo` on the left and `[1]` on the right when
   disabling an arm that was enabled.
7. Wait about one second before saving. Leave Terminal 2 open with both arms'
   following disabled.

### Terminal 3: save the current position

First position the left follower at the scanner, confirm reading range and
wrist clearance, and disable following on both arms. Then run:

```bash
python3 experiments/teach_waypoints.py --name scan_left
```

Expect `Saved scan_left; review limits and routes before commissioning`.
To check clearance with a parcel, hold it securely at its normal grasp width;
waypoint capture does not require fully closed jaws.

Before switching arms, release the parcel safely under teleoperation and return
the previously used follower home. First position the right follower at the
scanner and disable following on both arms, then run:

```bash
python3 experiments/teach_waypoints.py --name scan_right
```

First position the left follower over bin 0 at the intended release height and
disable following on both arms, then run:

```bash
python3 experiments/teach_waypoints.py --name drop_bin0_left
```

Repeat the positioning, locking, disabling, and saving steps for every remaining
waypoint. Run each command only after reaching its own intended posture:

| Position to reach | Command in Terminal 3 |
| --- | --- |
| Left arm over bin 1 | `python3 experiments/teach_waypoints.py --name drop_bin1_left` |
| Right arm over bin 0 | `python3 experiments/teach_waypoints.py --name drop_bin0_right` |
| Right arm over bin 1 | `python3 experiments/teach_waypoints.py --name drop_bin1_right` |
| Left arm a few centimetres above receiving | `python3 experiments/teach_waypoints.py --name drop_receiving_left` |
| Right arm a few centimetres above receiving | `python3 experiments/teach_waypoints.py --name drop_receiving_right` |

Teach both arms' bin poses even when they release into the same physical bin.
Do not run all save commands at one posture. Saving does not open the gripper;
release the parcel safely under teleoperation before ending the session.

## Replace or inspect a saved pose

Inspect `experiments/waypoints.local.yaml`. Reposition deliberately before
replacing an existing pose:

```bash
python3 experiments/teach_waypoints.py --name scan_left --overwrite
```

For `Stop moving the follower before capture`, disable following on both arms,
wait for the follower to settle, then retry. For a connection timeout, check that
Terminal 1 is running and that its host/port match `LAUNCH_NODES`.

## Before running automatic cycles

1. Keep `commissioned: false` until the entire revised layout and paths are checked.
2. Set `joint_limits_rad` to 12 verified min/max pairs: left J1–J6, then right J1–J6.
   Include wrist cable limits.
3. Set each arm's `rotation_direction` to `1` or `-1` for the verified sweep direction.
4. Teach intermediate poses where direct joint movement could hit a parcel,
   scanner, other arm, or bin rim. End names with `_left` or `_right`.
5. Add intermediate poses to the relevant `routes`. Check drop and home routes
   from every possible final scan rotation, including intermediate read angles.
6. Check whether an intermediate lift is required before unwinding the wrist.
7. Verify receiving-return release heights, grasp retention, stationary scanner
   reads, and all approach/retreat paths.
8. Set `commissioned: true` only after those checks. Recheck it after every save;
   waypoint capture resets it to false.

Do not treat joint-increment and jaw-command checks as proof of parcel clearance
or grasp retention. Follow [live cycle prerequisites](../runtime/evaluation.md#prerequisites)
before operation.

## Check the software without robot movement

Choose a new temporary output file and run these separately:

```bash
python3 experiments/teach_waypoints.py --dry-run --output /tmp/example-waypoints.yaml
python3 experiments/scripted_motion.py --dry-run
```

Inspect the generated example poses and simulation result. Keep the example
waypoints uncommissioned and never use them as calibrated live robot positions.
