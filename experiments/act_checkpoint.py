"""Load the bundled ACT model using its saved training configuration."""

import os
import pickle
from pathlib import Path
import sys
from unittest.mock import patch


def load_act_checkpoint(checkpoint_dir, model_name, task_name):
    checkpoint_dir = Path(checkpoint_dir).expanduser().resolve()
    for name in (model_name, 'config.pkl', 'dataset_stats.pkl'):
        if not (checkpoint_dir / name).is_file():
            raise ValueError('Missing checkpoint file: {}'.format(checkpoint_dir / name))
    with (checkpoint_dir / 'config.pkl').open('rb') as stream:
        config = pickle.load(stream)
    if config['task_name'] != task_name:
        raise ValueError('Checkpoint task {!r} does not match requested task {!r}'.format(
            config['task_name'], task_name))

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ModelTrain'))
    from ModelTrain.module import model_module

    # The bytecode-only constructor calls the training CLI to build defaults.
    # Supply the saved configuration instead, including architecture and horizon.
    # Its loader also concatenates the ModelTrain directory with ckpt_dir[1:].
    vendor_root = Path(model_module.__file__).resolve().parent.parent
    vendor_path = './' + os.path.relpath(checkpoint_dir, vendor_root)
    with patch.object(model_module, 'set_config', return_value=config):
        model = model_module.Imitate_Model(ckpt_dir=vendor_path, ckpt_name=model_name)
    model.loadModel()
    return model
