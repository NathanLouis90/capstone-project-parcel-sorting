"""Compare recorded joint gaps with rollout bounds without opening robot devices."""
import sys

from parcel_sorting.training.rollout_compatibility import main


if __name__ == '__main__':
    sys.exit(main())
