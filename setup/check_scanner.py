"""List barcode scanner devices or print scans from the configured scanner."""
import sys

from parcel_sorting.scanning.scanner_reader import main


if __name__ == '__main__':
    sys.exit(main())
