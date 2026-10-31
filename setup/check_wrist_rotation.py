"""Turn a held carton through four wrist positions at the scan pose and record scans."""
import sys

from parcel_sorting.runtime.hardware_checks import wrist_main


if __name__ == '__main__':
    sys.exit(wrist_main())
