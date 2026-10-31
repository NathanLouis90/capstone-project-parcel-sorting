# Inspect, recover, withdraw or home the robot

At the end you know each controller's mode and alarms and, when needed, the arms are recovered, withdrawn from contact, or back at the Xtrainer initial pose.

## Before you start

- Stop `recording/run_control.py`, `robot/launch_nodes.py`, `evaluation/run_cycle.py`, the setup checks and every other robot client, including clients on other computers. State-changing commands refuse to run while a local client is active.
- The PC reaches `192.168.5.1` and `192.168.5.2`, and the controllers accept TCP/IP commands.
- Emergency stop within reach. Keep people clear before any arm is enabled.
- Use one action per command: no action (status), `--inspect-pose`, `--recover`, `--lift-mm` or `--move`.
- Prepare one terminal (see [install](01_install.md#every-new-terminal)).

## Read the status first

1. Read both controllers' mode and alarms before clearing anything. Nothing moves.

   ```bash
   python3 robot/robot_home.py
   ```

   Expect: one line per arm, for example `right (192.168.5.2): mode 5 (enabled and idle), alarms [[], [], [], [], [], [], []]`, then `Status only. No robot state was changed.` Keep this output as evidence.

2. Pick the section that matches the status:

   | Status | Go to |
   | --- | --- |
   | Mode 5, no alarms, arms away from home | [Move to the initial pose](#move-to-the-initial-pose) |
   | Alarm `-2` (collision), contact removed | [Recover after a collision](#recover-after-a-collision) |
   | Alarm `-2` or `117`, tool trapping an obstacle | [Withdraw upward](#withdraw-upward-from-trapped-contact) |
   | Mode 3, alarms `[[116], [], [], [], [], [], []]` | [Recover from an emergency stop](#recover-from-an-emergency-stop-alarm-116) |

## Recover after a collision

1. Remove the contact where it is safe, resolve the cause and release any emergency stop. Then clear the alarm and enable the arm without homing (`--arm left` for the left arm).

   **Enabling energises the arm. Keep people clear.**

   ```bash
   python3 robot/robot_home.py --arm right --recover --clear-errors
   ```

   Expect: `right: mode 5, no alarms. Recovery complete; no target commands sent.` Home as below once the full path is clear.

## Withdraw upward from trapped contact

1. Check clearance above the tool and around every link. Confirm from the mounting that base +Z points upward, away from the surface (not from a camera image).

2. Lift one arm by an explicit distance from 1 to 50 mm, here 10 mm for the right arm.

   **The right arm moves up. Keep the emergency stop within reach.**

   ```bash
   python3 robot/robot_home.py --arm right --lift-mm 10 --base-z-up --clear-errors
   ```

   Expect: the start pose, the requested pose, the `MovL(...)` command, then `Lift complete. No home targets or gripper commands were sent.`

3. Do not retry or relax limits if frame checks, alarm clearing or path checks fail. Remove the obstacle before homing. The 5 % speed cap and User 0/Tool 0 frames stay set afterwards.

4. To investigate an unexpected lift result without moving (idle arm, no alarms):

   ```bash
   python3 robot/robot_home.py --arm right --inspect-pose
   ```

   Expect: modes, alarms, joints, `GetPose()` and the base/flange forward-kinematics readings, then `Status only. No robot state was changed.`

## Recover from an emergency stop (alarm 116)

A supervisor fault that cannot confirm a controlled stop sends a software `EmergencyStop()` to both arms. On this installation only a controller power cycle clears it.

1. Confirm every physical emergency-stop button is released.

2. Switch both controllers off, wait about 30 seconds, switch them on, and wait until both answer.

   ```bash
   nc -zv 192.168.5.1 29999
   nc -zv 192.168.5.2 29999
   ```

   Expect: `succeeded` for both.

3. Run the status command and require empty alarms on both arms. Then home as below, adding `--power-on` only if an arm reports mode 3 without alarms.

Do not use `--software-estop-reset` here: on these controllers its `PowerOn()` reset raised alarm 1009 twice. See [software emergency stop](../reference/hardware.md#software-emergency-stop-alarm-116).

## Release a held parcel

After a confirmed controlled stop (both arms mode 5, no alarms) a parcel may still be held. Be ready to catch it.

**The grippers open at the current pose, then both arms move home.**

```bash
python3 robot/robot_home.py --arm both --move --open-gripper
```

Expect: the grippers open first; if one does not report open, nothing moves. Use `--recover --open-gripper` instead to release without homing.

## Move to the initial pose

1. Check the full path for both arms, their tools and any held object. Remove surface contact first.

2. Home both arms (they move together, stage by stage, at a 10 % speed cap).

   **Both arms move. Keep the emergency stop within reach.**

   ```bash
   python3 robot/robot_home.py --move
   ```

   Expect: `Moving both arms together at 10% global speed cap.` then `Selected arms reached the Xtrainer initial pose.`

3. If an alarm needs clearing or an arm is powered off (mode 3, no alarms), only after resolving the cause:

   ```bash
   python3 robot/robot_home.py --clear-errors --power-on --move
   ```

   Expect: the same two lines as step 2.

Options: `--arm left` or `--arm right` for one arm, `--speed 1..50` (percent), `--timeout` seconds per stage (default 300). Restarting `recording/run_control.py` later repeats its own move to home, so clear both paths first.
See [homing and controller behaviour](../reference/hardware.md#homing-and-controller-behaviour).

## If something goes wrong

- `Stop robot clients first; active PIDs: ...` -> stop those programs and retry.
- `Controller closed the connection` -> another client (DobotStudio Pro, server) holds port 29999; close it.
- Alarm remains after `--recover --clear-errors` -> stop; resolve the physical cause or use the withdrawal. Never disable collision detection or repeat clearing to force motion.
- Alarm 1008 or 1009 -> power-up failed; check the emergency stops and power-cycle the controller instead of retrying.
- Fault, timeout or `Ctrl+C` during motion -> a stop is requested, but may not arrive; use the physical emergency stop and read the status before anything else.
- Loaded contact that the withdrawal cannot release -> follow the manufacturer's recovery procedure ([Operation Guide and FAQ](../provided_dobot/Dobot%20X-Trainer%20Operation%20Guide%20and%20FAQ.pdf)) or contact the Dobot FAE.
