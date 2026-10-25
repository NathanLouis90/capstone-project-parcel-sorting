"""Algorithm-specific defaults, preference migration, and generated training settings."""

from dataclasses import asdict, replace
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from scripts import train_models
from scripts.train_models import (
    edit_hyperparameters, hyperparameter_fields, load_hyperparameter_defaults,
    run_menu, save_hyperparameter_defaults,
)
from scripts.training_workflow import TrainingSettings, create_training_jobs


def prepared_dataset(path):
    path.mkdir()
    split = {'recipe': {'medium': 'poly_mailer'}, 'train': ['demo_0'], 'valid': ['demo_1'],
             'sources': [{'id': 'bottom/1'}, {'id': 'top/2'}]}
    (path / 'split.json').write_text(json.dumps(split))
    with h5py.File(str(path / 'dataset.hdf5'), 'w') as target:
        data = target.create_group('data')
        data.attrs['split_json'] = json.dumps(split)
        data.attrs['recipe'] = 'poly_mailer'
        for key in ('train', 'valid'):
            target.create_dataset('mask/' + key, data=np.asarray(split[key], dtype='S'))
    return path


def test_existing_flat_preferences_seed_both_algorithms(tmp_path):
    path = tmp_path / 'preferences.json'
    old = asdict(TrainingSettings(epochs=120, batch_size=4, prediction_length=24))
    for key in ('dp_unet_dimensions', 'dp_training_diffusion_steps', 'dp_inference_diffusion_steps'):
        old.pop(key)
    path.write_text(json.dumps(old))
    defaults = load_hyperparameter_defaults(path)
    assert all(profile.epochs == 120 and profile.prediction_length == 24 for profile in defaults.values())
    assert defaults['act'] is not defaults['diffusion_policy']
    defaults['act'] = replace(defaults['act'], epochs=50, prediction_length=8)
    save_hyperparameter_defaults(path, defaults)
    loaded = load_hyperparameter_defaults(path)
    assert loaded['act'].epochs == 50 and loaded['act'].prediction_length == 8
    assert loaded['diffusion_policy'].epochs == 120 and loaded['diffusion_policy'].prediction_length == 24


def test_editor_changes_only_selected_algorithm_and_preserves_shared_split(tmp_path, capsys):
    path = tmp_path / 'preferences.json'
    defaults = load_hyperparameter_defaults(path)
    # ACT: epochs, batch size, rate, chunk length, validation share, split seed.
    answers = iter(['1', '1', '50', '2', '4', '3', '0.0002', '6', '8', '7', '25', '8', '42', ''])
    edit_hyperparameters(defaults, path, lambda prompt: next(answers))
    loaded = load_hyperparameter_defaults(path)
    act, dp = loaded['act'], loaded['diffusion_policy']
    assert (act.epochs, act.batch_size, act.act_learning_rate, act.prediction_length) == (50, 4, 0.0002, 8)
    assert (dp.epochs, dp.batch_size, dp.dp_learning_rate, dp.prediction_length) == (1000, 8, 0.0001, 16)
    assert act.validation_percent == dp.validation_percent == 25
    assert act.seed == dp.seed == 42
    output = capsys.readouterr().out
    assert 'ACT hyperparameter defaults' in output and 'DP executed action horizon' not in output


def test_dp_editor_shows_its_advanced_fields_and_saves_on_back(tmp_path, capsys):
    root = tmp_path / 'datasets'
    answers = iter(['5', '2', '6', '32', 'a', '3', '32,64,128', 'b', 'q'])
    assert run_menu(root, tmp_path / 'models', input_fn=lambda prompt: next(answers)) == 0
    defaults = load_hyperparameter_defaults(root / '.training_cache/preferences.json')
    assert defaults['diffusion_policy'].prediction_length == 32
    assert defaults['diffusion_policy'].dp_unet_dimensions == [32, 64, 128]
    assert defaults['act'].prediction_length == 16
    output = capsys.readouterr().out
    assert '5. Edit hyperparameter defaults' in output
    assert 'DP U-Net dimensions' in output and 'ACT KL weight' not in output


def test_algorithm_fields_and_validation_are_independent():
    act_fields = hyperparameter_fields('act') + hyperparameter_fields('act', advanced=True)
    dp_fields = hyperparameter_fields('diffusion_policy') + hyperparameter_fields('diffusion_policy', advanced=True)
    assert not any(key.startswith('dp_') for key, _, _ in act_fields)
    assert not any(key.startswith('act_') for key, _, _ in dp_fields)
    TrainingSettings(prediction_length=1).validate('act')
    with pytest.raises(ValueError, match='fit prediction length'):
        TrainingSettings(prediction_length=1).validate('diffusion_policy')
    with pytest.raises(ValueError, match='multiple'):
        TrainingSettings(prediction_length=17).validate('diffusion_policy')
    with pytest.raises(ValueError, match='cannot exceed'):
        TrainingSettings(dp_training_diffusion_steps=10).validate('diffusion_policy')


def test_generated_jobs_use_each_algorithms_saved_defaults(tmp_path):
    prepared = prepared_dataset(tmp_path / 'prepared')
    act = TrainingSettings(device='cpu', epochs=20, batch_size=4, prediction_length=8, act_learning_rate=0.0002)
    dp = TrainingSettings(device='cpu', epochs=60, batch_size=2, prediction_length=32,
                          dp_learning_rate=0.0003, dp_unet_dimensions=[32, 64, 128],
                          dp_training_diffusion_steps=40, dp_inference_diffusion_steps=10)
    jobs = []
    for algorithm, settings, name in [('act', act, 'named_act'), ('diffusion_policy', dp, 'named_dp')]:
        jobs.extend(create_training_jobs(prepared, settings, {algorithm: name}, tmp_path / 'models'))
    act_config, dp_config = [json.loads(Path(job['config']).read_text()) for job in jobs]
    assert act_config['train']['num_epochs'] == 20 and act_config['train']['batch_size'] == 4
    assert act_config['train']['seq_length'] == 8
    assert dp_config['train']['num_epochs'] == 60 and dp_config['train']['batch_size'] == 2
    assert dp_config['train']['seq_length'] == 31
    assert dp_config['algo']['horizon']['prediction_horizon'] == 32
    assert dp_config['algo']['unet']['down_dims'] == [32, 64, 128]
    assert dp_config['algo']['ddpm']['num_train_timesteps'] == 40
    assert dp_config['algo']['ddpm']['num_inference_timesteps'] == 10
    assert act_config['algo']['optim_params']['policy']['learning_rate']['initial'] == 0.0002
    assert dp_config['algo']['optim_params']['policy']['learning_rate']['initial'] == 0.0003
    assert jobs[0]['dataset'] == jobs[1]['dataset']
    for job in jobs:
        summary = (tmp_path / 'models' / job['name'] / 'training_summary.txt').read_text()
        other_label = 'DP prediction horizon' if job['algorithm'] == 'act' else 'ACT chunk length'
        assert other_label not in summary


def test_paired_training_uses_independent_defaults_with_one_split(tmp_path, monkeypatch):
    prepared = prepared_dataset(tmp_path / 'prepared')
    defaults = load_hyperparameter_defaults(tmp_path / 'preferences.json')
    defaults['act'] = replace(defaults['act'], device='cpu', epochs=15, prediction_length=8)
    defaults['diffusion_policy'] = replace(defaults['diffusion_policy'], device='cpu', epochs=30, prediction_length=32)
    monkeypatch.setattr(train_models, 'select_datasets', lambda *args: [{'path': tmp_path / 'data', 'name': 'data'}])
    monkeypatch.setattr(train_models, 'collect_accepted', lambda projects: [
        {'medium': 'poly_mailer', 'id': 'data/1', 'cycle': '1'},
        {'medium': 'poly_mailer', 'id': 'data/2', 'cycle': '2'}])
    preparations = []
    monkeypatch.setattr(train_models, 'prepare_dataset', lambda *args, **kwargs: preparations.append(kwargs['algorithm']) or prepared)
    monkeypatch.setattr(train_models, 'check_training_device', lambda settings: None)
    trained = []
    monkeypatch.setattr(train_models, 'run_training_job', lambda job: trained.append(job))
    answers = iter(['3', 'pair_act', 'pair_dp', 'TRAIN'])
    train_models.train_action(tmp_path, tmp_path / 'models', defaults, tmp_path / 'preferences.json',
                             lambda prompt: next(answers))
    assert preparations == ['act']
    assert [(job['algorithm'], job['settings']['epochs'], job['settings']['prediction_length']) for job in trained] == [
        ('act', 15, 8), ('diffusion_policy', 30, 32)]
    assert trained[0]['dataset'] == trained[1]['dataset']
