# Envelope recording

Follow the [shared protocol](recording_guide.md). Record 50 fresh demonstrations
covering varied receiving positions and yaw. The holding arm is **right**.

## Grasp and carry

Use the left arm to slide the envelope to an overhanging edge, then return the left arm home. Pinch the short edge with the right gripper, keeping fingertips within about 30 mm of the edge.

Alternate 25 top and 25 bottom label faces. If the label faces up, roll right J6 180° immediately after lifting, in the same direction each time. If it faces down, do not roll. Arrive label-down. The runtime retains one 180° backup sweep.

End at `scan_right`, holding still for about one second. Stop recording before
release or homing. The other arm must be home at handoff.

```bash
python3 experiments/run_control.py --medium envelope --label-face top --show-img
```

Change `--label-face` for each assigned face. Review the recorded label face
against the images before accepting the demonstration.
