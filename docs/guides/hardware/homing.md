# Inspect, recover, withdraw, or home the robot

Prepare [one terminal](../../terminal_commands.md) with `Xtrainer` activated.
Read the [hardware README](README.md#homing-and-controller-behavior) for controller
interfaces, option meanings, frame calculations, speeds, and motion limits.

Use at most one action per invocation: `--inspect-pose`, `--recover`, `--lift-mm`,
or `--move`. Keep the PC connected to the controllers and confirm they already
accept TCP/IP commands. Update `ROBOT_HOME` in `experiments/experiments_config.py`
only when addresses or configured defaults need adjustment; restart after edits.

## Inspect the robot first

Before clearing an alarm, stop `run_control.py`, `launch_nodes.py`, and other
dashboard clients, then capture status. This standalone tool connects directly
to port 29999, which accepts one client per controller:

```bash
python3 experiments/robot_home.py
```

Read and retain the mode/alarm output for both controllers. This command requests
no motion or recovery. Do not enable an arm until the physical cause of its alarm
has been resolved.

## Recover from a collision without homing

1. Stop `run_control.py`, `launch_nodes.py`, and other command clients.
2. Remove contact or obstruction where it is safe to do so, resolve the alarm
   cause, release emergency stops, and keep people clear before enabling.
3. For the right arm, run:

```bash
python3 experiments/robot_home.py --arm right --recover --clear-errors
```

4. Use `--arm left` for the left follower. Add `--power-on` only if the controller
   is powered off and it is appropriate to energize it after resolving the cause.
5. Check status again. Require mode 5 and empty alarm arrays for the recovered arm.
   Stop if persistent alarms or unexpected modes prevent enabling.
6. Check the complete homing path before restarting `launch_nodes.py` and
   `run_control.py` in separate terminals. Clear both paths: recorder startup
   performs its usual initial-pose movement.

If the tool traps an obstacle and contact cannot first be removed safely, keep
other clients stopped and follow the withdrawal procedure below. Do not repeatedly
clear alarms or disable collision detection to force movement.

## Withdraw upward when the tool traps an obstacle

1. Stop every other command client. Do not run teleoperation concurrently.
2. Check clearance above the tool and around every arm link. Keep hands away from
   the contact area while the robot is enabled or moving.
3. Verify from the mounting and coordinate direction that base +Z points upward,
   away from the contacted surface. Do not infer direction from a camera image.
4. Select one arm and an explicit distance from 1 through 50 mm. For a 10 mm
   withdrawal of the right arm, run:

```bash
python3 experiments/robot_home.py --arm right --lift-mm 10 --base-z-up --clear-errors
```

5. Inspect the printed start pose, requested endpoint, and motion command. Do not
   retry or relax limits if frame validation, alarm clearing, or path checks fail.
6. Watch the movement with emergency-stop access. Contact forces may shift the
   arm when enabled. Do not rely on polling or network stop requests as a
   certified safety system.
7. After successful withdrawal, keep teleoperation stopped until the obstacle
   is removed and paths are clear. Remember that speed and selected frames remain
   changed; see [withdrawal behavior](README.md#withdrawal-frames-and-limits).
8. Use the manufacturer's recovery procedure or obtain assistance if loaded
   contact cannot be released through this supported command.

Only collision alarms `-2` and `117` are accepted for this withdrawal. If an alarm
cannot clear or returns before withdrawal, stop. Restarting `run_control.py`
invokes its existing initial-pose movement.

### Inspect an unexpected lift result without moving

Keep command clients stopped. For an idle right controller without alarms, run:

```bash
python3 experiments/robot_home.py --arm right --inspect-pose
```

Retain the mode, alarm, joint, `GetPose()`, and explicit User-0/Tool-0 forward-
kinematics readings. Compare them using the [frame explanation](README.md#withdrawal-frames-and-limits).
Inspection does not recover an arm still in error mode. Do not repeat movement
to collect evidence or relax limits while the cause remains unknown.

## Move to the initial pose

1. Stop `run_control.py`, `launch_nodes.py`, and any other command clients,
   including clients on other computers.
2. Release emergency stops and resolve alarm causes. Remove surface contact.
3. Check the full path for both arms, their tools, and any held object. Use a
   supported withdrawal first if contact prevents safe homing.
4. Run:

```bash
python3 experiments/robot_home.py --move
```

5. If alarms need clearing or an arm needs power, request those explicitly only
   after resolving their causes:

```bash
python3 experiments/robot_home.py --clear-errors --power-on --move
```

6. Use `--arm left` or `--arm right` for one follower; the default is both, moved
   sequentially. Adjust `--speed` only within 1–20 percent, and `--timeout` when a
   different per-stage limit is needed. Defaults are 10 percent and 300 seconds.
7. Check that each stage reaches its configured target and the controller is idle.
   Consult [target angles and completion checks](README.md#home-targets-and-fault-handling).
8. On a fault, timeout, or interruption, inspect before restarting. Use the
   physical emergency stop when needed; a network stop request may not arrive.

Do not use either homing sequence as a collision-free recovery plan from an
arbitrary posture or surface contact. Do not disable collision detection or
bypass emergency stops. Grippers are not commanded by the home script.

## Verification

Inspect the current pose without moving:

```bash
python3 experiments/robot_home.py --arm right --inspect-pose
```

Use the [practical robot checks](../../../tests/README.md) to inspect taught
waypoints separately. Verify actual movement and clearance on the installation
before relying on a path; neither pose inspection nor simulation establishes clearance.
