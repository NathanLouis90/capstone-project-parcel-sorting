# Hardware reference

This page explains the cell's hardware, stored poses and controller behaviour. For the steps, follow the procedures:
[hardware setup](../procedures/02_hardware_setup.md),
[labels and scanner](../procedures/03_labels_and_scanner.md),
[workspace](../procedures/04_workspace.md),
[teach waypoints](../procedures/05_teach_waypoints.md),
[check waypoints](../procedures/06_check_waypoints.md) and
[home and recover](../procedures/home_and_recover.md).
Manufacturer manuals: [User Guide V1.1](../provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf) and [Operation Guide and FAQ](../provided_dobot/Dobot%20X-Trainer%20Operation%20Guide%20and%20FAQ.pdf).

All editable settings live in `config/settings.py`; a change takes effect the next time the program that reads it starts. Command-line options override those defaults.

## Robot network

| Device | Address |
| --- | --- |
| Left follower (Nova 2) | `192.168.5.1` |
| Right follower (Nova 2) | `192.168.5.2` |
| PC, robot-facing Ethernet | any free `192.168.5.x`, mask `255.255.255.0` (for example `192.168.5.102`) |

Both controllers must be in TCP/IP secondary development mode, with payload 0.5 kg and the initial poses left `{-90, 0, -90, 0, 90, 90}` and right `{90, 0, 90, 0, -90, -90}` degrees set in DobotStudio Pro. `LAUNCH_NODES` holds the follower addresses and the server port (`6001`, host `127.0.0.1`); `ROBOT_HOME["ARMS"]` holds the addresses used by `robot/robot_home.py`. The dashboard port 29999 accepts one client per controller, so DobotStudio Pro, the robot server and `robot/robot_home.py` cannot hold it at the same time.

## Local hardware settings

Two local files in `config/` are ignored by Git:

| File | Contents |
| --- | --- |
| `dobot_settings.ini` | Camera serials, USB ports and leader calibration. Created from `dobot_settings.example.ini` with `cp -n`, which never overwrites an existing file, so rerunning the copy keeps working calibration. |
| `waypoints.local.yaml` | Taught poses, routes, joint limits and the commissioning flag. See [waypoint file and commissioning](#waypoint-file-and-commissioning). |

INI sections:

| Section | Entries | Written by |
| --- | --- | --- |
| `[COMPUTER]` | `passcode`: sudo password used to `chmod` the USB serial ports when the port helpers scan them. Leave blank if your user can already open `/dev/ttyACM*` and `/dev/ttyUSB*` (for example through the `dialout` group). Keep any password only in this local file. | You |
| `[CAMERA]` | `top`, `left` (left wrist), `right` (right wrist) RealSense serial numbers. | You |
| `[HAND_LEFT]`, `[HAND_RIGHT]` | Leader motor `joint_ids`, `append_id`, `joint_signs`, `start_joints` (radians, the leader posture matching the follower initial pose), `port`, `baud_rate`, `using_sensor`, and the calibrated `joint_offsets` and `gripper_config`. | `port`/`baud_rate`: `setup/1_find_ports.py`; offsets: `setup/2_get_offsets.py` |
| `[GRIPPER_LEFT]`, `[GRIPPER_RIGHT]` | Follower gripper servo `id`, servo endpoints `pos`, and `port`. | `port`: `setup/1_find_ports.py` |

The example values are not calibration for a physical robot. The helpers rewrite the whole INI file through Python's `configparser`, so comments in it are not kept.

### Setup helpers

| Helper | What it does | Settings |
| --- | --- | --- |
| `setup/1_find_ports.py` | Lists `ttyUSB`/`ttyACM` ports (at least 4 required), finds each leader by trying its motor IDs at 2 000 000 and 1 000 000 baud, then assigns the remaining ports to the grippers by pinging their servos. Writes ports to the INI and exits. Moves nothing. Rerun after every PC restart or USB reconnection. | `FIND_PORTS` |
| `setup/3_leader_buttons.py` | Locks/unlocks the leaders with the yellow button so they can be posed; records nothing and drives no follower. Leaders start locked; a short press (under 0.5 s) toggles lock, a long press (over 1 s) toggles the servo flag. Prints its loop time continuously. Stop with `Ctrl+C`; the leaders stay locked. | `LEADER_BUTTONS` |
| `setup/2_get_offsets.py` | Reads both leaders and saves `joint_offsets` (current leader joints minus `start_joints` × `joint_signs`) and `gripper_config` (gripper ID, closed = current trigger angle + 30°, open = current − 0.2°). The leaders must be locked at the follower initial pose with triggers released, and `3_leader_buttons.py` must have exited. Rerunning it replaces working calibration. | `GET_OFFSETS` |
| `setup/4_check_cameras.py` | Prints the serials of the connected RealSense cameras (`Found N devices`), resets them, and shows one window with top, left and right images. Runs until `Ctrl+C`; the cameras stay busy until then. | `CHECK_CAMERAS` (image flips) |

## Robot server and leader controls

`robot/launch_nodes.py` connects to both followers and their grippers and serves them on port 6001. At startup each gripper closes and reopens; it then prints `Starting robot server on port 6001`. Run only one server, and never restart it while a parcel is held. Recording, waypoint teaching, the setup checks and cycles all use this server.

`recording/run_control.py` makes the followers track the leaders. At startup it moves both followers to the initial pose. Leader controls (User Guide 4.1):

| Control | Effect |
| --- | --- |
| Yellow button, short press | Lock or unlock that leader. |
| Yellow button, long press (about 2 s) | Start or stop following for that arm; the follower slowly aligns to the leader first. Stopping prints `ButtonA: [0] stop servo` (left) or `[1]` (right). |
| Green button | Start or stop recording. Not used while teaching waypoints. |
| Trigger | Closes the follower gripper in proportion to how far it is pressed. |

Teleoperation stops when it hits Dobot's speed or position limits (red table light); rerun `recording/run_control.py` to clear it. See [recording](recording.md) for recording behaviour.

## Workspace layout and coordinate frame

The workspace uses a shared layout frame. Its X/Y origin lies between the two arm bases, referenced with the robot at home; Z = 0 is the surface of the EVA board. Dimensions are in millimetres, with a placement tolerance of ±10 mm.

| Item | Size in the board plane | Centre X | Centre Y |
| --- | --- | ---: | ---: |
| EVA board | 700 × 700 mm | 0 | 50 |
| Bin 0 | Not specified | -190 | -270 |
| Bin 1 | Not specified | 190 | -270 |
| Barcode scanner | Not specified | -30 | 80 |
| Receiving area | Not specified | -30 | 150 |

The coordinates are the centres of the physical items. They do not give the gripper position, parcel clearance, scan height or release height. Heights and the sizes of the bins, scanner and receiving area are not specified. If the board edges align with the layout axes, its nominal bounds are X = -350 to 350 mm and Y = -300 to 400 mm.

This layout frame is separate from each controller's base, User and Tool frames; their relationship must be calibrated before these coordinates could become Cartesian robot targets. The runtime uses separately taught joint waypoints for each arm. The layout does not generate those poses or replace calibration, motion limits or handoff tolerances, and ±10 mm is a placement tolerance, not a robot safety limit.

## Parcel dimensions and label faces

| Item | Dimensions | Candidate label faces | Purchase reference |
| --- | --- | --- | --- |
| Poly mailer, fixed bubble-wrap filling | 130 × 190 mm | Top, bottom | [Shopee](https://sg.shp.ee/KEAi1vGk) |
| Carton, exterior | 150 × 75 × 45 mm | Top, bottom, front, rear | [Lazada](https://s.lazada.sg/s.6ELRP?c=d&t=p-i1DjcEO-s2CK0KWD) |
| DL envelope | 110 × 220 mm | Top, bottom | [Lazada](https://s.lazada.sg/s.6ELkQ?c=d&t=p-i3XhIlx-sNuvvNZ) |
| USB HID presentation scanner | See the listing | Not applicable | [Shopee](https://sg.shp.ee/M8FZszsv) |
| Label stock | 100 × 150 mm | Cut an 80 × 40 mm layout for cartons | Not specified |

Purchase links are references from the reimplementation specification, not measurements of the installed items. The configured sizes and faces are in `MEDIA`. Carton front and rear are the long 150 × 45 mm faces, not the 75 × 45 mm ends. An end-on grasp aligns wrist roll with the long axis, so 90° wrist steps expose the four candidate faces. About 25 mm at each end is reserved for the fingertips; a central label stays clear of the grasp.

Mailer filling is fixed so deformation and grasp behaviour stay comparable. The receiving area sits below the top camera and holds one parcel at a time. Mailer pickup uses an elevated platform for the left-arm flip when the label starts facing up, followed by a right-arm corner pickup. The platform's position, size and height must be measured on the installation and checked against both learned pickup paths and the scripted scan, drop and home routes. The same scanner serves both arms.

## Scanner and destination mapping

The scanner is a dedicated USB HID device. Its configured identity (`SCANNER_READER`: device path, name, vendor and product IDs) is checked before exclusive capture; a path alone cannot substitute another device, and the normal keyboard must never be used. A US keyboard layout and presentation/continuous mode keep key decoding consistent. Only one process may own the scanner at a time.

| Token | Bin | Destination |
| --- | --- | --- |
| `DEST-A-S138683` | 0 | Dover |
| `DEST-B-S828608` | 1 | Punggol |

The mapping comes from `MAKE_LABELS["destinations"]`. The cycle supervisor owns the scanner at runtime; recording never opens it, and scan results never enter policy observations. Each runtime scan window opens after the handoff with a fresh cycle ID. Stale, unknown, partial and unmapped input cannot choose a bin. A mapped token stops the sweep; scanner or device failures are faults, and an exhausted healthy sweep is a no-read that uses the receiving-return route. See [runtime](runtime.md).

### Scanner check options

`setup/check_scanner.py`:

| Option | Meaning |
| --- | --- |
| `--simulate TOKEN` | Decode a token without opening a device. A mapped token exits 0; an unknown token gives no destination and exits 2. Tests the mapping, not the physical scanner or label. |
| `--list-devices` | Print input device paths and identities without capturing. |
| `--once` | Capture one valid mapped barcode, then exit (0 on a read, 2 otherwise). |
| `--window 10` | Seconds allowed for `--once`. |
| `--continuous` | Read until `Ctrl+C`. This is the default without `--once`. |
| `--device /dev/input/eventN` | Use this device path; the configured identity must still match. |
| `--debug` | Print key events and decoded characters. |

Stationary reads on every candidate face, and wrist cable slack through the carton rotation, are installation checks; a successful simulated token does not prove them.

## Label layouts and outputs

`setup/make_labels.py` writes Code 128 labels for both destinations in each run. Full-stock labels use the 100 × 150 mm layout for envelopes and mailers; the carton layout is 80 × 40 mm. Both use a 0.25 mm module width and 20 mm bar height, about 52 mm wide for the configured tokens. Printing at actual size keeps those dimensions.

| Option | Meaning |
| --- | --- |
| `--size 100x150` | Full 100 × 150 mm layout (default). `3x4` and `2x3` inch presets also exist. |
| `--size carton` | Compact 80 × 40 mm carton layout. |
| `--outdir DIR` | Output folder; default `output/labels/`. |
| `--combined` | Also write one PDF with both labels side by side (`labels_<size>_combined.pdf`); it may need larger stock. |
| `--no-crop-marks` | Omit the cutting guides. |

Each run writes `label_<size>_<token>.pdf` and barcode PNGs `bc_<token>.png`, for example `label_carton_DEST-A-S138683.pdf`. Regenerating the same size in the same folder replaces those files. Sample PDFs are in [docs/label_examples](../label_examples/). Layout, fonts and destinations are in `MAKE_LABELS`.

## Waypoint names and arm selection

A waypoint is a follower posture saved as six joint angles in radians. `setup/teach_waypoints.py` reads the follower (not the leader) through the robot server. It sends no motion command, does not enable following, does not open the gripper and does not store jaw width. Holding a parcel while teaching helps check reading range, clearance and release geometry.

| Name | Arm | Posture |
| --- | --- | --- |
| `scan_left` | Left | Parcel above the scanner, within reading range and with room to turn the wrist. Used for cartons. |
| `scan_right` | Right | Parcel above the same scanner. Used for envelopes and corner-grasped mailers; check barcode clearance for both. |
| `drop_bin0_left` / `drop_bin0_right` | Named arm | Parcel over the release point inside bin 0. |
| `drop_bin1_left` / `drop_bin1_right` | Named arm | Parcel over the release point inside bin 1. |
| `drop_receiving_left` / `drop_receiving_right` | Named arm | Parcel a few centimetres above the receiving surface, for a no-read return. |

Both arms can reach the same scanner and bins, but each needs its own joint configuration: two scan poses, four bin poses and two receiving-return poses, eight in total. Capture each at its own posture; saving twice at one posture stores identical angles under different names. Every name ends in `_left` or `_right`.

The holding arm is fixed per medium by `MEDIA`, not detected: cartons use the left arm; envelopes and mailers use the right arm after any left-arm assistance, and the assisting left arm returns home before scanning. See [runtime](runtime.md).

Capture samples the selected arm three times and refuses (`Stop moving the follower before capture`) if any joint varies by more than 0.01 rad, so following must be disabled on both arms first. A timeout usually means the server is not running or its host/port differ from `LAUNCH_NODES`. An existing name needs `--overwrite`. `--dry-run --output PATH` writes simulation-only example poses without hardware; they are marked `simulation_only: true`, are refused by every live check and cycle, and never calibrate a robot.

## Waypoint file and commissioning

`config/waypoints.local.yaml` (path `WAYPOINT_FILE`) is local and ignored by Git. It is written atomically as JSON, which is valid YAML.

| Key | Meaning |
| --- | --- |
| `units` | Must be `radians`. |
| `poses` | Name → six joint angles. |
| `routes` | Optional. Destination name → ordered list of intermediate same-arm pose names visited before it; `home_left`/`home_right` routes are used before going home. |
| `joint_limits_rad` | 12 min/max pairs: left J1–J6, then right J1–J6, including wrist cable limits. Every pose must lie inside them. |
| `rotation_direction` | `left` and `right`, each `1` or `-1`: the verified wrist sweep direction. |
| `commissioned` | `true` only after the full layout and paths are checked. Every save resets it to `false`. Full cycles refuse a file that is not commissioned; the setup checks accept it. |

Commissioning covers parcel clearance, grasp retention, release heights, scanner reach and approach/retreat paths for the actual layout. Teach intermediate poses wherever a direct joint move could hit a parcel, the scanner, the other arm or a bin rim, and list them in `routes`. The final read can happen between nominal scan angles, so drop and home routes must work from every possible final wrist rotation; a lift may be needed before unwinding the wrist. The software does not invent safe limits, and checking command increments does not establish physical clearance. Limits taken from the manufacturer's joint ranges are not installation cable limits.

## Waypoint and wrist checks

Both checks use the normal validated motion loop with the running robot server, need neither cameras nor a trained model, accept `commissioned: false`, and only require the poses they visit.

| Check | What moves |
| --- | --- |
| `setup/check_waypoints.py` | One selected arm follows its route to a saved pose; the other arm must stay home. |
| `setup/check_wrist_rotation.py` | Starting at the taught scan pose, the holding wrist (J6) visits offsets 0°, 90°, 180° and 270°. |

Common behaviour:

- Before any command, a preflight simulates every interpolated step against the joint limits and motion limits; a rejected path sends nothing. Preflight does not detect collisions with parcels, the scanner, bin rims or the other arm.
- Each live step needs `MOVE` typed in an interactive terminal. Any other answer stops without moving.
- After each move the measured joints must be within 0.025 rad of the target, or the check stops as a fault.
- `Ctrl+C` or a fault during motion requests a stop through the server's controller connections; this is not a substitute for the physical emergency stop. Neither check releases a parcel or returns home after a cancel or fault.
- Controller status and stop requests go through the server's existing dashboard connections. If a check asks you to restart `robot/launch_nodes.py`, the running server predates this interface: restart it once with empty grippers and all motion clients stopped.

### Waypoint menu

Without arguments, `setup/check_waypoints.py` shows a persistent numbered menu: `home_left`, both arms' scan, bin and receiving-return poses, any extra taught `_left`/`_right` poses, and `q`. Angles are shown in degrees; missing poses show `unrecorded` and send nothing. Home uses the configured initial-pose joints plus any taught `home_left`/`home_right` route. `q` exits at the current pose. `--list` prints the menu without opening any device; `--name NAME` runs one selection and exits, with the same interlock.

**Idle-arm interlock.** Before each selection and every motion command, the measured joints of the arm not selected must be within `SUPERVISOR["waypoint_home_tolerance_rad"]` (0.025 rad, about 1.43°) of home. For example, `scan_left` then `drop_bin0_left` is allowed while the right arm is home; `scan_right` is blocked until `home_left` completes. If both arms start away from home, every move is blocked. Only the selected arm receives motion and gripper commands.

Blocked selections, failed preflights and cancelled moves return to the menu. A controller or communication fault, or a failure during movement, ends the session and requests a stop on both controllers. Every selection starts from the current posture, so check each transition; reaching a destination once does not validate other start postures.

### Waypoint check settings

`WAYPOINT_DEFAULTS` in `config/settings.py`, read once at start (restart after editing):

| Key | Meaning |
| --- | --- |
| `speed_rad_s` | Joint speed, default `0.1`, maximum `SUPERVISOR["joint_speed_rad_s"]` (0.25). |
| `left_gripper`, `right_gripper` | Gripper command sent with each move of that arm: `"open"` (1.0), `"closed"` (0.0) or a number between. Position commands, not force. See [gripper commands](#gripper-commands-in-the-checks). |
| `waypoint_file` | The taught file, default `config/waypoints.local.yaml`. |
| `report_file` | `None` (off) or a filename such as `REPO_ROOT / "cycle_logs" / "waypoint_checks.jsonl"`. Relative paths resolve from the repository root. |

The report appends one JSON line per selection (completed, cancelled, blocked or fault) with the waypoint, measured angles and outcome. It does not run a sorting cycle. Opening the menu or editing the settings sends no command.

### Gripper commands in the checks

The robot driver sends a gripper command `c` as servo position `c × 255`. Per `RUNTIME` (`open_gripper_command` 1.0, `closed_gripper_command` 0.0, confirmed from wrist-camera recordings and used by recording checks, cycles and `robot/robot_home.py --open-gripper`), **1.0 opens the jaws and 0.0 closes them**.

The waypoint menu and the wrist check use the same convention: `"open"` sends 1.0 and `"closed"` sends 0.0, and `--grippers LEFT RIGHT` takes the same numbers (for a left-arm carton check, `--grippers 0 1`: left closed, right open). Give values that match the jaws' current state and watch the jaws at the first `MOVE`; the driver cannot measure the jaw position, so a wrong value is only seen physically.

### Wrist check options

`setup/check_wrist_rotation.py` does not pick up the parcel or move to the scanner first. The holding arm must already be within 0.025 rad of `scan_<arm>`, and `rotation_direction` must be set for that arm. Turns follow `rotation_direction` from the starting wrist angle. At each position the arm settles, then only fresh scans count during the dwell. The sweep always visits all four positions, then leaves the wrist at 270°; release and unwinding are manual. Exit status 0 means at least one mapped read (all matching `--expect-token` when given); no read or a mismatched token gives 2. A single label face may read at only one orientation, so check each starting face in its own trial.

| Option | Meaning |
| --- | --- |
| `--live` / `--dry-run` | One is required. `--dry-run` uses a virtual robot and opens no device; it uses the local waypoint file if present, otherwise marked synthetic poses. |
| `--arm left` / `--arm right` | Holding arm (default left). |
| `--grippers LEFT RIGHT` | Required with `--live`; see [gripper commands](#gripper-commands-in-the-checks). |
| `--label-face` | Starting face, recorded in the report only; it does not change the motion. |
| `--expect-token` | Fail if a different token is read. |
| `--dwell 3` | Stationary scan window per position in seconds (0.1–120, default 3). |
| `--speed 0.1` | Joint speed in rad/s (maximum 0.25). |
| `--report PATH` | Append the result as a JSON line. |
| `--waypoints PATH` | Waypoint file (default `config/waypoints.local.yaml`). |
| `--device` | Dedicated scanner path; the identity check still applies. The live check opens its own scanner reader. |
| `--fake-read-at 0/90/180/270`, `--fake-no-read` | Dry run only: simulate a read at that offset (default 90) or no read. |

A dry run tests software behaviour only and never establishes physical clearance.

## Homing and controller behaviour

`robot/robot_home.py` talks to the Dobot V3 controllers directly over TCP/IP (dashboard port 29999, motion port 30003). It needs neither DobotStudio Pro, leaders, cameras nor the robot server; `--open-gripper` additionally opens the gripper serial ports. The controllers must already accept TCP/IP commands; the script does not change their control mode. Any state-changing action first checks for local robot clients (`launch_nodes.py`, `run_control.py`, `run_cycle.py`, `teach_waypoints.py`, `check_waypoints.py`, `check_wrist_rotation.py`, `3_leader_buttons.py`) and refuses while one runs; it cannot see clients on other computers.

`ROBOT_HOME` supplies addresses, home targets, default arm, ports, speed, timeouts, polling interval, error-clearing delay, inspection samples, stable samples and the `--open-gripper` settings. Options override the arm, speed and stage timeout.

### Homing options

| Option | Meaning |
| --- | --- |
| *(none)* | Read `RobotMode()` and `GetErrorID()` for the selected arms. No clearing, enabling, speed change or motion. Run this first: it keeps the evidence of a stop. |
| `--arm left/right/both` | Select controllers (default both). No leader arms are involved. |
| `--inspect-pose` | Read modes, alarms, joints and pose three times and calculate base/flange forward kinematics. No state change. |
| `--recover` | Stop prior execution and enable the arm after resolving alarms; no home target. Enabling energises the arm. |
| `--lift-mm 1..50` | Move one arm this far along base +Z. Requires a single arm and `--base-z-up`. |
| `--base-z-up` | Your confirmation that base +Z points upward, away from the contacted surface. It measures nothing. |
| `--move` | Two-stage joint move to the Xtrainer initial pose. Both arms move together at each stage by default. |
| `--clear-errors` | Request alarm clearing after resolving the cause. Needs `--recover`, `--lift-mm` or `--move`. |
| `--power-on` | Power an arm in mode 3. Needs a recovery or motion action. |
| `--software-estop-reset` | For an arm in mode 3 whose only alarm is 116 from a software `EmergencyStop()`, with every physical stop released. Needs `--power-on` and `--recover` or `--move`. See [alarm 116](#software-emergency-stop-alarm-116). |
| `--open-gripper` | Open the selected grippers (`[GRIPPER_LEFT]`/`[GRIPPER_RIGHT]` in the INI) before any arm is reset, enabled or moved; a held object drops at the current pose. Motion is refused if a gripper does not report open within `gripper_open_timeout_s`. Needs `--move` or `--recover`. |
| `--speed 10` | Global speed cap in percent, 1–50 (default 10). It stays set afterwards. Lifts are capped at 5 %. |
| `--timeout 300` | Seconds per stage, not per session (default 300). |

Only one action may be given per run. Controller modes: 3 powered off, 4 disabled, 5 enabled and idle, 6 dragging, 7 running, 9 error.

### Alarms and recovery without homing

An alarm array such as `[[-2], [], [], [], [], [], []]` means collision detection (the first group is the controller/algorithm alarms). A leading command return code `-2` instead means the command was rejected because the robot was in alarm. See the [Dobot V3 alarm reference](https://docs.trossenrobotics.com/dobot_cr_cobots_docs/tcpip_protocol/functions.html#geterrorid).

Recovery requests `ClearError()` when asked, checks that alarms cleared, sends `ResetRobot()` to stop prior execution and enables a disabled arm. It opens no motion port, sends no joint target, changes no speed and commands no gripper unless `--open-gripper` is given. Persistent alarms or unexpected modes prevent enabling; mode 3 needs `--power-on`. Success leaves mode 5 with empty alarms.

Already-running server and recorder processes keep their own error flags, so clearing the controller does not recover them; restart them. Restarting teleoperation repeats its startup move to the initial pose, which needs a clear path.

### Software emergency stop (alarm 116)

Supervisor faults first try a controlled stop (`CONTROLLED_STOP`: `ResetRobot()`, then both arms idle, alarm-free and still). If that cannot be confirmed, the supervisor sends `EmergencyStop()` to both controllers, which then report mode 3 with `[[116], [], [], [], [], [], []]`. This happens, for example, after a controller collision alarm, so alarm 116 can appear without anyone pressing a button. Dobot's alarm table describes 116 as a pressed emergency-stop button; a physical button raises the same code. `ClearError()` does not reset it.

The [Dobot V3 TCP/IP guide](https://github.com/Dobot-Arm/TCP-IP-Protocol-6AXis-V3) (`EmergencyStop` entry, 2025-05-08 edition) states that after a software-triggered stop, `PowerOn()` resets and powers the arm. `--software-estop-reset` follows that: `PowerOn()`, wait for mode 4 or 5 with empty alarms, then `ResetRobot()` and `EnableRobot()`. If 116 remains or another alarm appears, it stops before enabling. The V4 `EmergencyStop(mode)` release form does not apply to these V3 controllers.

**On this installation the reset does not work:** `PowerOn()` raised alarm 1009 (power-on failure, communication exception) twice. Alarm 1008 means an emergency stop during power-up. After 1008 or 1009, check the emergency stops and hardware and power-cycle the controller instead of retrying. The working recovery is to switch both controllers off for about 30 seconds and on again; use `--software-estop-reset` only if a firmware update or the Dobot FAE confirms support.

### Withdrawal frames and limits

`--lift-mm` accepts only collision alarms `-2` and `117`. It clears the alarm once, stops prior execution, enables the arm, selects `User(0)` and `Tool(0)` (both must succeed) and reads `GetPose()`. The pose must be stable over three readings and agree with explicit base/flange forward kinematics within 0.5 mm and 0.5°, within five seconds.

The target changes only Z by the requested distance: `MovL(X,Y,Z+distance,Rx,Ry,Rz,User=0,Tool=0,SpeedL=10,AccL=5)`. Orientation stays fixed; the gripper translates with the flange. See the [linear movement reference](https://docs.trossenrobotics.com/dobot_cr_cobots_docs/tcpip_protocol/functions.html#movl). The global speed is capped at 5 % with a 10 % Cartesian ratio (ratios, not a fixed mm/s). The lowered cap and User 0/Tool 0 remain afterwards; restarting the robot server selects Tool 1 for teleoperation again.

A new alarm, a timeout or `Ctrl+C` requests a stop, as does measured X or Y moving more than 2 mm, Z decreasing more than 0.5 mm, or Z passing the endpoint by more than 0.5 mm. Polling and stop requests depend on working communications and are not a certified safety system. Contact forces can shift the arm when it is enabled. An alarm that cannot be cleared, or returns before motion, prevents movement; repeated clearing or disabling collision detection is not a supported way to escape loaded contact.

`--inspect-pose` uses `PositiveSolution` with User 0 and Tool 0 for the measured joints. It is a calculation, not motion, and needs an idle controller without alarms; it cannot recover an arm in error. A difference between `GetPose()` and that calculation can come from the selected frames or motion between readings; once User 0/Tool 0 are selected, a stationary arm should match closely. See the [forward-kinematics reference](https://docs.trossenrobotics.com/dobot_cr_cobots_docs/tcpip_protocol/functions.html#positivesolution). Lift output includes the start and requested poses; path failures include the measured pose, XYZ displacement and the limit that triggered the stop.

### Home targets and fault handling

| Arm | First target (degrees) | Xtrainer initial pose (degrees) |
| --- | --- | --- |
| Left | `[-90, 30, -110, 20, 90, 90]` | `[-90, 0, -90, 0, 90, 90]` |
| Right | `[90, -30, 110, -20, -90, -90]` | `[90, 0, 90, 0, -90, -90]` |

The same targets are used by teleoperation startup (`MANIPULATE_UTILS`), and the initial pose is the home used by the checks and cycles. `--move` enables disabled arms, sets the global speed cap and sends `JointMovJ` with `SpeedJ=100,AccJ=10`. With both arms, each stage sends both targets back to back and waits for both: start and arrival are not synchronised. A stage completes when the joints are within 0.5° of target and the controller is idle over three samples.

These are initial poses, not all-zero joints. The controller's joint trajectory differs from teleoperation's ServoJ interpolation, and neither is a collision-free recovery from an arbitrary posture or surface contact. Active alarms, unexpected modes, rejected commands or malformed replies stop further stages. A fault, timeout or `Ctrl+C` during motion sends a best-effort `ResetRobot()` stop to both controllers; a communication failure can prevent it from arriving. Collision detection and emergency stops are never bypassed.
