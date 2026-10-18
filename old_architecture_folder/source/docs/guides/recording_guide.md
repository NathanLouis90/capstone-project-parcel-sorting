# Recording demonstrations

Use the [Policy A guide](policy_a.md) or [Policy B guide](policy_b.md) for the task, arm selection and recorder command. This page covers shared controls and optional links between episodes. Run Bash commands in a terminal at the repository root with Python 3.8 `Xtrainer` activated. Variable assignments are run in that terminal; configuration changes are edits to the named Python file. See [command examples](../../README.md#how-to-use-command-examples).

## Prepare the hardware

Complete the README's [setup](../../README.md#software-setup) and [quick startup](../../README.md#quick-startup). On a new checkout, create your local settings file from `scripts/dobot_config/dobot_settings.example.ini` and calibrate it. Keep existing working settings.

Stop `3_just_buttonA.py` and `5_camera_read.py` before recording; the recorder needs the leaders and cameras. Server startup cycles grippers, and recorder startup can move both followers. Clear both arm paths, even when recording a one-arm task.

## Recorder options

| Argument | Meaning |
| --- | --- |
| `--project-name` | Folder name for this collection; choose any name or episode count |
| `--policy-stage` | `A` or `B`; include it so recordings contain task details needed for preparation |
| `--medium` | `poly_mailer`, `carton` or `envelope` |
| `--demonstrated-bin` | Chosen bin, `0` or `1`, for B; omit for A |
| `--show-img` | Show camera previews |
| `--no-capture-barcode` | Record without scanner reads; this is the default |
| `--capture-barcode` | Save scanner reads during A; see the [barcode guide](barcode_scanning_guide.md) |
| `--source-episode` | Optional path to the completed A episode preceding this B recording |

Defaults are in `RUN_CONTROL` in `experiments/experiments_config.py`. Command-line values override them. Recording a new folder does not register it for training; do that later using [dataset preparation](dataset_preparation.md).

## Align and synchronize the leaders

The yellow **A** and green **B** button labels are unrelated to the policy names.

For each arm you need:

1. Support the leader handle. Short-press yellow **A** for less than 0.5 seconds to unlock, position it at its calibrated initial posture, then short-press again to lock.
2. Hold yellow **A** for more than 2 seconds and release to synchronize the follower. Wait for alignment. The code's threshold is 1 second; the longer hold follows the operating manual.
3. Support the leader and short-press yellow **A** to unlock it for teleoperation. Squeeze the trigger to close the follower gripper; release it to open.

Synchronize only the required arms. An unused arm stays home with its gripper closed. Both arm states and all three cameras are recorded regardless of which arm is synchronized. For envelope A, both arms are needed but their demonstrated movements must be sequential.

## Record each episode

1. Put the parcel in its starting location and both followers at home with closed grippers.
2. Press/release green **B** to start; confirm the recording message.
3. Demonstrate the task described in your policy guide.
4. Return home, then press/release green **B** again to stop. Wait for `Saved episode metadata: ...` before the next episode.
5. Before exiting or resetting the parcel by hand, stop recording, disable synchronization with a long yellow press, support/lock the leaders, and confirm stationary followers. Exit with Ctrl+C.

At least one arm must be synchronized to record. Recording off does not mean teleoperation off. The buttons and software exit are not emergency stops. Interrupting an active recording marks it incomplete.

Episodes are saved in `datasets/<project>/collect_data/<episode_id>/` with three camera image folders, joint/action files, and `episode_metadata.json`. A saved episode starts as unreviewed; it does not prove successful manipulation. Use [dataset preparation](dataset_preparation.md) to review and convert it.

## Optional link between A and B

You can record independent A and B episodes. Linking them is useful when B moves the same parcel from the pose A left at staging; it is not required for training.

Add `--source-episode "$A_EPISODE"` to B's full recorder command, after setting `A_EPISODE` to the actual A episode directory. Still supply `--demonstrated-bin`. A must be completed, nonempty and recorded with the same parcel type. If A saved a scanner read, B's chosen bin must match it.

Do not improve the staged pose by hand between a linked A and B recording. Restart B with a new source path for each new pair; keeping the same argument links later B episodes to the same A. The link saves their relationship only. It does not merge episodes or make the robot run A followed by B automatically.
