import os
from pathlib import Path
import pickle
import sys
import types

import pytest

from experiments.act_checkpoint import load_act_checkpoint


@pytest.fixture
def checkpoint(tmp_path):
    directory = tmp_path / 'saved model'
    directory.mkdir()
    config = {'task_name': 'parcel', 'episode_len': 400,
              'policy_config': {'num_queries': 23}}
    with (directory / 'config.pkl').open('wb') as stream:
        pickle.dump(config, stream)
    (directory / 'policy_best.ckpt').touch()
    (directory / 'dataset_stats.pkl').touch()
    return directory, config


def test_checkpoint_config_and_paths_ignore_inference_cli(checkpoint, monkeypatch):
    directory, config = checkpoint
    vendor = types.ModuleType('ModelTrain.module.model_module')
    vendor.__file__ = str(Path(__file__).resolve().parents[1]
                          / 'ModelTrain/module/model_module.pyc')

    def training_defaults():
        pytest.fail('Inference must not parse the training CLI')

    vendor.set_config = training_defaults

    class Model:
        def __init__(self, ckpt_dir, ckpt_name):
            self.config = vendor.set_config()
            self.ckpt_dir = ckpt_dir
            self.ckpt_name = ckpt_name

        def loadModel(self):
            # Reproduce the two path expressions in the bytecode-only loader.
            root = os.path.dirname(os.path.dirname(os.path.abspath(vendor.__file__)))
            weights = root + os.path.join(self.ckpt_dir, self.ckpt_name)[1:]
            stats = os.path.join(root + self.ckpt_dir[1:], 'dataset_stats.pkl')
            assert Path(weights).resolve() == directory / 'policy_best.ckpt'
            assert Path(stats).resolve() == directory / 'dataset_stats.pkl'
            self.loaded = True

    vendor.Imitate_Model = Model
    monkeypatch.setitem(sys.modules, vendor.__name__, vendor)
    monkeypatch.setattr(sys, 'argv', ['run_cycle.py', '--medium', 'poly_mailer', '--live',
                                    '--backend', 'vendor', '--checkpoint', str(directory)])
    argv = sys.argv[:]
    path = sys.path[:]
    try:
        model = load_act_checkpoint(directory, 'policy_best.ckpt', 'parcel')
    finally:
        sys.path[:] = path
    assert model.config == config
    assert model.loaded
    assert vendor.set_config is training_defaults
    assert sys.argv == argv


def test_mismatched_checkpoint_rejected_before_vendor_import(checkpoint):
    directory, _ = checkpoint
    with pytest.raises(ValueError, match='does not match requested task'):
        load_act_checkpoint(directory, 'policy_best.ckpt', 'another_task')


@pytest.mark.parametrize('missing', ['config.pkl', 'dataset_stats.pkl', 'policy_best.ckpt'])
def test_missing_checkpoint_files_rejected(checkpoint, missing):
    directory, _ = checkpoint
    (directory / missing).unlink()
    with pytest.raises(ValueError, match='Missing checkpoint file'):
        load_act_checkpoint(directory, 'policy_best.ckpt', 'parcel')


@pytest.mark.parametrize('kind', ['ACT', 'CNNMLP'])
def test_model_builder_uses_overrides_without_parsing_cli(monkeypatch, kind):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'ModelTrain'))
    from ModelTrain.detr import main

    observed = []

    class Model:
        def cuda(self):
            return self

        def named_parameters(self):
            return []

    def build(args):
        observed.append(args)
        return Model()

    monkeypatch.setattr(main, 'build_{}_model'.format(kind), build)
    monkeypatch.setattr(main.torch.optim, 'AdamW', lambda *args, **kwargs: 'optimizer')
    monkeypatch.setattr(sys, 'argv', ['run_cycle.py', '--medium', 'poly_mailer', '--dry-run'])
    builder = getattr(main, 'build_{}_model_and_optimizer'.format(kind))
    _, optimizer = builder({'num_queries': 23, 'hidden_dim': 512, 'lr': 2e-5})
    assert optimizer == 'optimizer'
    assert observed[0].num_queries == 23
    assert observed[0].hidden_dim == 512
    assert observed[0].lr == 2e-5
    assert observed[0].weight_decay == 1e-4
