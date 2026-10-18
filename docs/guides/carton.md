# Carton recording

Follow the [shared protocol](recording_guide.md). Record 50 fresh demonstrations
covering varied receiving positions and yaw. The holding arm is **left**.

## Grasp and carry

Use only the left arm. Approach along the long axis at 20° or less and pinch within about 25 mm of the end. Keep the right arm home with its gripper closed.

Cycle label faces through top, bottom, front and rear: about 12 to 13 recordings per face. Front/rear are the 150 × 45 mm long sides. Do not teach a roll; present the carton as grasped. The supervisor scans the initial face and up to three further faces in 90° J6 steps.

End at `scan_left`, holding still for about one second. Stop recording before
release or homing. The other arm must be home at handoff.

```bash
python3 experiments/run_control.py --medium carton --label-face top --show-img
```

Change `--label-face` for each assigned face. Review the recorded label face
against the images before accepting the demonstration.
