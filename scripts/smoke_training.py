"""Train and reload tiny synthetic ACT/DP checkpoints without opening hardware."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'robomimic-r2d2'))


def run(output):
    import cv2
    import h5py
    import numpy as np
    import torch
    from experiments.handoff import home_action
    from experiments.robomimic_runner import RobomimicPolicy
    from scripts.convert_to_robomimic import convert
    from scripts.scripts_config import ROBOMIMIC
    from robomimic.scripts.config_gen.parcel_sorting_gen import generate_configs

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / 'synthetic_poly_mailer' / 'train_data'
    project.mkdir(parents=True)
    for index in range(4):
        path = project / ('episode_init_{}.hdf5'.format(index))
        with h5py.File(str(path), 'x') as source:
            metadata = dict(schema_version=3, medium='poly_mailer',
                            label_face='top' if index % 2 else 'bottom',
                            cycle_id=str(index), episode_id=str(index), review_status='accepted')
            source.attrs['episode_metadata_json'] = json.dumps(metadata)
            for key in ('medium', 'label_face', 'cycle_id'):
                source.attrs[key] = metadata[key]
            source.attrs['compress'] = True
            source['observations/qpos'] = np.tile(home_action(), (20, 1))
            source['action'] = np.tile(home_action(), (20, 1))
            _, image = cv2.imencode('.jpg', np.full((32, 32, 3), [10, 40, 200], dtype=np.uint8))
            for camera in ROBOMIMIC['cameras']:
                source['observations/images/' + camera] = np.tile(image.ravel(), (20, 1))
    dataset, split = output / 'synthetic.hdf5', output / 'split.json'
    convert([project.parent], 'poly_mailer', dataset, split)
    configs = generate_configs(dataset, split, output / 'configs', smoke=True, cpu=True)
    environment = dict(os.environ, PYTHONPATH=str(ROOT) + ':' + str(ROOT / 'robomimic-r2d2'),
                       OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    torch.set_num_threads(1)
    results = []
    for config in configs:
        log = output / (config.stem + '.log')
        with log.open('w') as stream:
            subprocess.run([sys.executable, str(ROOT / 'robomimic-r2d2/robomimic/scripts/train.py'),
                            '--config', str(config)], env=environment, cwd=str(ROOT),
                           stdout=stream, stderr=subprocess.STDOUT, check=True)
        checkpoints = sorted((output / 'configs/runs' / config.stem).glob('*/models/*.pth'))
        if not checkpoints:
            raise ValueError('Training did not save a checkpoint; inspect ' + str(log))
        policy = RobomimicPolicy('poly_mailer', checkpoints[-1], device=torch.device('cpu'))
        observation = dict(qpos=home_action(), images={
            camera: np.zeros((128, 128, 3), dtype=np.uint8) for camera in ROBOMIMIC['cameras']})
        for _ in range(3):
            action = policy.step(observation)
            if action.shape != (14,) or not np.isfinite(action).all():
                raise ValueError('Checkpoint produced invalid action shape/values')
        results.append(dict(policy_type=policy.policy_type, checkpoint=str(checkpoints[-1]), steps=3))
        print(policy.policy_type + ': trained, loaded and stepped without hardware')
    (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New output directory; never overwrite a previous check')
    args = parser.parse_args(argv)
    run(args.output)


if __name__ == '__main__':
    main()
