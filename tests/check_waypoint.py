"""Choose real-robot waypoints using waypoint_config.py; see tests/README.md."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from experiments.hardware_checks import waypoint_main


if __name__ == '__main__':
    sys.exit(waypoint_main())
