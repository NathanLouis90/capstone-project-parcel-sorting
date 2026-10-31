"""Readable inventory of every saved training configuration field."""

import ast


MENU_FIELDS = {
    'algo_name': 'Training prompt: ACT or DP', 'experiment.name': 'Training prompt: Model name',
    'train.output_dir': 'Derived from the chosen model name',
    'train.num_epochs': 'Common: Epochs', 'train.batch_size': 'Common: Batch size',
    'train.seed': 'Common: Random seed (shared split)',
    'train.cuda': 'Advanced: Training device',
    'experiment.epoch_every_n_steps': 'Common: Training batches per epoch',
    'experiment.validation_epoch_every_n_steps': 'Common: Validation batches per epoch',
    'experiment.save.every_n_epochs': 'Advanced: Periodic checkpoint interval',
    'algo.optim_params.policy.learning_rate.initial': 'Common: Learning rate',
    'algo.act.kl_weight': 'ACT advanced: KL weight',
    'algo.act.qpos_noise_std': 'ACT advanced: Joint-input noise (training)',
    'algo.act.hidden_dim': 'ACT advanced: Hidden dimension',
    'algo.act.dim_feedforward': 'ACT advanced: Feedforward dimension',
    'algo.act.enc_layers': 'ACT advanced: Encoder layers',
    'algo.act.dec_layers': 'ACT advanced: Decoder layers',
    'algo.act.nheads': 'ACT advanced: Attention heads',
    'algo.act.latent_dim': 'ACT advanced: Latent dimension',
    'algo.act.pretrained_backbone': 'ACT advanced: Pretrained image backbone',
    'algo.act.temporal_agg': 'ACT advanced: Temporal ensembling (rollout)',
    'algo.act.temporal_ensemble_coeff': 'ACT advanced: Ensemble coefficient (rollout)',
    'algo.act.query_frequency': 'ACT advanced: Replan interval (rollout)',
    'algo.horizon.prediction_horizon': 'DP common: Prediction horizon',
    'algo.horizon.observation_horizon': 'DP advanced: Observation history',
    'algo.horizon.action_horizon': 'DP advanced: Executed action horizon',
    'algo.unet.down_dims': 'DP advanced: U-Net dimensions',
    'algo.ddpm.num_train_timesteps': 'DP advanced: Training diffusion steps',
    'algo.ddpm.num_inference_timesteps': 'DP advanced: Inference diffusion steps',
}

MEANINGS = {
    'train.num_epochs': 'Maximum training epochs; each epoch uses the configured batch budget.',
    'train.batch_size': 'Sequence samples in each optimizer update.',
    'train.cuda': 'Request CUDA training; runtime availability determines the actual device.',
    'train.seed': 'Training random seed; the menu also uses a shared seed for splitting recordings.',
    'train.max_grad_norm': 'Gradient clipping threshold; null leaves clipping disabled.',
    'train.seq_length': 'ACT chunk length; for DP this is prediction horizon minus observation history plus one.',
    'train.frame_stack': 'Number of observation frames supplied together; DP uses its observation horizon.',
    'train.pad_seq_length': 'Pad sequences near episode ends instead of discarding short tails.',
    'train.pad_frame_stack': 'Pad observation history at episode starts.',
    'train.hdf5_normalize_obs': 'Normalize observations using statistics computed from training data.',
    'train.hdf5_filter_key': 'Frozen HDF5 mask selecting training recordings.',
    'train.hdf5_validation_filter_key': 'Frozen HDF5 mask selecting validation recordings.',
    'algo.optim_params.policy.optimizer_type': 'Optimizer algorithm used for policy weights.',
    'algo.optim_params.policy.learning_rate.initial': 'Initial optimizer learning rate; epoch logs show the rate actually used.',
    'algo.optim_params.policy.learning_rate.scheduler_type': 'Scheduler family; no scheduler is constructed when epoch_schedule is empty.',
    'algo.optim_params.policy.learning_rate.epoch_schedule': 'Decay milestones, or the endpoint for the linear scheduler. Empty disables the scheduler.',
    'algo.optim_params.policy.learning_rate.decay_factor': 'Learning-rate multiplier or endpoint factor used by an enabled scheduler.',
    'algo.optim_params.policy.regularization.L2': 'Optimizer weight decay; for AdamW this is decoupled weight decay.',
    'algo.act.kl_weight': 'Weight multiplying ACT KL loss in reconstruction loss plus KL weight times KL loss.',
    'algo.act.qpos_noise_std': 'Training-only Gaussian noise on normalized joint inputs, so the policy must use the cameras. 0 disables it; validation and rollout are noise-free.',
    'algo.act.hidden_dim': 'Transformer embedding width.',
    'algo.act.dim_feedforward': 'Width of transformer feedforward layers.',
    'algo.act.enc_layers': 'Number of transformer encoder layers.',
    'algo.act.dec_layers': 'Number of transformer decoder layers.',
    'algo.act.nheads': 'Attention heads; hidden dimension must divide evenly by this value.',
    'algo.act.latent_dim': 'Dimension of the ACT variational latent representation.',
    'algo.act.backbone': 'ACT image feature extractor architecture.',
    'algo.act.pretrained_backbone': 'Initialize the ACT image backbone with pretrained weights.',
    'algo.act.temporal_agg': 'Inference-only: blend predictions for the same timestep from overlapping chunks.',
    'algo.act.temporal_ensemble_coeff': 'Inference-only: positive favors older predictions, negative favors newer, zero averages.',
    'algo.act.query_frequency': 'Inference-only, ensembling off: 0 executes a full chunk; otherwise replan after this many steps.',
    'algo.horizon.observation_horizon': 'Past observations used to condition DP.',
    'algo.horizon.prediction_horizon': 'Total action sequence predicted by DP.',
    'algo.horizon.action_horizon': 'DP actions executed before predicting another sequence.',
    'algo.unet.down_dims': 'Channel widths of the DP denoising U-Net.',
    'algo.ddpm.num_train_timesteps': 'Length of the DDPM training noise schedule.',
    'algo.ddpm.num_inference_timesteps': 'DDPM denoising steps for each rollout prediction.',
    'experiment.epoch_every_n_steps': 'Optimizer-update batches per configured training epoch.',
    'experiment.validation_epoch_every_n_steps': 'Sampled validation batches per epoch.',
    'experiment.save.every_n_epochs': 'Periodic checkpoint interval; best-validation saves are additional.',
    'experiment.ckpt_path': 'Optional initialization checkpoint; null starts a fresh policy training run.',
    'experiment.save.on_best_validation': 'Save a checkpoint whenever sampled validation loss reaches a new minimum.',
}


def flatten_configuration(value, prefix=''):
    """Keep scalar lists intact and enumerate every object within structured lists."""
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from flatten_configuration(child, prefix + '.' + key if prefix else key)
    elif isinstance(value, list) and value and all(isinstance(child, dict) for child in value):
        for index, child in enumerate(value):
            yield from flatten_configuration(child, '{}[{}]'.format(prefix, index))
    else:
        yield prefix, value


def _section(path):
    if path.startswith('algo.optim_params.') or path in ('train.num_epochs', 'train.batch_size', 'train.seed', 'train.max_grad_norm'):
        return 'Training and optimization'
    if path in ('algo.act.temporal_agg', 'algo.act.temporal_ensemble_coeff', 'algo.act.query_frequency'):
        return 'ACT rollout defaults'
    if path.startswith(('algo.act.', 'algo.loss.')):
        return 'ACT architecture and objective'
    if path.startswith('algo.'):
        return 'Algorithm architecture and objective'
    if path.startswith(('train.data', 'train.hdf5_', 'train.action_', 'train.dataset_', 'observation.', 'snapshot.')) or path in (
            'train.seq_length', 'train.frame_stack', 'train.pad_seq_length', 'train.pad_frame_stack',
            'train.goal_mode', 'train.num_data_workers', 'train.data_format', 'train.shuffled_obs_key_groups'):
        return 'Data and preprocessing'
    if path.startswith('experiment.save.'):
        return 'Checkpoint saving'
    if path.startswith(('experiment.rollout.', 'experiment.mse.')) or path in ('experiment.validate', 'experiment.epoch_every_n_steps', 'experiment.validation_epoch_every_n_steps'):
        return 'Validation and evaluation'
    return 'Run identity, files and logging'


def _effect(config, path):
    algo = config['algo_name']
    if algo == 'act' and path.startswith('algo.loss.'):
        return 'Unused by this ACT objective. ACT directly computes reconstruction L1 plus algo.act.kl_weight times KL.'
    if algo == 'act' and path.startswith('observation.encoder.'):
        return 'Unused generic encoder defaults for ACT; ACT constructs its image backbone from algo.act settings.'
    if path.startswith('experiment.rollout.') and path != 'experiment.rollout.enabled' and not config['experiment']['rollout']['enabled']:
        return 'Inactive: automatic training-time environment rollouts are disabled.'
    if path.startswith('experiment.mse.') and path != 'experiment.mse.enabled' and not config['experiment']['mse']['enabled']:
        return 'Inactive: the optional reconstruction evaluation block is disabled.'
    for scheduler in ('ddpm', 'ddim'):
        if path.startswith('algo.' + scheduler + '.') and path != 'algo.' + scheduler + '.enabled':
            if not config['algo'].get(scheduler, {}).get('enabled', False):
                return 'Inactive: this diffusion scheduler is disabled.'
    if path.startswith(('meta.', 'experiment.logging.')) or path in ('train.output_dir', 'experiment.name', 'algo_name'):
        return 'Run metadata or logging configuration, not a model-learning hyperparameter.'
    if path.endswith(('.learning_rate.scheduler_type', '.learning_rate.decay_factor')):
        schedule = config['algo']['optim_params']['policy']['learning_rate'].get('epoch_schedule', [])
        if not schedule:
            return 'Inactive: epoch_schedule is empty, so no learning-rate scheduler is constructed.'
    return MEANINGS.get(path, 'Saved backend configuration. See menu access for available controls.')


def configuration_catalog(config, details=None):
    rows = []
    for path, value in flatten_configuration(config):
        menu = MENU_FIELDS.get(path, 'Not exposed in menu')
        if path == 'train.seq_length':
            menu = 'ACT common: Chunk length' if config['algo_name'] == 'act' else 'Derived from DP horizons'
        elif path == 'train.frame_stack' and config['algo_name'] == 'diffusion_policy':
            menu = 'Derived from DP observation history'
        elif path.startswith('train.data['):
            menu = 'Derived from dataset selection (option 4 or 7)'
        rows.append(dict(path=path, name=path.rsplit('.', 1)[-1].replace('_', ' ').capitalize(),
                         value=value, section=_section(path), menu=menu, source='Saved configuration',
                         effect=_effect(config, path)))
    recorded = {row['path'] for row in rows}
    for path, value in [('algo.optim_params.policy.optimizer_type', 'adam'),
                        ('algo.optim_params.policy.learning_rate.scheduler_type', 'multistep')]:
        if path not in recorded:
            rows.append(dict(path=path, name=path.rsplit('.', 1)[-1].replace('_', ' ').capitalize(),
                value=value, section='Training and optimization', menu='Not exposed in menu',
                source='Backend fallback; absent from saved configuration', effect=MEANINGS[path]))
    if config['algo_name'] == 'act':
        for key, value in [('temporal_agg', False), ('temporal_ensemble_coeff', 0.01), ('query_frequency', 0),
                           ('qpos_noise_std', 0.0)]:
            if key not in config['algo']['act']:
                path = 'algo.act.' + key
                rows.append(dict(path=path, name=key.replace('_', ' ').capitalize(), value=value,
                    section=_section(path), menu=MENU_FIELDS[path], source='Legacy compatibility fallback; absent from saved configuration',
                    effect=MEANINGS[path]))
    if details:
        total = (details.get('train_count') or 0) + (details.get('valid_count') or 0)
        values = {'datasets': details.get('datasets'), 'training_recordings': details.get('train_count'),
                  'validation_recordings': details.get('valid_count'), 'image_size': details.get('image_size'),
                  'split_seed': (details.get('split') or {}).get('seed'),
                  'validation_percentage_actual': 100 * details['valid_count'] / total
                      if total and details.get('valid_count') is not None else None}
        controls = {'image_size': 'Advanced: Image size (new raw snapshots only)',
                    'split_seed': 'Common: Random seed (shared split)',
                    'validation_percentage_actual': 'Common: Requested validation share; actual counts can differ for grouped cycles'}
        for key, value in values.items():
            rows.append(dict(path='snapshot.' + key, name=key.replace('_', ' ').capitalize(), value=value,
                section='Data and preprocessing', menu=controls.get(key, 'Derived from frozen dataset selection'),
                source='Frozen dataset metadata or derived counts', effect='The selected run uses this frozen snapshot.'))
    return rows


def act_build_defaults():
    """Expose code-level architecture defaults without claiming historical provenance."""
    from config.settings import REPO_ROOT as root
    source = root / 'third_party/act/act/detr/main.py'
    wanted = {'--dropout': 'Transformer dropout', '--pre_norm': 'Pre-layer normalization',
              '--dilation': 'Dilated image backbone', '--position_embedding': 'Image positional embedding'}
    result = []
    for node in ast.walk(ast.parse(source.read_text())):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'add_argument' or not node.args:
            continue
        try:
            name = ast.literal_eval(node.args[0])
        except (ValueError, TypeError):
            continue
        if name not in wanted:
            continue
        keywords = {item.arg: item.value for item in node.keywords}
        if 'default' in keywords:
            value = ast.literal_eval(keywords['default'])
        elif 'action' in keywords and ast.literal_eval(keywords['action']) == 'store_true':
            value = False
        else:
            continue
        result.append((wanted[name], value))
    transformer = root / 'third_party/act/act/detr/models/transformer.py'
    for node in ast.parse(transformer.read_text()).body:
        if not isinstance(node, ast.ClassDef) or node.name != 'Transformer':
            continue
        constructor = next(item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == '__init__')
        defaults = dict(zip([arg.arg for arg in constructor.args.args][-len(constructor.args.defaults):], constructor.args.defaults))
        result.append(('Transformer activation', ast.literal_eval(defaults['activation'])))
    implementation = root / 'robomimic-r2d2/robomimic/algo/act.py'
    for node in ast.walk(ast.parse(implementation.read_text())):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'Normalize':
            for keyword in node.keywords:
                if keyword.arg in ('mean', 'std'):
                    result.append(('ACT image normalization ' + keyword.arg, ast.literal_eval(keyword.value)))
    return result
