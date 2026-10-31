"""ACT feedback frequency, temporal blending, episode boundaries, and checkpoint defaults."""

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path

import pytest
import torch

from parcel_sorting.policies.robomimic_policy import add_act_rollout_arguments, apply_act_rollout_overrides
from robomimic.algo.act import ACT
from robomimic.algo.act_rollout import ACTActionSelector
from parcel_sorting.training.menu import edit_hyperparameters, load_hyperparameter_defaults
from parcel_sorting.training.report import settings_rows
from parcel_sorting.training.workflow import TrainingSettings, create_training_jobs


class Predictor:
    def __init__(self, size):
        self.size, self.calls = size, 0

    def __call__(self):
        chunk = torch.arange(self.size, dtype=torch.float32)[None, :, None] + self.calls * 100
        self.calls += 1
        return chunk


@pytest.mark.parametrize('interval,expected', [
    (0, [0, 1, 2, 3, 100, 101]),
    (2, [0, 1, 100, 101, 200, 201]),
    (1, [0, 100, 200, 300, 400, 500]),
])
def test_replan_interval_uses_correct_offset_in_latest_chunk(interval, expected):
    predict = Predictor(4)
    selector = ACTActionSelector(4, query_frequency=interval)
    actual = [selector.select(predict).item() for _ in expected]
    assert actual == expected
    assert predict.calls == (2 if interval == 0 else 3 if interval == 2 else 6)


@pytest.mark.parametrize('coefficient,expected', [
    (0, 5), (1, 10 / (1 + math.e)), (-1, 10 * math.e / (1 + math.e)),
    (1e308, 0), (-1e308, 10),
])
def test_ensemble_weight_order_includes_valid_zero_predictions(coefficient, expected):
    selector = ACTActionSelector(3, temporal_agg=True, coefficient=coefficient)
    chunks = iter([torch.zeros(1, 3, 2), torch.full((1, 3, 2), 10.)])
    assert torch.equal(selector.select(lambda: next(chunks)), torch.zeros(1, 2))
    result = selector.select(lambda: next(chunks))
    assert torch.isfinite(result).all()
    assert result.tolist()[0] == pytest.approx([expected, expected])


def test_ensemble_expires_predictions_keeps_memory_bounded_and_resets():
    selector = ACTActionSelector(3, temporal_agg=True, coefficient=0)
    predict = Predictor(3)
    results = [selector.select(predict).item() for _ in range(4)]
    assert results == pytest.approx([0, 50.5, 101, 201])
    for _ in range(100):
        selector.select(predict)
        assert len(selector.chunks) <= 3
    selector.reset()
    assert not selector.chunks and selector.latest_chunk is None
    result = selector.select(lambda: torch.full((1, 3, 1), -5.))
    assert result.item() == -5 and selector.timestep == 1


def test_nonfinite_predictions_and_changed_batch_shape_are_refused():
    selector = ACTActionSelector(3, temporal_agg=True)
    with pytest.raises(ValueError, match='finite'):
        selector.select(lambda: torch.full((1, 3, 1), float('nan')))
    selector.select(lambda: torch.zeros(1, 3, 1))
    with pytest.raises(ValueError, match='dimensions changed'):
        selector.select(lambda: torch.zeros(2, 3, 1))


def test_native_act_observes_new_state_each_step_and_clears_warmup_history():
    class Network(torch.nn.Module):
        def forward(self, joints, images, env_state):
            return joints[:, :1, None].expand(-1, 1, 2).transpose(1, 2), None, (None, None)

    policy = ACT.__new__(ACT)
    policy.camera_keys, policy.proprio_keys = ['top'], ['qpos']
    policy.normalize = lambda image: image
    policy.nets = torch.nn.ModuleDict({'policy': Network()})
    policy.nets.eval()
    policy.device = torch.device('cpu')
    policy.action_selector = ACTActionSelector(2, temporal_agg=True, coefficient=0)
    policy.reset()

    def observation(value):
        return {'qpos': torch.tensor([[value]], dtype=torch.float32), 'top': torch.zeros(1, 3, 2, 2)}

    assert policy.get_action(observation(0)).item() == 0
    assert policy.get_action(observation(10)).item() == 5
    policy.reset()
    assert policy.a_hat_store is None
    assert policy.get_action(observation(20)).item() == 20


def test_old_checkpoint_defaults_and_in_memory_rollout_overrides():
    config = {'train': {'seq_length': 16}, 'algo': {'act': {}}}
    effective = apply_act_rollout_overrides(config, 'act')
    assert effective['temporal_ensemble'] is False and effective['query_frequency'] == 16
    effective = apply_act_rollout_overrides(config, 'act', temporal=True, coefficient=-0.01)
    assert effective['temporal_ensemble'] is True and effective['query_frequency'] == 1
    assert config['algo']['act']['temporal_ensemble_coeff'] == -0.01
    effective = apply_act_rollout_overrides(config, 'act', temporal=False, query_frequency=4)
    assert effective['query_frequency'] == 4
    with pytest.raises(ValueError, match='ACT checkpoint'):
        apply_act_rollout_overrides({'algo': {}}, 'diffusion_policy', temporal=True)


def test_command_line_defaults_do_not_override_saved_settings():
    parser = argparse.ArgumentParser()
    add_act_rollout_arguments(parser)
    assert parser.parse_args([]).act_temporal_ensemble is None
    assert parser.parse_args(['--act-temporal-ensemble']).act_temporal_ensemble is True
    assert parser.parse_args(['--no-act-temporal-ensemble']).act_temporal_ensemble is False


def test_temporal_menu_settings_persist_into_checkpoint_config_and_report(tmp_path):
    import h5py
    import numpy as np
    preferences = tmp_path / 'preferences.json'
    defaults = load_hyperparameter_defaults(preferences)
    # Existing advanced ACT fields stay in place; new rollout settings follow them.
    answers = iter(['1', 'a', '9', 'yes', '10', '-0.01', '11', '4', '', ''])
    edit_hyperparameters(defaults, preferences, lambda prompt: next(answers))
    loaded = load_hyperparameter_defaults(preferences)
    assert loaded['act'].act_temporal_ensemble is True
    assert loaded['diffusion_policy'].act_temporal_ensemble is False
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    split = dict(recipe={'medium': 'poly_mailer'}, sources=[{'id': 'mailers/1'}], train=['demo_0'], valid=['demo_1'])
    (prepared / 'split.json').write_text(json.dumps(split))
    with h5py.File(str(prepared / 'dataset.hdf5'), 'w') as target:
        data = target.create_group('data')
        data.attrs.update(split_json=json.dumps(split), recipe='poly_mailer')
        for key in ('train', 'valid'):
            target.create_dataset('mask/' + key, data=np.asarray(split[key], dtype='S'))
    job = create_training_jobs(prepared, loaded['act'], {'act': 'ensemble_act'}, tmp_path / 'models')[0]
    config = json.loads(Path(job['config']).read_text())
    assert config['algo']['act']['temporal_agg'] is True
    assert config['algo']['act']['query_frequency'] == 4
    rows = dict(settings_rows(config, {}))
    assert rows['ACT temporal ensembling (rollout default)'] is True
    assert rows['Effective ACT replan interval (control steps)'] == 1
    with pytest.raises(ValueError, match='replan interval'):
        replace(TrainingSettings(), act_query_frequency=17).validate('act')


def test_joint_input_noise_applies_only_in_training_mode():
    class Network(torch.nn.Module):
        def forward(self, joints, images, env_state, actions=None, is_pad=None):
            self.seen = joints.clone()
            return actions, None, (torch.zeros(1, 1), torch.zeros(1, 1))

    policy = ACT.__new__(ACT)
    policy.camera_keys, policy.proprio_keys = ['top'], ['qpos']
    policy.normalize = lambda image: image
    policy.nets = torch.nn.ModuleDict({'policy': Network()})
    policy.algo_config = type('Config', (), {'act': {'qpos_noise_std': 0.5}})()
    policy.kl_divergence = lambda mu, logvar: (torch.zeros(1), None, None)
    batch = {'obs': {'qpos': torch.zeros(64, 14), 'top': torch.zeros(64, 3, 2, 2),
                     'pad_mask': torch.ones(64, 4, 1)}, 'actions': torch.zeros(64, 4, 2)}
    policy.nets.train()
    policy._forward_training(batch)
    assert 0.4 < policy.nets['policy'].seen.std().item() < 0.6
    policy.nets.eval()
    policy._forward_training(batch)
    assert policy.nets['policy'].seen.abs().max().item() == 0


def test_joint_input_noise_reaches_new_act_configs_and_rejects_negative_values(tmp_path):
    import h5py
    import numpy as np
    assert TrainingSettings().act_qpos_noise_std == 0.5
    with pytest.raises(ValueError, match='joint-input noise'):
        replace(TrainingSettings(), act_qpos_noise_std=-0.1).validate('act')
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    split = dict(recipe={'medium': 'poly_mailer'}, sources=[{'id': 'mailers/1'}], train=['demo_0'], valid=['demo_1'])
    (prepared / 'split.json').write_text(json.dumps(split))
    with h5py.File(str(prepared / 'dataset.hdf5'), 'w') as target:
        data = target.create_group('data')
        data.attrs.update(split_json=json.dumps(split), recipe='poly_mailer')
        for key in ('train', 'valid'):
            target.create_dataset('mask/' + key, data=np.asarray(split[key], dtype='S'))
    job = create_training_jobs(prepared, TrainingSettings(), {'act': 'noisy_act'}, tmp_path / 'models')[0]
    config = json.loads(Path(job['config']).read_text())
    assert config['algo']['act']['qpos_noise_std'] == 0.5
    assert dict(settings_rows(config, {}))['Joint-input noise std (training only)'] == 0.5
    legacy = json.loads(Path(job['config']).read_text())
    del legacy['algo']['act']['qpos_noise_std']
    assert dict(settings_rows(legacy, {}))['Joint-input noise std (training only)'] == 0.0
