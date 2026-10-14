# Return to the Xtrainer initial pose from a terminal

Run the `bash` command blocks below in a terminal from the repository root with `Xtrainer` activated. Commands with motion flags move hardware; follow the preparation steps before running them.

`experiments/robot_home.py` connects directly to the existing Dobot V3 TCP/IP
interfaces. It does not require DobotStudio, leader arms, cameras, gripper
initialization, or the ZMQ robot server. The computer must still have network
access to both controllers, and the controllers must already accept TCP/IP
commands. This script does not change the controller's control mode.

Edit `ROBOT_HOME` in `experiments/experiments_config.py` for arm addresses and
targets, the default arm selection, ports, speed, timeouts, polling interval,
error-clearing delay, inspection samples, and stable samples. CLI arguments
override the arm, speed, and stage timeout defaults. Restart the script after
editing. Existing default values and motion limits are preserved; motion and
recovery still require an explicit CLI action.

## Inspect the robot first

From `/home/adiel/dobot_xtrainer/experiments`, run:

```bash
python3 robot_home.py
```

This only reads `RobotMode()` and `GetErrorID()` for `192.168.5.1` and
`192.168.5.2`. It does not clear alarms, enable arms, change speeds, or move.
Capture this output after a stop, before clearing alarms, to preserve evidence
of the cause.

## Recover from a collision without homing

An alarm list such as `[[-2], [], [], [], [], [], []]` identifies collision
detection in the V3 controller/algorithm alarm array. This differs from `-2`
as the leading command return code, which indicates that a command was rejected
because the robot is in alarm status. See the distributor's
[Dobot V3 protocol reference](https://docs.trossenrobotics.com/dobot_cr_cobots_docs/tcpip_protocol/functions.html#geterrorid).

Stop both `run_control.py` and `launch_nodes.py`, remove the contact or obstruction,
and release any emergency stops before attempting recovery. For the right arm:

```bash
python3 robot_home.py --arm right --recover --clear-errors
```

This requests `ClearError()`, checks that alarms have cleared, sends
`ResetRobot()` to stop previous motion, and enables the arm if it is disabled.
It does not open the motion port, send joint targets, change speeds, or command
grippers. Enabling energizes the arm; keep people clear of the robot. If power
is off, explicitly add `--power-on` after resolving the cause. Persistent alarms
or unexpected modes prevent enabling.

Check status again. The recovered arm must report mode 5 and empty alarm arrays.
Then restart `launch_nodes.py` in one terminal and `run_control.py` in another.
The latter still executes its existing initial pose movement during startup, so
check the entire path before restarting teleoperation. Existing robot objects
retain their error flags, so clearing the controller alone does not recover
already running client and server processes.

## Withdraw upward when the tool traps an obstacle

If the tool is pressing against a horizontal surface and prevents removing an
obstacle, use a short linear withdrawal before homing. Stop all other command
clients first. Check clearance above the tool and around every arm link, and
keep hands away from the contact area while the robot is enabled or moving.

The command moves along the robot's base +Z axis, using User 0. This points
upward for an upright base installation. Do not infer that direction from the
camera image; verify the mounting and coordinate direction. `--base-z-up`
records that confirmation. For example, to withdraw the right arm by 10 mm:

```bash
python3 robot_home.py --arm right --lift-mm 10 --base-z-up --clear-errors
```

Use `--arm left` for the left arm. An explicit distance from 1 through 50 mm is
required. The command clears the collision alarm once, stops previous execution,
enables the arm, selects `User(0)` and `Tool(0)`, and reads its current flange
pose with parameter-free `GetPose()`, as used by the V3 SDK. Both frame selection
commands must succeed before the pose is read or movement is sent. It requires
three stable comparisons with the previous pose, agreement with explicit
base/flange forward kinematics within 0.5 mm and 0.5 degrees, and stable joint
readings while collecting those values. The pose checks run for at most five
seconds before refusing movement.

The script constructs an absolute target from that measured pose, changing only
Z by the requested positive distance. It sends
`MovL(X,Y,Z+distance,Rx,Ry,Rz,User=0,Tool=0,SpeedL=10,AccL=5)`. Translation
is in the base frame, and the requested orientation stays unchanged. With fixed
orientation, the attached gripper translates along the same direction even
though Tool 0 denotes the flange. See the
[linear movement reference](https://docs.trossenrobotics.com/dobot_cr_cobots_docs/tcpip_protocol/functions.html#movl).

The earlier relative movement command was replaced with this explicit endpoint
after an installation reported a path-check failure. Read-only inspection showed
matching base/flange readings afterward, but did not establish the cause of the
earlier failure. The change does not relax any movement limits. Review the printed
start pose, requested endpoint, and motion command when evaluating recovery.

This sends no home targets, gripper commands, or collision setting changes. It
caps global speed at 5 percent, with a 10 percent Cartesian speed ratio. These
are ratios, not a fixed speed in mm/s. The lowered global cap remains afterward.
The selected global user and tool frames also remain at 0 afterward. Restarting
the existing robot launcher selects Tool 1 for teleoperation again.

The script checks completion against the measured base-frame flange pose and
requests a stop if a new alarm occurs, the motion times out, or Ctrl+C is pressed.
It also requests a stop if measured X or Y deviates over 2 mm, Z decreases over
0.5 mm, or Z exceeds the requested endpoint by over 0.5 mm. Polling and stop
requests depend on working communication and are not a certified safety system.
Contact forces may shift the arm when it is enabled.

Only collision alarms `-2` and `117` are accepted for this withdrawal. If the
alarm cannot clear or returns before withdrawal, the script refuses further
movement. Do not repeatedly clear alarms or disable collision detection to force
movement. Use the manufacturer's recovery procedure or obtain assistance if the
loaded contact cannot be released through the supported command.

After successful withdrawal, keep teleoperation stopped until the obstacle is
removed. Restarting `run_control.py` invokes its existing initial pose movement.

### Inspect an unexpected lift result without moving

If the lift reports a departure from the requested path, keep all command
clients stopped and inspect the readings before retrying movement:

```bash
python3 robot_home.py --arm right --inspect-pose
```

This reads modes, alarms, joints, and the current selected-frame pose three
times. It also asks the controller to calculate forward kinematics for those
joints with explicit User 0 and Tool 0, using `PositiveSolution`. This calculation
does not command movement. Inspection does not clear alarms, enable the arm,
select different frames, change speeds, open the motion port, or command the
gripper. It requires an idle controller without alarms; it does not recover
an arm that is still in error mode.

Compare `GetPose()` to the base/flange calculation. A difference can reflect
different selected coordinate frames or movement between the separate readings;
it does not by itself prove unintended robot motion. The previous lift command
selects User 0 and Tool 0, so a stationary arm should produce closely matching
Cartesian readings after that selection has taken effect. See the
[controller forward kinematics reference](https://docs.trossenrobotics.com/dobot_cr_cobots_docs/tcpip_protocol/functions.html#positivesolution).

Lift output now includes the start pose and requested endpoint. A path failure
includes the measured pose, XYZ displacement, and exact limit that triggered
the stop request. Do not relax those limits or repeat motion to collect evidence
while the source of the unexpected result remains unknown.

## Move to the initial pose

Stop `run_control.py`, `launch_nodes.py`, and any other robot command clients.
Release emergency stops and resolve the physical cause of any alarm. Remove
surface contact and confirm clearance along the entire path for both arms,
their tools, and anything held by the grippers. The script checks known local
client processes, but cannot detect every controller client on other computers.

```bash
python3 robot_home.py --move
```

If alarms need clearing or an arm needs power, explicitly request those actions
after resolving the cause:

```bash
python3 robot_home.py --clear-errors --power-on --move
```

Use `--arm left` or `--arm right` to select one arm. The command uses the same
two joint targets as `robot_pose_init()` in `scripts/manipulate_utils.py`, in
degrees:

| Arm | First target | Final Xtrainer initial pose |
| --- | --- | --- |
| Left | `[-90, 30, -110, 20, 90, 90]` | `[-90, 0, -90, 0, 90, 90]` |
| Right | `[90, -30, 110, -20, -90, -90]` | `[90, 0, 90, 0, -90, -90]` |

It enables disabled arms, sets a global speed cap of 10 percent, and sends
`JointMovJ` commands with `SpeedJ=100,AccJ=10`. Arms move sequentially, and each
stage waits for measured joints within 0.5 degrees of the target and an idle
controller across three samples. Grippers are not commanded. The global speed
cap remains lowered afterward; `--speed` accepts 1 through 20 percent.

These are the Xtrainer initial poses, not an all-zero joint pose. Their targets
come from the existing setup, but the controller's joint movement trajectory
differs from the teleoperation script's ServoJ interpolation. Neither sequence
is a collision-free recovery plan from arbitrary poses or surface contact.

Active alarms, unexpected operating modes, rejected commands, or malformed
responses prevent further stages. During movement, a fault, timeout, or Ctrl+C
triggers a best-effort `ResetRobot()` stop request. If communication fails, that
request may not reach the controller; use the physical emergency stop if needed.
This script does not disable collision detection or bypass emergency stops.

## Verification

Run the hardware-free tests from the repository root:

```bash
python3 -m unittest discover -s tests -p test_robot_home.py -v
```

The script has been checked with simulated controllers. Actual movement and
clearance must be verified on the installation before relying on the path.
