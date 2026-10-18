"""Generate matched ACT and Diffusion Policy configs from a frozen parcel split."""
import argparse
from pathlib import Path
import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'robomimic-r2d2'))
from robomimic.scripts.config_gen.parcel_sorting_gen import generate_configs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, type=Path)
    parser.add_argument('--split-file', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--smoke', action='store_true', help='Small models, two steps, one epoch; not final evaluation')
    parser.add_argument('--cpu', action='store_true')
    args = parser.parse_args(argv)
    for path in generate_configs(args.dataset, args.split_file, args.output_dir, args.smoke, args.cpu):
        print(path)


if __name__ == '__main__':
    main()
