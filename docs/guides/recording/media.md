# Recording by medium

Use the [shared recording protocol](README.md) for startup, buttons, timing,
metadata and review. Collect 50 fresh accepted demonstrations per medium,
spread over varied positions and yaw throughout the receiving zone.

Keep the robot server running in Terminal 1. Run one of the commands below in
Terminal 2 after [preparing both terminals](../../terminal_commands.md).

| Shared argument | Meaning |
| --- | --- |
| `--medium envelope`, `poly_mailer`, or `carton` | Record the named parcel type and choose its default dataset project. This does not automatically park the other arm. |
| `--label-face top` | Record that the label starts facing upward at receiving. Change this value as the schedule below requires. |
| `--show-img` | Show camera previews during teleoperation. |

Each example starts a hardware session and homes both followers. It does not
start recording an episode until you press the green button.

| Medium | Holding arm | Label schedule | Runtime backup scan |
| --- | --- | --- | --- |
| Envelope | Right; left assists the initial slide | Alternate 25 top and 25 bottom | One 180° J6 roll |
| Poly mailer | Left | Alternate 25 top and 25 bottom | One 180° J6 roll |
| Carton | Left | Cycle top, bottom, front, rear; 12–13 per face | Up to three 90° J6 rolls |

For flat media, teach a 180° carry flip when the label faces upward and no flip
when it faces downward. Use the same roll direction each time and arrive
label-down. Keep the label clear of the fingertips. Confirm stationary scanner
reads and wrist cable slack before recording.

## Envelopes

Use the left arm to slide the envelope to an overhanging edge, then return that
arm home. Pinch the short edge with the right gripper, keeping fingertips within
about 30 mm of the edge. For a top-facing label, roll right J6 180° immediately
after lifting. End at `scan_right`, holding still for about one second.

```bash
python3 experiments/run_control.py --medium envelope --label-face top --show-img
```

## Poly mailers

Keep bubble-wrap filling fixed. Use the left gripper to pinch near one short
end from a tilted approach. The right arm stays home with its gripper closed.
For a top-facing label, roll left J6 180° immediately after lifting. End at
`scan_left`, holding still for about one second.

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face top --show-img
```

## Cartons

Approach along the long axis at 20° or less and pinch within about 25 mm of the
end. The right arm stays home with its gripper closed. Front and rear are the
150 × 45 mm long sides. Present the carton as grasped; do not teach a roll.
End at `scan_left`, holding still for about one second. The supervisor handles
the scanner sweep after handoff.

```bash
python3 experiments/run_control.py --medium carton --label-face top --show-img
```

For envelope and mailer bottom-face demonstrations, replace `--label-face top`
with `--label-face bottom`. For cartons, use `top`, `bottom`, `front`, or `rear`
to match the actual labelled face. Stop the episode and disable following on
both arms before restarting the recorder with another face value; restarting
homes both followers. See the shared guide for optional project/output arguments.

Stop recording before release or
homing, with the idle arm home. Confirm the assigned face in the images before
accepting each demonstration.
