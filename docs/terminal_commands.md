# Prepare terminals and run guide commands

Read the [terminal syntax reference](README.md#terminal-syntax) for option,
variable, path, and line-continuation meanings. Use Bash on the robot PC.

## Prepare each terminal

Run these commands in every new terminal:

```bash
conda activate Xtrainer
cd /home/adiel/dobot_xtrainer
```

Replace the checkout path if yours differs. Check that this directory contains
`experiments/`, `scripts/`, and `README.md`. Follow the repository installation
procedure once on a new PC; do not repeat installation for every session.

## Choose the terminals for your task

| Task | Instructions |
| --- | --- |
| Record demonstrations | Keep `launch_nodes.py` in Terminal 1 and run `run_control.py` in Terminal 2. Follow the [recording procedure](guides/recording/protocol.md). |
| Teach poses | Keep those two processes running. Disable following on both arms, then save with `teach_waypoints.py` in Terminal 3. Follow the [waypoint walkthrough](guides/hardware/waypoints.md#use-three-terminals). |
| Run a live cycle | Stop the recorder. Keep the server in Terminal 1 and run `run_cycle.py` in Terminal 2. Follow [cycle startup](guides/runtime/evaluation.md). |
| Review, convert, train, or simulate | Use one terminal without starting a robot server. Stop recording before training. |
| Inspect, recover, or home | Follow the [home procedure](guides/hardware/homing.md). Stop command clients before recovery or motion. |

Do not start duplicate servers or competing motion clients. Check each hardware
procedure before startup; server startup cycles grippers and recorder startup
homes both followers.

## Run a guide's example

1. Choose the relevant procedure from the [documentation index](README.md#workflow).
2. Complete its prerequisites before running its command blocks.
3. Replace placeholders such as `/path/to/model.pth` and `EPISODE_ID` with actual
   local paths or episode folder names.
4. Keep shell variable assignments and commands that use them in the same terminal.
5. Copy a complete multiline block. Leave no spaces after a trailing `\`.
6. Check [dry-run effects](README.md#dry-run-effects) before running a dry-run command;
   several tools still create files or append logs.
7. Choose persistent output paths for results you need to retain.
8. Use an entrypoint's `--help` to inspect options when needed. Follow the specific
   setup procedure for numbered hardware calibration helpers instead of assuming
   they accept `--help`.
9. Stop foreground processes with Ctrl+C when the procedure instructs you to do
   so. During hardware motion, use the physical emergency stop when necessary;
   Ctrl+C does not replace it.
