# Hardware: meaning and behavior

Use [parcel preparation](media.md), [scanner checks and label printing](barcodes.md),
[waypoint teaching](waypoints.md), and [inspection/recovery/homing](homing.md)
for step-by-step instructions. This README explains the hardware, stored poses,
controller behavior, and command options behind those procedures.

## Workspace layout and coordinate frame

The measured workspace uses a shared layout frame. Its X/Y origin is between
the two arm bases, referenced with the robot in its home pose. Z = 0 is the
surface of the EVA board. All dimensions and coordinates below are in
millimetres, with a placement tolerance of ±10 mm.

| Item | Size in the board plane | Centre X | Centre Y |
| --- | --- | ---: | ---: |
| EVA board | 700 × 700 mm | 0 mm | 50 mm |
| Bin 0 | Not specified | -190 mm | -270 mm |
| Bin 1 | Not specified | 190 mm | -270 mm |
| Barcode scanner | Not specified | -30 mm | 80 mm |
| Receiving area | Not specified | -30 mm | 150 mm |

The coordinates describe the centres of the physical items. They do not specify
the gripper position, parcel clearance, scan height, or release height. Heights
and the dimensions of the bins, scanner, and receiving area have not been
specified. If the board edges align with the layout X/Y axes, its nominal bounds
are X = -350 to 350 mm and Y = -300 to 400 mm.

This shared layout frame is separate from each arm controller's base, User,
and Tool frames. Their relationship must be calibrated before converting these
coordinates into Cartesian robot targets. The runtime still uses separately
taught joint waypoints for each arm; this layout does not generate those poses
or replace existing calibration, motion limits, or handoff tolerances. The
±10 mm value describes physical placement tolerance, not a robot safety limit.

## Parcel dimensions and label faces

| Item | Dimensions | Candidate label faces | Purchase reference |
| --- | --- | --- | --- |
| Poly mailer, fixed bubble-wrap filling | 130 × 190 mm | Top, bottom | [Shopee](https://sg.shp.ee/KEAi1vGk) |
| Carton, exterior | 150 × 75 × 45 mm | Top, bottom, front, rear | [Lazada](https://s.lazada.sg/s.6ELRP?c=d&t=p-i1DjcEO-s2CK0KWD) |
| DL envelope | 110 × 220 mm | Top, bottom | [Lazada](https://s.lazada.sg/s.6ELkQ?c=d&t=p-i3XhIlx-sNuvvNZ) |
| USB HID presentation scanner | See the purchased scanner listing | Not applicable | [Shopee](https://sg.shp.ee/M8FZszsv) |
| Label stock | 100 × 150 mm | Cut an 80 × 40 mm layout for cartons | Not specified |

Purchase links are references from the supplied reimplementation specification,
not measurements of the installed items. Carton front/rear are the long
150 × 45 mm faces, rather than the 75 × 45 mm ends. An end-on grasp aligns wrist
roll with the long axis, exposing the four candidate faces in 90° steps. About
25 mm at each end is reserved for fingertips; central placement keeps the label
clear of the grasp.

Mailer filling is fixed so deformation and grasp behavior remain comparable.
Receiving sits below the top camera, with one parcel at a time and no intermediate
platform. The same scanner serves both arms.

## Scanner and destination mapping

The scanner is a dedicated USB HID device. Its configured identity is checked
before exclusive capture; a path alone is not sufficient to substitute another
device. A US keyboard layout and supported presentation/continuous mode keep
key decoding consistent. Only one process should own the scanner at a time.

| Token | Destination |
| --- | --- |
| `DEST-A-S138683` | Bin 0, Dover |
| `DEST-B-S828608` | Bin 1, Punggol |

The cycle supervisor owns the scanner during runtime. Recording does not open it
or include scanner results in policy observations. Each runtime scan window is
armed after handoff with a fresh cycle ID. Stale, unknown, partial, and unmapped
input cannot choose a bin. A mapped token stops the sweep; scanner/device
failures are faults, while an exhausted healthy sweep is a no-read and uses the
receiving-return route.

### Scanner command options

`--simulate TOKEN` decodes a supplied token without opening an input device. The
mapped result exits with status 0; an unknown token yields no destination and
status 2. This tests mapping, not physical scanner/label quality. `--help` prints
the full scanner option list and exits.

| Argument | Meaning |
| --- | --- |
| `--list-devices` | Print input device paths and identities without starting exclusive capture. |
| `--once` | Capture one valid mapped barcode, then exit. |
| `--window 10` | Allow up to 10 seconds for the one-shot read. This value is in seconds. |
| `--device /dev/input/eventN` | Optional: replace `eventN` with the actual scanner path from the listing. Configured name/vendor/product must still match. |
| `--debug` | Optional: print scanner key events and decoded characters while troubleshooting. |
| `--continuous` | Optional: keep reading until stopped with `Ctrl+C`; this is also the default when `--once` is omitted. |

Without `--once`, continuous capture is the default. The capture process grabs
the dedicated scanner exclusively; the normal keyboard must never be used as
its device. Stationary reads on every candidate face, plus wrist cable slack
through carton rotation, are installation checks rather than consequences of a
successful simulated token.

## Label layouts and outputs

Full-stock labels use a 100 × 150 mm layout for envelopes and mailers. The
carton layout is 80 × 40 mm and fits the nominated carton faces after cutting.
Both retain a barcode module width of 0.25 mm and bar height of 20 mm, about
52 mm wide for the configured destination tokens. Printing without scaling
preserves those dimensions.

| Argument | Meaning |
| --- | --- |
| `--size 100x150` | Generate full 100 × 150 mm layouts for envelopes and poly mailers. |
| `--size carton` | Select the preset for compact 80 × 40 mm carton-face layouts. |
| `--outdir barcode_scanning/labels` | Optional output folder; this is the default. Each run writes labels for both destinations. |
| `--combined` | Optional: also create one PDF with both destination labels side by side. |
| `--no-crop-marks` | Optional: omit the cutting guides from the PDFs. |

Default outputs are beneath `barcode_scanning/labels/`; sample PDFs are beneath
`barcode_scanning/label_examples/`. Each generation writes both destinations,
PDFs, and barcode PNGs. Carton filenames include
`label_carton_DEST-A-S138683.pdf`, `label_carton_DEST-B-S828608.pdf`, and, with
`--combined`, `labels_carton_combined.pdf`. The combined sheet places destinations
side by side and may need larger stock. Regenerating the same size in the same
folder replaces those generated files.

## Waypoint names and arm selection

A waypoint is a follower posture saved as six joint angles in radians. Leaders
are the smaller handles used to position followers; the capture tool reads the
follower, not the leader. It does not command movement, enable following, open
the gripper, or store jaw width. Holding a parcel during teaching helps check
reading range, clearances, and release geometry.

| Name | Arm | Position to teach |
| --- | --- | --- |
| `scan_left` | Left | Hold the parcel above the scanner, within reading range and with room to rotate the wrist. Used for mailers and cartons. |
| `scan_right` | Right | Hold the parcel above the same scanner using the right arm. Used for envelopes. |
| `drop_bin0_left` / `drop_bin0_right` | Named arm | Hold the parcel over the release point inside bin 0. |
| `drop_bin1_left` / `drop_bin1_right` | Named arm | Hold the parcel over the release point inside bin 1. |
| `drop_receiving_left` / `drop_receiving_right` | Named arm | Hold the parcel a few centimetres above the receiving surface for a no-read return. |

`scan_left` and `scan_right` can put the parcel over the same scanner, but each
arm requires its own joint configuration. The same applies to each shared bin:
there are four bin-drop poses, two scan poses, and two receiving-return poses,
eight required poses in total. A single capture must occur at that pose's own
intended posture; consecutive save commands at one posture would save identical
angles under different names.

Current runtime carrier selection is fixed by `MEDIA`: mailers and cartons use
the left arm, and envelopes use the right after left-arm assistance. It does not
detect the carrier automatically. Envelope pickup can use both policy arms; the
assisting left arm returns home before scanning. See [runtime arm selection](../runtime/README.md#holding-arm-selection).

### Files, stability checks, and commissioning

The default `experiments/waypoints.local.yaml` is local and excluded from Git.
It contains radians, a `poses` mapping, optional `routes`, verified joint limits,
rotation directions, and the `commissioned` flag. Saving a pose resets
`commissioned` to false. The tool uses atomic replacement; its JSON output is
valid YAML. Existing pose names require `--overwrite` for replacement.

The live capture samples the selected arm three times and refuses capture if
joint variation exceeds 0.01 rad. Both arms' following is paused before capture.
A timeout usually indicates a stopped server or mismatched configured host/port.

`joint_limits_rad` holds 12 min/max pairs for left J1–J6 followed by right J1–J6,
including wrist cable limits. `rotation_direction` gives `left` and `right` each
`1` or `-1`. The software does not invent safe limits or establish physical
clearance by checking command increments.

A route is an ordered list of intermediate named poses before a destination.
For example, a `drop_bin0_left` route lists poses visited before that drop point,
and `home_left` lists poses before home. Intermediate names end in `_left` or
`_right`. The final read can occur between nominal scan angles, so routes must
work from every possible final wrist rotation. A lift may be needed before
unwinding the wrist. Commissioning covers parcel clearance, grasp retention,
release heights, scan reach, and approach/retreat paths for the actual layout.

### Software-only waypoint checks

`teach_waypoints.py --dry-run --output PATH` writes simulation-only,
uncommissioned example poses without reading hardware.
`scripted_motion.py --dry-run` exercises a simulated joint stream without sending hardware commands.
They are separate programs; generating example waypoints does not calibrate a
robot or commission a path.

## Homing and controller behavior

`experiments/robot_home.py` uses the existing Dobot V3 TCP/IP interfaces directly.
It needs neither DobotStudio, leaders, cameras, gripper initialization, nor the
ZMQ server. The PC must reach the controllers and they must already accept TCP/IP
commands; this script does not change their control mode.

`ROBOT_HOME` in `experiments/experiments_config.py` supplies addresses, targets,
default arm selection, ports, speed, timeouts, polling interval, error-clearing
delay, inspection samples, and stable samples. CLI arguments override arm,
speed, and stage timeout. Changes take effect on the next invocation.

### Homing command options

| Argument | Meaning |
| --- | --- |
| `--arm right` / `--arm left` | Select one follower controller. The default is `both`; `--arm both` makes that explicit. No leader arms are involved. |
| `--inspect-pose` | Read joints/pose and calculate base/flange forward kinematics without moving or changing controller state. |
| `--recover` | Stop prior execution and enable the selected arm after resolving alarms; do not send a home target. Enabling energizes the arm. |
| `--lift-mm 10` | Move the selected arm 10 mm along base +Z. Requires one arm, a distance from 1 through 50 mm, and `--base-z-up`. |
| `--base-z-up` | Confirm you checked that base +Z points upward, away from the contacted surface. Does not measure or change that direction. |
| `--move` | Execute the two-stage joint movement to the configured Xtrainer initial pose. Defaults to both arms, sequentially. |
| `--clear-errors` | Request alarm clearing after resolving the cause. Requires `--recover`, `--lift-mm`, or `--move`. |
| `--power-on` | Explicitly request power if the selected controller is in powered-off mode 3. Requires a recovery or motion action. |
| `--speed 10` | Set the requested global speed cap as a percentage, from 1 through 20. Default: 10. Withdrawal also has the stricter cap described below. |
| `--timeout 300` | Allow up to 300 seconds per stage, not per whole session. Default: 300 seconds. |

At most one action is selected. With none, the script reads `RobotMode()` and
`GetErrorID()` for `192.168.5.1` and `192.168.5.2`; it does not clear alarms,
enable arms, change speeds, or move. Capturing these readings before clearing
preserves evidence after a stop.

### Recovery without home motion

An alarm array such as `[[-2], [], [], [], [], [], []]` identifies collision
detection in the V3 controller/algorithm alarm array. A leading command return
code `-2` instead means the command was rejected because the robot was in alarm
status. See the [Dobot V3 alarm reference](https://docs.trossenrobotics.com/dobot_cr_cobots_docs/tcpip_protocol/functions.html#geterrorid).

Recovery requests `ClearError()` when asked, verifies alarms cleared, sends
`ResetRobot()` to stop prior execution, and enables a disabled arm. It opens no
motion port, sends no joint target, changes no speed, and commands no gripper.
Enabling energizes the arm. Persistent alarms or unexpected modes prevent
enabling. Powered-off mode 3 requires the explicit `--power-on` request.
Successful recovery leaves mode 5 and empty alarms.

Already-running client/server robot objects retain their error flags. Clearing
the controller alone therefore does not recover those processes. Restarting
teleoperation repeats its startup initial-pose movement, which is a separate
motion requiring a clear path.

### Withdrawal frames and limits

Withdrawal moves along base +Z using User 0. This is upward for an upright base
installation, but `--base-z-up` records the operator's mounting/direction check;
it does not measure direction. A camera view is not that check. The selected
arm and explicit distance are required, with distance limited to 1–50 mm.

The script clears an accepted collision alarm once, stops prior execution,
enables the arm, selects `User(0)` and `Tool(0)`, then reads parameter-free
`GetPose()` as in the V3 SDK. Both frame-selection commands must succeed before
pose reading or motion. Pose validation requires three stable comparisons with
the previous pose, agreement with explicit base/flange forward kinematics within
0.5 mm and 0.5 degrees, and stable joints while collecting readings. Validation
has a five-second limit.

The absolute target changes only measured Z by the requested positive distance.
The command is `MovL(X,Y,Z+distance,Rx,Ry,Rz,User=0,Tool=0,SpeedL=10,AccL=5)`.
Orientation stays fixed; the attached gripper translates in the same base
direction even though Tool 0 denotes the flange. See the [linear movement reference](https://docs.trossenrobotics.com/dobot_cr_cobots_docs/tcpip_protocol/functions.html#movl).

This explicit endpoint replaced an earlier relative command after an installation
reported a path-check failure. Later read-only inspection found matching
base/flange readings but did not establish the earlier failure's cause. The
replacement does not relax movement limits.

Withdrawal sends no home targets, gripper commands, or collision-setting
changes. Global speed is capped at 5 percent with a 10 percent Cartesian ratio;
these are ratios, not a fixed mm/s speed. The lowered global cap and selected
User 0/Tool 0 remain afterward. Restarting the existing robot launcher selects
Tool 1 for teleoperation again.

A new alarm, timeout, or Ctrl+C triggers a stop request. The script also requests
a stop when measured X or Y deviates over 2 mm, Z decreases over 0.5 mm, or Z
exceeds the endpoint by over 0.5 mm. Polling and stop requests depend on working
communications and are not a certified safety system. Contact forces can shift
the arm when enabling.

Only collision alarms `-2` and `117` are accepted for withdrawal. An alarm that
cannot clear or returns before motion prevents further movement. Repeated alarm
clearing or disabling collision detection is not a supported way to force escape
from loaded contact.

`--inspect-pose` reads modes, alarms, joints, and the selected-frame pose three
times, then uses `PositiveSolution` for those joints with explicit User 0 and
Tool 0. This is a calculation, not motion. It requires an idle controller without
alarms and does not clear alarms, enable, select frames, change speed, open the
motion port, or command the gripper. It cannot recover an arm still in error.

A difference between `GetPose()` and the explicit base/flange calculation can
reflect selected frames or motion between separate readings; it does not alone
prove unintended movement. After User 0/Tool 0 selection has taken effect, a
stationary arm should closely match. See the [forward-kinematics reference](https://docs.trossenrobotics.com/dobot_cr_cobots_docs/tcpip_protocol/functions.html#positivesolution).
Lift output includes the start and requested endpoint; path failures include the
measured pose, XYZ displacement, and exact limit that caused the stop request.

### Home targets and fault handling

The two-stage targets match `robot_pose_init()` in `scripts/manipulate_utils.py`,
with angles in degrees:

| Arm | First target | Final Xtrainer initial pose |
| --- | --- | --- |
| Left | `[-90, 30, -110, 20, 90, 90]` | `[-90, 0, -90, 0, 90, 90]` |
| Right | `[90, -30, 110, -20, -90, -90]` | `[90, 0, 90, 0, -90, -90]` |

The home command enables disabled arms, sets the default global cap to 10
percent, and sends `JointMovJ` with `SpeedJ=100,AccJ=10`. Arms move sequentially.
Each stage waits for joints within 0.5 degrees of target and an idle controller
across three samples. It does not command grippers. The global speed cap remains
lowered; `--speed` supports 1–20 percent, and `--timeout` defaults to 300 seconds
per stage, not per session.

These are Xtrainer initial poses, not all-zero joints. The controller's joint
trajectory differs from teleoperation's ServoJ interpolation. Neither is a
collision-free recovery plan from arbitrary postures or surface contact. The
script checks known local client processes but cannot detect every client on
other computers.

Active alarms, unexpected modes, rejected commands, or malformed responses stop
further stages. A fault, timeout, or Ctrl+C during motion triggers a best-effort
`ResetRobot()` stop request. Communication failure can prevent that request from
reaching the controller. Collision detection and emergency stops are not bypassed.

### Verification scope

Use `python3 experiments/robot_home.py --arm right --inspect-pose` to inspect
the current right-arm pose without moving. The [practical robot checks](../../../tests/README.md)
provide separate wrist, waypoint, and full-cycle checks. Software checks do not
establish installation clearance or physical motion safety.
