# Architecture

How the code is organized, from the programs you run down to the hardware
drivers, and how a sorting cycle moves through it.

## Layers

```
entrypoints   setup/  robot/  recording/  training/  evaluation/  tools/
                 │ thin scripts: parse arguments, call the library
                 ▼
library       parcel_sorting/
                 runtime/    cycle supervisor, validated motion loop, live runtime, hardware checks
                 training/   dataset preparation, training jobs, reports, menu
                 ────────────────────────────────────────────────────────────
                 hardware/   Dobot followers, leaders, grippers, cameras, ZMQ server/client, robot_home
                 policies/   robomimic ACT/DP policy-step adapter, simulated policy
                 data/       episode recording format, metadata, checks, curation
                 ────────────────────────────────────────────────────────────
                 safety/     kinematics, joint/workspace limits, handoff check (pure numpy)
                 scanning/   HID barcode reader and destination mapping
                 utils.py, control_timing.py
                 │
                 ▼
settings      config/settings.py, config/dobot_settings.ini, config/waypoints.local.yaml
                 │
                 ▼
bundled       robomimic-r2d2/ (ACT/DP training and models), third_party/ (ACT model, Dynamixel and Feetech SDKs)
```

Imports point downward only:

| Package | Imports from |
| --- | --- |
| `safety`, `scanning`, `utils` | `config` only |
| `hardware` | `safety`, `utils` |
| `policies` | `safety`, robomimic |
| `data` | `safety` |
| `runtime` | `hardware`, `policies`, `data`, `safety`, `scanning` |
| `training` | `data`, `safety`, robomimic |

Programs in the stage folders contain the operator-facing logic for one task
(`recording/run_control.py`, `setup/teach_waypoints.py`, ...) or are a few
lines that call a library `main()` (`evaluation/run_cycle.py`,
`robot/robot_home.py`, `training/train_models.py`). Nothing imports from the
stage folders.

## Where to find things

| Question | Look in |
| --- | --- |
| Change a speed, limit, tolerance, IP, port or path | `config/settings.py` |
| Camera serials, USB ports, leader calibration | `config/dobot_settings.ini` (local) |
| Taught poses, routes, joint limits | `config/waypoints.local.yaml` (local) |
| What happens during a cycle | `parcel_sorting/runtime/cycle.py` |
| Why a command was rejected | `parcel_sorting/safety/inference_safety.py`, `parcel_sorting/safety/handoff.py` |
| How joints are streamed at 25 Hz | `parcel_sorting/runtime/scripted_motion.py` (`MotionLoop`) |
| How the live robot, cameras and stop requests are wired | `parcel_sorting/runtime/hardware_runtime.py` |
| How a checkpoint becomes robot actions | `parcel_sorting/policies/robomimic_policy.py` |
| How recordings become training data | `parcel_sorting/training/workflow.py` |
| Training menu prompts | `parcel_sorting/training/menu.py` |
| ACT/DP robomimic configs | `robomimic-r2d2/robomimic/scripts/config_gen/parcel_sorting_gen.py` |
| Episode files and metadata | `parcel_sorting/data/recording.py`, `parcel_sorting/data/dataset_metadata.py` |
| Robot controller protocol | `parcel_sorting/hardware/robots/dobot_api.py`, `parcel_sorting/hardware/robot_home.py` |

## Processes

Live work uses two processes that talk over ZMQ on port 6001:

- `robot/launch_nodes.py` is the robot server. It owns both follower
  connections and the grippers. Only one may run.
- One client at a time sends commands through it: `recording/run_control.py`
  (teleoperation and recording), `setup/check_waypoints.py`,
  `setup/check_wrist_rotation.py` or `evaluation/run_cycle.py`.

`robot/robot_home.py` talks to the controllers directly (dashboard port
29999). It refuses to move while the server or a motion client is running.
Training and dataset tools never open hardware.

## Policy-step contract

ACT and Diffusion Policy share one interface, so the supervisor does not care
which one is running:

```
policy.reset()
action = policy.step({"qpos": 14 joint/gripper values, "images": {"top", "left_wrist", "right_wrist"}})
# action: 14 values (left J1–J6, left gripper, right J1–J6, right gripper)
```

The contract is written down as `Policy` in
`parcel_sorting/policies/interface.py`, next to `POLICY_LOADERS`, the registry
that `evaluation/run_cycle.py --policy NAME` chooses from. `robomimic` (ACT and
DP) is the only registered type today: `RobomimicPolicy` loads a `.pth`
checkpoint, normalizes inputs with the checkpoint's statistics, and parks the
arm that a medium does not use. `SimulatedPolicy` stands in for dry runs.

## Cycle flow

`Cycle` in `parcel_sorting/runtime/cycle.py` is built from three skills that
can also be called on their own: `pick(start)`, `scan(cycle_id)` and
`place(bin_index or None)`. `run()` chains them and logs the attempt.

1. **Pick.** The policy runs until the holding arm reaches its scan pose. Each
   action passes `validate_action` (finite values, joint step, joint limits,
   jaw-tip workspace) before `MotionLoop` streams it at 25 Hz.
2. **Handoff.** `HandoffCheck` requires the holding arm at the scan pose
   (forward kinematics within tolerance), closed gripper commands, the other
   arm at home, and 0.5 s of settled joints. Learned control then ends.
3. **Scan.** The supervisor opens a scan window and rolls J6 only as needed:
   one 180° turn for flat media, up to three 90° turns for cartons.
4. **Place.** The first valid token selects a taught bin route; a no-read
   returns the parcel to receiving. All scripted motion uses the same
   validated loop.
5. **Log.** The robot returns home, the operator records the outcome, and one
   CSV row is appended to `cycle_logs/cycles.csv`.

Faults request a controlled stop of both arms and never home automatically.
Barcode tokens, bins and label-face metadata never enter the policy inputs.
See [runtime](runtime.md) for the details.

## Media

`MEDIA` in `config/settings.py` defines each medium: holding arm, active arms,
label faces, wrist rotation step and number of turns.

| Medium | Policy arms | Holds at scan | Label recovery |
| --- | --- | --- | --- |
| envelope | both | right | learned carry flip, then one 180° wrist turn if needed |
| poly_mailer | right (left held at home) | right | one 180° wrist turn |
| carton | left (right held at home) | left | up to three 90° wrist turns |

Every list of media in the code is read from `MEDIA`; nothing else names them.

## Extending the system

**Add a medium** (for example moving from poly mailers to envelopes or cartons):

1. Add or edit its `MEDIA` entry in `config/settings.py` (holding arm, active
   arms, label faces, wrist rotation step and count).
2. Teach and check the holding arm's scan, bin and receiving poses, including
   enough J6 range for every wrist turn
   ([check waypoints](../procedures/06_check_waypoints.md)).
3. Record, review and train with `--medium NAME`
   ([procedures 07–09](../README.md#procedures)), then run cycles with the same
   medium. The supervisor, recorder, review and training menu need no code change.
4. Write its evaluation protocol as a new procedure, following
   [11_evaluate_poly_mailer.md](../procedures/11_evaluate_poly_mailer.md).

**Add a policy type** (for example a VLA):

1. Write a class that implements `Policy` (`policy_type`, `reset`, `step`,
   optional `warmup`) in a new module under `parcel_sorting/policies/`.
2. Register a loader in `POLICY_LOADERS`; import heavy libraries inside it.
3. Run it with `evaluation/run_cycle.py --policy NAME --checkpoint PATH`. Its
   actions pass the same validation, handoff check, scan and placement, and its
   rows are logged with its `policy_type`.
4. If it needs its own training, add the trainer under `parcel_sorting/training/`
   and an entrypoint in `training/`; the robomimic menu stays as it is.

**Change the task flow** (for example a planner or agent that decides what to
do next): call the `Cycle` skills directly, or write a new supervisor in
`parcel_sorting/runtime/` that reuses `MotionLoop`, `HandoffCheck` and
`validate_action`. Every robot command must still go through `MotionLoop`, so
the safety checks apply whatever decides the next step.

**Add a setting**: put it in `config/settings.py` in the section of the program
that reads it.

## Limits of the software checks

Runtime forward kinematics constrains the jaw tips only. Physical
commissioning must still cover the parcel body, fixtures, the clearance
between the arms and cable travel. Gripper feedback is a command estimate, so
the operator decides whether a grasp or drop happened.
