# Record episodes

The result is a set of pick-to-scan demonstrations under `datasets/<medium>_<label_face>/collect_data/`, ready for review.

## Before you start

- Complete [hardware setup](02_hardware_setup.md), [workspace preparation](04_workspace.md), and [waypoint checks](06_check_waypoints.md). `scan_left` and `scan_right` must be taught.
- Confirm stationary scanner reads and wrist cable slack through the scan sweep. Stop `setup/check_scanner.py` and every other setup helper.
- Open two terminals. In each, run:
  ```bash
  conda activate Xtrainer
  cd ~/dobot_xtrainer
  ```
- Clear both follower paths, hold no parcel, and keep the emergency stop within reach. Server startup cycles both grippers; recorder startup homes both followers.

## Start the server and recorder

1. In Terminal 1, start the robot server and leave it running for the whole session.

   **Both grippers cycle. Keep the emergency stop within reach.**
   ```bash
   python3 robot/launch_nodes.py
   ```
   Expect: `Starting robot server on port 6001`. Leave it running.

2. In Terminal 2, start the recorder. Replace `poly_mailer` with `envelope` or `carton`, and `bottom` with the label face in front of you (`top`/`bottom`; cartons also `front`/`rear`).

   **Both followers move to home.**
   ```bash
   python3 recording/run_control.py --medium poly_mailer --label-face bottom --show-img
   ```
   Expect: `Recording project: poly_mailer_bottom`, then `Ok, let's start`, and three camera views.

## Enable following

3. Put each leader near its follower's posture. Hold that leader's yellow button for about 2 seconds, then release.
   **The follower moves to match its leader.**
   Expect: the follower aligns to the leader ("dynamic approach").
4. Support the leader and short-press yellow (under 0.5 s) to unlock it.
   Expect: the leader moves freely and the follower tracks it.
5. Enable only the arms the medium uses (see below). Keep an unused leader locked and aligned with its follower at home.

## Record one episode

6. Place one parcel with the label centred on the selected face, clear of the fingertips. Start with both followers home and grippers open.
7. Press and release green, then start moving within about 0.5 s.
   Expect: the status light turns green and frames are saved.
8. Demonstrate the grasp and carry for the medium (below). Finish at the scan pose holding the parcel securely, with the other arm home.
9. Hold still for about 1 second, then press and release green.
   Expect: the status light returns to yellow; a new folder exists under `collect_data/`.
10. Release the parcel and return home outside the recording. Disable following (long-press yellow) before resetting the parcel by hand.

Repeat steps 6–10 until you have 50 accepted demonstrations per medium across varied receiving positions and yaw. See [scan poses and label schedules](../reference/recording.md#scan-poses-and-label-schedules).

## Medium-specific demonstrations

### Envelope (`--medium envelope`)

- Use both arms. Alternate top and bottom labels: 25 accepted episodes per face.
- Slide the envelope to an overhanging edge with the left arm.
- Pinch the short edge with the right gripper, fingertips within about 30 mm of the edge. Return the left arm home.
- Top-facing label: roll right J6 180° right after lifting, always in the same direction. Bottom-facing label: no flip.
- End at `scan_right` with the label facing down.

### Poly mailer (`--medium poly_mailer`)

- Use the right arm only. Keep the left follower at home with its leader locked and aligned (or its following disabled).
- Keep the bubble-wrap filling fixed. Alternate top and bottom labels: 25 accepted episodes per face.
- Grasp a corner margin with the right gripper, clear of the label and contents, with enough material to avoid slipping or tearing.
- End at `scan_right` with the left arm home.

### Carton (`--medium carton`)

- Use the left arm only. Keep the right follower home with its leader locked and aligned.
- Cycle top, bottom, front and rear labels: 12–13 accepted episodes per face (front/rear are the long 150 × 45 mm sides).
- Approach along the long axis at 20° or less and pinch within about 25 mm of the end. Hold securely; do not force the jaws fully closed.
- Present the carton as grasped, without a wrist roll. End at `scan_left`.

## Change the label face or finish

11. Stop any active episode with green, release the parcel under teleoperation, return both arms home, lock both leaders and disable following.
12. Stop the recorder in Terminal 2 with Ctrl+C.
    Expect: the terminal prompt returns. Keep Terminal 1 running.
13. To record another face, clear both paths and repeat step 2 with the new `--label-face`.

Continue with [review episodes](08_review_episodes.md).

## If something goes wrong

- No `Ok, let's start` after about 5 seconds -> check the robot network and TCP/IP mode; see [hardware setup](02_hardware_setup.md).
- Green does nothing -> enable following on at least one arm first (step 3); frames are saved only while an arm follows.
- `[Warn]: recording control period overrun` repeats -> close other programs and camera previews; overruns are counted in the episode metadata.
- Red light and the recorder exits -> a pose or joint safety limit was hit. Clear the workspace, restart the recorder, and reject any partial episode during review.
- A camera assertion stops the recorder -> check that camera with `setup/4_check_cameras.py`, then restart.
- A follower faults or will not move -> follow [home and recover](home_and_recover.md).
