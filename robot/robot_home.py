"""Inspect follower status; recover or home only when explicitly requested."""
import sys

from parcel_sorting.hardware.robot_home import main


if __name__ == '__main__':
    sys.exit(main())
