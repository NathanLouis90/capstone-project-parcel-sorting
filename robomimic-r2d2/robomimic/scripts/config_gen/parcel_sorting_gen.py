"""Parcel recipes using the same ConfigGenerator as ACT / diffusion config_gen."""
import json
from pathlib import Path

from robomimic.config import config_factory
from robomimic.utils.hyperparam_utils import ConfigGenerator
from scripts.scripts_config import ROBOMIMIC


def generate_configs(dataset, split_file, output_dir, smoke=False, cpu=False):
    import h5py
    dataset, split_file, output_dir = Path(dataset).resolve(), Path(split_file).resolve(), Path(output_dir)
    split = json.loads(split_file.read_text())
    with h5py.File(str(dataset), 'r') as source:
        if json.loads(source['data'].attrs['split_json']) != split:
            raise ValueError('Split file differs from dataset split')
        for key in ('train', 'valid'):
            names = [name.decode() for name in source['mask/' + key][:]]
            if names != split[key]:
                raise ValueError('Dataset filter differs from explicit split file')
        recipe_name = source['data'].attrs['recipe']
    if recipe_name not in ROBOMIMIC['recipes']:
        raise ValueError('Unknown medium recipe')
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for algorithm in ('act', 'diffusion_policy'):
        config = json.loads(config_factory(algorithm).dump())
        name = recipe_name + '_' + algorithm + ('_smoke' if smoke else '')
        config['experiment']['name'] = name
        base = output_dir / ('base_' + algorithm + '.json')
        base.write_text(json.dumps(config, indent=2) + '\n')
        generator = ConfigGenerator(str(base), script_file=str(output_dir / (algorithm + '_train.sh')),
                                    generated_config_dir=str(output_dir))
        parameters = {
            'experiment.validate': True,
            'experiment.rollout.enabled': False,
            'experiment.render_video': False,
            'experiment.logging.log_wandb': False,
            'experiment.logging.log_tb': False,
            'experiment.logging.terminal_output_to_txt': False,
            'experiment.epoch_every_n_steps': ROBOMIMIC['smoke_steps' if smoke else 'steps_per_epoch'],
            'experiment.validation_epoch_every_n_steps': ROBOMIMIC['smoke_steps' if smoke else 'validation_steps'],
            'experiment.save.every_n_epochs': ROBOMIMIC['smoke_epochs' if smoke else 'save_every_epochs'],
            'experiment.save.on_best_validation': True,
            'experiment.save.on_best_rollout_success_rate': False,
            'experiment.save.on_best_rollout_return': False,
            'train.data': [{'path': str(dataset)}],
            'train.output_dir': str((output_dir / 'runs').resolve()),
            'train.dataset_keys': ['actions'],
            'train.action_keys': ['actions'],
            'train.action_config': {'actions': {'normalization': 'min_max'}},
            'train.hdf5_cache_mode': 'low_dim',
            'train.hdf5_load_next_obs': False,
            'train.hdf5_normalize_obs': True,
            'train.hdf5_filter_key': 'train',
            'train.hdf5_validation_filter_key': 'valid',
            'train.num_data_workers': 0,
            'train.batch_size': ROBOMIMIC['smoke_batch_size' if smoke else 'batch_size'],
            'train.num_epochs': ROBOMIMIC['smoke_epochs' if smoke else 'epochs'],
            'train.seed': ROBOMIMIC['seed'],
            'train.cuda': not cpu,
            'train.seq_length': ROBOMIMIC['action_chunk'],
            'train.frame_stack': 1,
            'observation.modalities.obs.low_dim': ['qpos'],
            'observation.modalities.obs.rgb': ROBOMIMIC['cameras'],
            'observation.modalities.obs.depth': [],
            'observation.modalities.obs.scan': [],
            'observation.encoder.rgb.core_kwargs': {'feature_dimension': ROBOMIMIC['visual_feature_dimension'], 'backbone_kwargs': {'pretrained': False}},
            'algo.optim_params.policy.learning_rate.initial': ROBOMIMIC['learning_rate'],
        }
        if algorithm == 'act':
            parameters['algo.act.pretrained_backbone'] = not smoke
            if smoke:
                parameters.update({
                    'algo.act.hidden_dim': ROBOMIMIC['smoke_act_hidden_dim'],
                    'algo.act.dim_feedforward': ROBOMIMIC['smoke_act_feedforward_dim'],
                    'algo.act.enc_layers': ROBOMIMIC['smoke_act_layers'],
                    'algo.act.dec_layers': ROBOMIMIC['smoke_act_layers'],
                })
        else:
            parameters.update({
                'algo.horizon.observation_horizon': ROBOMIMIC['observation_horizon'],
                'algo.horizon.action_horizon': ROBOMIMIC['action_horizon'],
                'algo.horizon.prediction_horizon': ROBOMIMIC['action_chunk'],
                'train.frame_stack': ROBOMIMIC['observation_horizon'],
                'train.seq_length': ROBOMIMIC['action_chunk'] - ROBOMIMIC['observation_horizon'] + 1,
            })
            if smoke:
                parameters['algo.unet.down_dims'] = ROBOMIMIC['smoke_unet_down_dims']
                parameters['algo.ddpm.num_train_timesteps'] = ROBOMIMIC['smoke_diffusion_steps']
                parameters['algo.ddpm.num_inference_timesteps'] = ROBOMIMIC['smoke_diffusion_steps']
        for key, value in parameters.items():
            generator.add_param(key=key, name='', group=0, values=[value])
        generator.generate()
        path = output_dir / (name + '.json')
        # Record split provenance alongside config without adding unsupported trainer keys.
        path.with_suffix('.split.json').write_text(json.dumps(split, indent=2) + '\n')
        paths.append(path)
    return paths
