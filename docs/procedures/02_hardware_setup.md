# Set up the robot network, USB devices, leaders and cameras

At the end the PC reaches both followers, `config/dobot_settings.ini` holds your camera serials, USB ports and leader calibration, and all three camera images show.

## Before you start

- Complete [software installation](01_install.md).
- Have DobotStudio Pro on a PC that can reach the followers, and the [User Guide](../provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf) (section 3.5) open.
- Connect both leaders, both follower grippers and all three cameras by USB.
- Stop `robot/launch_nodes.py`, `recording/run_control.py` and every other program that uses the leaders, grippers or cameras.
- If `config/dobot_settings.ini` already holds working calibration, skip step 9 (offsets). Do not recalibrate a working setup.
- Prepare one terminal (see [install](01_install.md#every-new-terminal)).

## Steps

1. Configure the followers in DobotStudio Pro (User Guide 3.5): left follower `192.168.5.1`, right follower `192.168.5.2`, payload 0.5 kg, initial poses left `{-90, 0, -90, 0, 90, 90}` and right `{90, 0, 90, 0, -90, -90}`, remote control mode **TCP/IP secondary development**.

   Expect: DobotStudio Pro connects to both arms at those addresses.

2. Give the PC's robot-facing Ethernet port a free address such as `192.168.5.102`, mask `255.255.255.0`, then check both controllers.

   ```bash
   nc -zv 192.168.5.1 29999
   nc -zv 192.168.5.2 29999
   ```

   Expect: `succeeded` for both. Close DobotStudio Pro afterwards; port 29999 accepts one client.

3. Create your local hardware settings file. `-n` never overwrites an existing file.

   ```bash
   cp -n config/dobot_settings.example.ini config/dobot_settings.ini
   ```

   Expect: `config/dobot_settings.ini` exists. Edit only this copy; it is ignored by Git.

4. Allow USB access. Either add your user to the `dialout` group and log in again, or enter your sudo password as `passcode` under `[COMPUTER]` in `config/dobot_settings.ini`.

   ```bash
   sudo usermod -aG dialout $USER
   ```

   Expect: after logging in again, `groups` lists `dialout`.

5. Find the USB ports of both leaders and both grippers. Repeat this after every PC restart or USB reconnection.

   ```bash
   python3 setup/1_find_ports.py
   ```

   Expect: `Success(hand): HAND_LEFT /dev/ttyACM...`, `Success(hand): HAND_RIGHT ...`, two `Success(gripper): ...` lines, and the program exits by itself. Nothing moves.

6. Start the leader button helper.

   ```bash
   python3 setup/3_leader_buttons.py
   ```

   Expect: `button thread init success...` followed by a fast stream of loop times. Both leaders are locked (stiff).

7. Hold each leader handle with both hands, short-press its yellow button to unlock it, move it to the follower initial pose from step 1, then short-press yellow again to lock it. Keep the gripper triggers released.

   Expect: `ButtonA: [0] unlock` / `lock` for the left leader and `[1]` for the right.

8. Stop the helper with `Ctrl+C` and make sure it has exited.

   Expect: the terminal prompt returns. The leaders stay locked.

9. First-time calibration only: save the leader offsets with both leaders still locked at the initial pose.

   ```bash
   python3 setup/2_get_offsets.py
   ```

   Expect: a block per leader with `curr_joints`, `dev(write)`, `gripper open (degrees)` and `gripper close (degrees)`; the program exits by itself and writes `joint_offsets` and `gripper_config` into `config/dobot_settings.ini`.

10. Put the three camera serial numbers into `[CAMERA]` (`top`, `left` wrist, `right` wrist) in `config/dobot_settings.ini`, then open the preview.

    ```bash
    python3 setup/4_check_cameras.py
    ```

    Expect: `Found 3 devices: [...]` (these are the serial numbers), then one window with three images side by side: top, left wrist, right wrist. If `[CAMERA]` still holds placeholders, the program prints the serials and then stops with an error; copy the serials in and rerun.

11. Check that each image comes from the camera named in its slot, then stop the preview with `Ctrl+C` in the terminal.

    Expect: the window closes. Always stop the preview before recording.

Continue with [labels and scanner](03_labels_and_scanner.md).
See [local hardware settings](../reference/hardware.md#local-hardware-settings) for what each INI entry means.

## If something goes wrong

- `nc` fails -> check the cable, the PC address and mask, and that DobotStudio Pro is closed.
- `At least 4 ports should be detected` -> reconnect the leaders and grippers, check `ls /dev/ttyACM* /dev/ttyUSB*`, rerun step 5.
- `Error: find port error` or `Permission denied` on `/dev/tty...` -> redo step 4, then step 5.
- Leaders follow the followers badly or drift after calibration -> repeat steps 6–9 with the leaders exactly at the initial pose.
- A camera fails to open or shows the wrong view -> reconnect its cable, check its serial in `[CAMERA]`, rerun step 10.
