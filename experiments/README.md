# Robot operation

Run from the repository root in the Python 3.8 `Xtrainer` environment.

| Program | Purpose |
| --- | --- |
| `launch_nodes.py` | Start the follower/gripper server |
| `run_control.py` | Record a required medium and label face; scanner stays off |
| `teach_waypoints.py` | Read and save a manually positioned follower pose |
| `run_cycle.py` | Pick, scan, place or recover, home, and log a cycle |
| `scripted_motion.py` | Shared validated 25 Hz joint stream; software-only CLI |
| `run_inference.py` | Vendor and simulated policy-step adapters |
| `robomimic_runner.py` | ACT/DP adapter and hardware-free checkpoint check |
| `robot_home.py` | Inspect status; recover/home only when explicitly requested |

See [recording](../docs/guides/recording/README.md), [waypoints](../docs/guides/hardware/waypoints.md)
and [cycle evaluation](../docs/guides/runtime/evaluation.md). Edit
`experiments_config.py` for motion and handoff defaults. Keep calibrated poses
and verified joint/cable limits in ignored `waypoints.local.yaml`.

Hardware startup can move both followers. Stay at the robot with emergency-stop
access. After a fault the cycle stops and waits; it never homes automatically.
