import json
from pathlib import Path
from types import SimpleNamespace
import sys

import cv2
import h5py
import numpy as np
import pytest

from scripts.convert_to_robomimic import convert
from scripts.scripts_config import ROBOMIMIC

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'robomimic-r2d2'))


def vendor_file(project, index, bin_index, status='accepted', stage='B', cycle=None):
    directory = project / 'train_data'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'episode_init_{}.hdf5'.format(index)
    with h5py.File(str(path), 'w') as source:
        source.attrs['policy_stage'] = stage
        source.attrs['medium'] = 'poly_mailer'
        source.attrs['bin_index'] = bin_index
        source.attrs['cycle_id'] = cycle or '{}-{}'.format(project.name, index)
        source.attrs['episode_metadata_json'] = json.dumps({'review_status': status})
        source.attrs['compress'] = True
        source.create_dataset('observations/qpos', data=np.zeros((3, 14)))
        source.create_dataset('action', data=np.ones((3, 14)))
        source.create_dataset('observations/destination', data=np.tile(np.eye(2)[bin_index], (3, 1)))
        image = np.full((8, 8, 3), [10, 40, 200], dtype=np.uint8)
        _, encoded = cv2.imencode('.jpg', image)
        for camera in ROBOMIMIC['cameras']:
            source.create_dataset('observations/images/' + camera, data=np.tile(encoded.ravel(), (3, 1)))
    return path


def projects(tmp_path):
    values = [tmp_path / 'bin0', tmp_path / 'bin1']
    for bin_index, project in enumerate(values):
        for index in range(2):
            vendor_file(project, index, bin_index)
    return values


def test_conditioned_conversion_rgb_provenance_and_split(tmp_path):
    sources = projects(tmp_path)
    output, split_file = tmp_path / 'B.hdf5', tmp_path / 'split.json'
    with pytest.warns(UserWarning, match='fewer than three'):
        split = convert(sources, 'policy_B_conditioned', output, split_file)
    assert set(split['train']).isdisjoint(split['valid'])
    assert len(split['train']) == len(split['valid']) == 2
    with h5py.File(str(output), 'r') as source:
        assert source['data'].attrs['total'] == 12
        for name, demo in source['data'].items():
            bin_index = demo.attrs['bin_index']
            assert demo.attrs['policy_stage'] == 'B'
            assert demo.attrs['medium'] == 'poly_mailer'
            assert np.all(demo['obs/destination'][:] == np.eye(2)[bin_index])
            frame = demo['obs/top'][0]
            assert frame.dtype == np.uint8
            assert frame.shape == (128, 128, 3)
            assert frame[0, 0, 0] > frame[0, 0, 2]  # RGB, not BGR
        assert json.loads(source['data'].attrs['split_json']) == json.loads(split_file.read_text())
    with pytest.raises(FileExistsError):
        convert(sources, 'policy_B_conditioned', output, split_file)


def test_conditioned_dataset_requires_both_bins(tmp_path):
    project = tmp_path / 'bin0'
    for index in range(2):
        vendor_file(project, index, 0)
    with pytest.raises(ValueError, match='both bins'):
        convert([project], 'policy_B_conditioned', tmp_path / 'B.h5', tmp_path / 'split.json')


def test_destination_is_constant_and_matches_bin(tmp_path):
    sources = projects(tmp_path)
    with h5py.File(str(sources[0] / 'train_data/episode_init_0.hdf5'), 'r+') as source:
        source['observations/destination'][1] = [0, 1]
    with pytest.raises(ValueError, match='remain constant'):
        convert(sources, 'policy_B_conditioned', tmp_path / 'B.h5', tmp_path / 'split.json')


def test_unreviewed_not_selected(tmp_path):
    project = tmp_path / 'A'
    vendor_file(project, 0, 0, status='unreviewed', stage='A')
    with pytest.raises(ValueError, match='No accepted'):
        convert([project], 'policy_A_unified', tmp_path / 'A.h5', tmp_path / 'split.json')


def test_split_refuses_changed_sources(tmp_path):
    sources = projects(tmp_path)
    split_file = tmp_path / 'split.json'
    with pytest.warns(UserWarning):
        convert(sources, 'policy_B_conditioned', tmp_path / 'B.h5', split_file)
    with h5py.File(str(sources[0] / 'train_data/episode_init_0.hdf5'), 'r+') as source:
        source['action'][0, 0] = 2
    with pytest.warns(UserWarning), pytest.raises(ValueError, match='sources changed'):
        convert(sources, 'policy_B_conditioned', tmp_path / 'B2.h5', split_file)


def test_cycle_not_split_between_filters(tmp_path):
    sources = projects(tmp_path)
    vendor_file(sources[0], 2, 0, cycle='bin0-0')
    with pytest.warns(UserWarning):
        split = convert(sources, 'policy_B_conditioned', tmp_path / 'B.h5', tmp_path / 'split.json')
    assert any({'demo_0', 'demo_2'}.issubset(set(split[key])) for key in ('train', 'valid'))


def test_matched_configs_use_frozen_split(tmp_path):
    from robomimic.scripts.config_gen.parcel_sorting_gen import generate_configs
    sources = projects(tmp_path)
    output, split_file = tmp_path / 'B.h5', tmp_path / 'split.json'
    with pytest.warns(UserWarning):
        convert(sources, 'policy_B_conditioned', output, split_file)
    paths = generate_configs(output, split_file, tmp_path / 'configs', smoke=True, cpu=True)
    configs = [json.loads(path.read_text()) for path in paths]
    for config in configs:
        assert config['train']['hdf5_filter_key'] == 'train'
        assert config['train']['hdf5_validation_filter_key'] == 'valid'
        assert config['train']['hdf5_normalize_obs']
        assert config['train']['action_config']['actions']['normalization'] == 'min_max'
        assert config['observation']['modalities']['obs']['low_dim'] == ['qpos', 'destination']
        assert not config['experiment']['rollout']['enabled']
    assert configs[0]['train']['data'] == configs[1]['train']['data']


def test_observation_normalization_preserves_image_and_mask():
    from robomimic.utils.obs_utils import normalize_obs_dict
    image = np.ones((3, 8, 8))
    observations = dict(qpos=np.array([2., 4.]), top=image, pad_mask=np.ones(1))
    result = normalize_obs_dict(observations, {'qpos': {'mean': np.array([[1., 2.]]), 'std': np.array([[1., 2.]])}})
    np.testing.assert_allclose(result['qpos'], [1, 1])
    assert result['top'] is image
    assert result['pad_mask'] is observations['pad_mask']


def test_swap_matches_noise_and_resets_history(tmp_path):
    from scripts.check_destination_swap import compare_episode

    class FakePolicy:
        def __init__(self):
            self.policy = SimpleNamespace(obs_key_shapes={'qpos': (14,), 'destination': (2,)},
                                          global_config=SimpleNamespace(train=SimpleNamespace(frame_stack=2)))
            self.resets = 0

        def start_episode(self):
            self.resets += 1

        def __call__(self, obs):
            assert obs['qpos'].shape == (2, 14)
            assert np.all(obs['destination'][0] == obs['destination'][1])
            return np.random.normal(size=14) + obs['destination'][-1, 0]

    sources = projects(tmp_path)
    with pytest.warns(UserWarning):
        convert(sources, 'policy_B_conditioned', tmp_path / 'B.h5', tmp_path / 'split.json')
    policy = FakePolicy()
    with h5py.File(str(tmp_path / 'B.h5'), 'r') as source:
        result = compare_episode(policy, source['data/demo_0'], 5, 3)
    assert policy.resets == 2
    assert result['swap_right_joint_rms_rad'] == pytest.approx(1)
