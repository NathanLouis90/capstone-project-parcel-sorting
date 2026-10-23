"""Run the existing pick, scan, bin placement and outcome logger."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from experiments.run_cycle import main


if __name__ == '__main__':
    sys.exit(main())
