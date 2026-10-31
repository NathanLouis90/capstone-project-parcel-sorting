"""Move one arm to taught waypoints from a menu; each move needs MOVE."""
import sys

from parcel_sorting.runtime.hardware_checks import waypoint_main


if __name__ == '__main__':
    sys.exit(waypoint_main())
