# Poly mailer recording

Follow the [shared protocol](recording_guide.md). Record 50 fresh demonstrations
covering varied receiving positions and yaw. The holding arm is **left**.

## Grasp and carry

Use only the left arm. Pinch near one short end with a tilted approach. Keep bubble-wrap filling fixed and the right arm home with its gripper closed.

Alternate 25 top and 25 bottom label faces. If the label faces up, roll left J6 180° immediately after lifting, in the same direction each time. Otherwise do not roll. Arrive label-down. The runtime retains one 180° backup sweep.

End at `scan_left`, holding still for about one second. Stop recording before
release or homing. The other arm must be home at handoff.

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face top --show-img
```

Change `--label-face` for each assigned face. Review the recorded label face
against the images before accepting the demonstration.
