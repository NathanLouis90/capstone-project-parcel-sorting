"""Load an ACT/DP checkpoint and print predictions on synthetic inputs; sends no robot commands."""
import sys

from parcel_sorting.policies.robomimic_policy import main


if __name__ == '__main__':
    sys.exit(main())
