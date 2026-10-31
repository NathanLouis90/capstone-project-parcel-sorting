"""Dataset management and reproducible ACT/DP training without manual intermediates.

Only reviewed, trusted local recordings are supported. This module never opens
robot devices. Generated datasets are immutable and live outside source projects.
"""

from collections import Counter, defaultdict, deque
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import pickle
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import cv2
import h5py
import numpy as np

from parcel_sorting.data.dataset_metadata import read_episode_metadata, write_hdf5_metadata
from parcel_sorting.data.recording import inspect_episode, write_metadata
from parcel_sorting.data.curation import Plan, execute, hashes, metadata, signature
from config.settings import EPISODE_FORMAT, REPO_ROOT as ROOT

CAMERAS = {'top': 'topImg', 'left_wrist': 'leftImg', 'right_wrist': 'rightImg'}
PIPELINE_VERSION = 1


@dataclass
class TrainingSettings:
    validation_percent: float = 20.0
    seed: int = 0
    epochs: int = 1000
    batch_size: int = 8
    train_steps: int = 100
    validation_steps: int = 10
    save_every: int = 50
    act_learning_rate: float = 0.0001
    dp_learning_rate: float = 0.0001
    prediction_length: int = 16
    dp_observation_length: int = 2
    dp_action_length: int = 8
    dp_unet_dimensions: list = field(default_factory=lambda: [256, 512, 1024])
    dp_training_diffusion_steps: int = 100
    dp_inference_diffusion_steps: int = 100
    act_kl_weight: float = 20.0
    # Training-only noise on normalized joint inputs. Without it, the poly-mailer
    # ACT run learned to ignore the cameras; 0.5 restored camera use in a pilot.
    act_qpos_noise_std: float = 0.5
    act_hidden_dim: int = 512
    act_feedforward_dim: int = 3200
    act_encoder_layers: int = 4
    act_decoder_layers: int = 7
    act_heads: int = 8
    act_latent_dim: int = 32
    act_pretrained: bool = True
    act_temporal_ensemble: bool = False
    act_temporal_ensemble_coeff: float = 0.01
    act_query_frequency: int = 0
    image_size: int = 128
    device: str = 'cuda'

    def validate(self, algorithm=None):
        if not math.isfinite(self.validation_percent) or not 0 < self.validation_percent < 100:
            raise ValueError('Validation percentage must be between 0 and 100')
        positive = ['epochs', 'batch_size', 'train_steps', 'validation_steps', 'save_every',
                    'prediction_length', 'image_size']
        if algorithm in (None, 'act'):
            positive.extend(('act_hidden_dim', 'act_feedforward_dim', 'act_encoder_layers',
                             'act_decoder_layers', 'act_heads', 'act_latent_dim'))
        if algorithm in (None, 'diffusion_policy'):
            positive.extend(('dp_observation_length', 'dp_action_length',
                             'dp_training_diffusion_steps', 'dp_inference_diffusion_steps'))
        for key in positive:
            value = getattr(self, key)
            if type(value) is not int or value < 1:
                raise ValueError('{} must be a positive integer'.format(key))
        if type(self.seed) is not int or not 0 <= self.seed < 2 ** 32:
            raise ValueError('Seed must be an integer from 0 through 4294967295')
        for key in ('act_learning_rate', 'dp_learning_rate'):
            if algorithm is not None and key != ('act_learning_rate' if algorithm == 'act' else 'dp_learning_rate'):
                continue
            if not math.isfinite(getattr(self, key)) or getattr(self, key) <= 0:
                raise ValueError('{} must be positive and finite'.format(key))
        if not math.isfinite(self.act_kl_weight) or self.act_kl_weight < 0:
            raise ValueError('ACT KL weight must be nonnegative and finite')
        if (type(self.act_qpos_noise_std) not in (int, float) or not math.isfinite(self.act_qpos_noise_std)
                or self.act_qpos_noise_std < 0):
            raise ValueError('ACT joint-input noise must be nonnegative and finite')
        if algorithm in (None, 'act') and self.act_hidden_dim % self.act_heads:
            raise ValueError('ACT hidden dimension must divide evenly by attention heads')
        if algorithm in (None, 'act'):
            if type(self.act_temporal_ensemble) is not bool:
                raise ValueError('ACT temporal ensembling must be true or false')
            if (type(self.act_temporal_ensemble_coeff) not in (int, float)
                    or not math.isfinite(self.act_temporal_ensemble_coeff)):
                raise ValueError('ACT ensemble coefficient must be finite')
            if type(self.act_query_frequency) is not int or not 0 <= self.act_query_frequency <= self.prediction_length:
                raise ValueError('ACT replan interval must be 0 (full chunk) or between 1 and chunk length')
        if algorithm in (None, 'diffusion_policy'):
            if self.dp_observation_length - 1 + self.dp_action_length > self.prediction_length:
                raise ValueError('DP observation length - 1 + action length must fit prediction length')
            if (not isinstance(self.dp_unet_dimensions, (list, tuple)) or len(self.dp_unet_dimensions) < 2
                    or any(type(v) is not int or v < 8 or v % 8 for v in self.dp_unet_dimensions)):
                raise ValueError('DP U-Net dimensions need at least two positive multiples of 8')
            multiple = 2 ** (len(self.dp_unet_dimensions) - 1)
            if self.prediction_length % multiple:
                raise ValueError('DP prediction horizon must be a multiple of {}'.format(multiple))
            if self.dp_inference_diffusion_steps > self.dp_training_diffusion_steps:
                raise ValueError('DP inference diffusion steps cannot exceed training diffusion steps')
        if self.image_size < 80:
            raise ValueError('Image size must be at least 80 pixels for the image encoders')
        if self.device not in ('cuda', 'cpu') or type(self.act_pretrained) is not bool:
            raise ValueError('Choose device cuda/cpu and a boolean pretrained setting')


def dataset_path(root, name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name) or name in ('.', '..'):
        raise ValueError('Use a dataset name containing letters, numbers, underscores, or hyphens')
    path = Path(root) / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Dataset symlinks are not supported')
    return path


def raw_episodes(project):
    folder = Path(project) / 'collect_data'
    _refuse_symlink_path(folder)
    return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith('.')) if folder.is_dir() else []


def _refuse_symlink_path(path):
    path = Path(path)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Recording symlinks are not supported: ' + str(path))


def discover_datasets(root):
    root = Path(root)
    result = []
    if not root.exists():
        return result
    for project in sorted(root.iterdir()):
        if project.name.startswith('.') or project.is_symlink() or not (project / 'collect_data').is_dir():
            continue
        counts, media = Counter(), set()
        for episode in raw_episodes(project):
            try:
                m = metadata(episode)
                counts[m.get('review_status', 'unreviewed')] += 1
                media.add(m.get('medium', 'unknown'))
                if not m.get('recording_complete'):
                    counts['incomplete'] += 1
            except (OSError, ValueError, TypeError):
                counts['invalid'] += 1
        result.append(dict(name=project.name, path=project, counts=dict(counts), media=sorted(media)))
    return result


def _legacy_stale(project, reason):
    folder = Path(project) / 'train_data'
    if folder.exists():
        _refuse_symlink_path(folder / 'STALE.json')
        write_metadata(folder / 'STALE.json', dict(reason=reason, timestamp=datetime.now(timezone.utc).isoformat()))


def _audit(project, record):
    with (Path(project) / 'curation_log.jsonl').open('a') as stream:
        stream.write(json.dumps(record, sort_keys=True) + '\n')


def plan_rejected_deletion(project):
    """Find rejected raw episodes and their attributable legacy artifacts."""
    project = Path(project)
    _refuse_symlink_path(project)
    _refuse_symlink_path(project / 'curation_log.jsonl')
    rejected = [p for p in raw_episodes(project) if metadata(p).get('review_status') == 'rejected']
    quarantine = project / 'rejected_data'
    if quarantine.exists():
        rejected.extend(p for p in quarantine.iterdir() if p.is_dir() and p.name != 'converted'
                        and metadata(p).get('review_status') == 'rejected')
    identifiers = {p.name for p in rejected}
    paths = list(rejected)
    for folder in (project / 'train_data', quarantine / 'converted/train_data'):
        for path in folder.glob('*.hdf5'):
            with h5py.File(str(path), 'r') as source:
                saved = json.loads(source.attrs.get('episode_metadata_json', '{}'))
            if saved.get('episode_id') in identifiers:
                paths.append(path)
    for identifier in identifiers:
        for folder in (project / 'output_videos', quarantine / 'converted/output_videos'):
            paths.extend(folder.glob(identifier + '_video*.mp4'))
        log = project / 'conversion_logs' / (identifier + '.log')
        if log.exists():
            paths.append(log)
    for path in paths:
        _refuse_symlink_path(path)
    return dict(project=project, episodes=rejected,
                payloads=[dict(path=p, hashes=hashes(p)) for p in sorted(set(paths))])


def delete_rejected(plan):
    """Permanently delete the previewed selection; never create a quarantine."""
    for path in (plan['project'] / 'curation_log.jsonl', plan['project'] / 'train_data/STALE.json'):
        _refuse_symlink_path(path)
    for episode in plan['episodes']:
        _refuse_symlink_path(episode)
        if metadata(episode).get('review_status') != 'rejected':
            raise ValueError('Review status changed; inspect the deletion again')
    for payload in plan['payloads']:
        _refuse_symlink_path(payload['path'])
        if hashes(payload['path']) != payload['hashes']:
            raise ValueError('Files changed since deletion preview: ' + str(payload['path']))
    deleted = []
    try:
        for payload in plan['payloads']:
            path = payload['path']
            shutil.rmtree(str(path)) if path.is_dir() else path.unlink()
            deleted.append(str(path))
    finally:
        if deleted:
            _legacy_stale(plan['project'], 'Rejected recordings permanently deleted')
            _audit(plan['project'], dict(command='delete rejected', deleted=deleted,
                                         timestamp=datetime.now(timezone.utc).isoformat()))
    return len(plan['episodes'])


def accepted_episodes(project):
    return sorted((p for p in raw_episodes(project) if metadata(p).get('review_status') == 'accepted'),
                  key=lambda p: (metadata(p).get('started_at', 0), p.name))


def move_recordings(root, source_name, destination_name, identifiers):
    """Create a compatible destination automatically and move without registration."""
    source, destination = dataset_path(root, source_name), dataset_path(root, destination_name)
    if source == destination or not (source / 'collect_data').is_dir():
        raise ValueError('Choose an existing source and a different destination')
    for project in (source, destination):
        for path in (project / 'curation_log.jsonl', project / 'train_data/STALE.json'):
            _refuse_symlink_path(path)
    selected = {p.name: p for p in raw_episodes(source)}
    if not identifiers or len(set(identifiers)) != len(identifiers) or any(i not in selected for i in identifiers):
        raise ValueError('Choose unique episode IDs from the source dataset')
    paths = [selected[i] for i in identifiers]
    signatures = [signature(p) for p in paths + raw_episodes(destination)]
    for key in ('medium', 'schema_version', 'camera_names', 'control_period_ms'):
        if any(s[key] != signatures[0][key] for s in signatures):
            raise ValueError('Source and destination have incompatible ' + key)
    plan = Plan('move recordings')
    if not destination.exists():
        plan.new_projects.add(destination)
    for path in paths:
        if (destination / 'rejected_data' / path.name).exists():
            raise ValueError('Episode already exists in the destination')
        plan.add(path, destination / 'collect_data' / path.name)
    plan.projects.update((source, destination))
    # The menu presents dataset names and counts; internal audit paths stay internal.
    with redirect_stdout(io.StringIO()):
        execute(plan, yes=True)
    return len(paths)


def collect_accepted(projects):
    entries, identities, periods, media = [], set(), set(), set()
    for project in sorted(map(Path, projects)):
        _refuse_symlink_path(project)
        for episode in accepted_episodes(project):
            _refuse_symlink_path(episode)
            m = read_episode_metadata(episode)
            if m.get('source') == 'rollout':
                raise ValueError('Select demonstration datasets; rollout recordings require the separate opt-in workflow')
            inspect_episode(episode)
            if m['episode_id'] != episode.name:
                raise ValueError('Episode ID differs from its folder: ' + str(episode))
            identity = (m['cycle_id'], m['episode_id'])
            if identity in identities:
                raise ValueError('The same recording was selected twice; choose one copy of ' + episode.name)
            identities.add(identity)
            periods.add(m['control_period_ms'])
            media.add(m['medium'])
            entries.append(dict(id=project.name + '/' + episode.name, path=episode,
                                metadata=m, cycle=m['cycle_id'], medium=m['medium']))
    if not entries:
        raise ValueError('No accepted recordings selected; review episodes first')
    if len(media) != 1 or len(periods) != 1:
        raise ValueError('Combine datasets of one parcel medium and one recording rate')
    return entries


def split_recordings(entries, validation_percent, seed):
    """Split whole parcel cycles so related episodes cannot leak across partitions."""
    if not math.isfinite(validation_percent) or not 0 < validation_percent < 100:
        raise ValueError('Validation percentage must be between 0 and 100')
    cycles = defaultdict(list)
    for index, entry in enumerate(entries):
        cycles[entry['cycle']].append('demo_{}'.format(index))
    keys = sorted(cycles)
    if len(keys) < 2:
        raise ValueError('At least two independent parcel cycles are needed for train/validation')
    random.Random(seed).shuffle(keys)
    count = max(1, min(len(keys) - 1, round(len(keys) * validation_percent / 100)))
    result = dict(recipe={'medium': entries[0]['medium']}, seed=seed,
                  validation_percent=validation_percent, train=[], valid=[],
                  sources=[dict(id=e['id'], cycle=e['cycle'], sha256=e.get('sha256', 'pending')) for e in entries])
    for index, cycle in enumerate(keys):
        result['valid' if index < count else 'train'].extend(cycles[cycle])
    return result


def _episode_digest(episode):
    return hashlib.sha256(json.dumps(hashes(episode), sort_keys=True).encode()).hexdigest()


def _file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_dataset(projects, settings, cache_root, progress=print, algorithm=None):
    """Build the trainer's final RGB HDF5 directly from accepted raw recordings."""
    settings.validate(algorithm)
    entries = collect_accepted(projects)
    for index, entry in enumerate(entries, 1):
        progress('Checking recording {}/{}'.format(index, len(entries)))
        entry['sha256'] = _episode_digest(entry['path'])
    split = split_recordings(entries, settings.validation_percent, settings.seed)
    mirror = np.tile(np.asarray(EPISODE_FORMAT['MIRROR_STATE_MULTIPLY']), 2)
    if mirror.shape != (14,) or not np.isfinite(mirror).all():
        raise ValueError('Invalid joint/action mirror settings')
    description = dict(version=PIPELINE_VERSION, split=split, image_size=settings.image_size,
                       mirror=mirror.tolist(), color='RGB', medium=entries[0]['medium'])
    identity = hashlib.sha256(json.dumps(description, sort_keys=True).encode()).hexdigest()
    cache_root = Path(cache_root)
    _refuse_symlink_path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    destination = cache_root / identity
    if destination.exists():
        for name in ('manifest.json', 'dataset.hdf5', 'split.json'):
            _refuse_symlink_path(destination / name)
        manifest = json.loads((destination / 'manifest.json').read_text())
        if (manifest['description'] != description
                or json.loads((destination / 'split.json').read_text()) != split
                or _file_digest(destination / 'dataset.hdf5') != manifest['dataset_sha256']):
            raise ValueError('Prepared data failed its integrity check; inspect the training cache')
        progress('Reusing prepared data: {} training, {} validation recordings.'.format(len(split['train']), len(split['valid'])))
        return destination
    temporary = Path(tempfile.mkdtemp(prefix='.preparing-', dir=str(cache_root)))
    try:
        with h5py.File(str(temporary / 'dataset.hdf5'), 'x') as target:
            data = target.create_group('data')
            data.attrs['env_args'] = json.dumps(dict(env_name='DobotParcelOffline', type=1,
                                                      env_kwargs={'medium': entries[0]['medium']}))
            data.attrs['recipe'] = entries[0]['medium']
            data.attrs['split_file'] = str((destination / 'split.json').resolve())
            data.attrs['split_json'] = json.dumps(split, sort_keys=True)
            total = 0
            for index, entry in enumerate(entries):
                episode, m = entry['path'], entry['metadata']
                frames = sorted((episode / 'observation').glob('*.pkl'), key=lambda p: int(p.stem))
                n = len(frames)
                progress('Preparing recording {}/{} ({} frames)'.format(index + 1, len(entries), n))
                demo = data.create_group('demo_{}'.format(index))
                write_hdf5_metadata(demo, m)
                demo.attrs['recording_id'] = entry['id']
                demo.attrs['num_samples'] = n
                actions = demo.create_dataset('actions', shape=(n, 14), dtype=np.float32)
                obs = demo.create_group('obs')
                qpos = obs.create_dataset('qpos', shape=(n, 14), dtype=np.float32)
                images = {camera: obs.create_dataset(camera, shape=(n, settings.image_size, settings.image_size, 3),
                          dtype=np.uint8, chunks=(1, settings.image_size, settings.image_size, 3), compression='gzip')
                          for camera in CAMERAS}
                for i, frame in enumerate(frames):
                    # As in the existing recorder/converter, pickles must be trusted local data.
                    recording = pickle.loads(frame.read_bytes())
                    for key, output in (('joint_positions', qpos), ('control', actions)):
                        value = np.asarray(recording[key])
                        if value.shape != (14,) or not np.isfinite(value).all():
                            raise ValueError('Expected 14 finite {} values in {}'.format(key, frame))
                        output[i] = value * mirror
                    for camera, folder in CAMERAS.items():
                        bgr = cv2.imread(str(episode / folder / (frame.stem + '.jpg')))
                        if bgr is None:
                            raise ValueError('Unreadable image in ' + str(episode))
                        images[camera][i] = cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB),
                                                       (settings.image_size, settings.image_size), interpolation=cv2.INTER_AREA)
                if _episode_digest(episode) != entry['sha256']:
                    raise ValueError('Recording changed during preparation; stop recording and retry')
                total += n
            data.attrs['total'] = total
            masks = target.create_group('mask')
            for key in ('train', 'valid'):
                masks.create_dataset(key, data=np.asarray(split[key], dtype='S'))
        write_metadata(temporary / 'split.json', split)
        write_metadata(temporary / 'manifest.json', dict(description=description,
                       dataset_sha256=_file_digest(temporary / 'dataset.hdf5')))
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(str(temporary))
    progress('Prepared {} recordings: {} training, {} validation.'.format(len(entries), len(split['train']), len(split['valid'])))
    return destination


def model_name_valid(name):
    return bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name))


def next_model_name(root, algorithm, medium):
    prefix = 'act' if algorithm == 'act' else 'dp'
    version = 1
    while (Path(root) / '{}_{}_v{}'.format(prefix, medium, version)).exists():
        version += 1
    return '{}_{}_v{}'.format(prefix, medium, version)


def summary_text(name, algorithm, datasets, split, settings):
    lines = ['Model: ' + name, 'Algorithm: ' + ('ACT' if algorithm == 'act' else 'Diffusion Policy'),
             'Datasets: ' + ', '.join(datasets),
             'Training recordings: {}'.format(len(split['train'])),
             'Validation recordings: {}'.format(len(split['valid'])), '', 'Training settings:']
    labels = {
        'validation_percent': 'Validation percentage', 'seed': 'Random seed',
        'epochs': 'Epochs', 'batch_size': 'Batch size', 'train_steps': 'Training batches per epoch',
        'validation_steps': 'Validation batches per epoch', 'save_every': 'Periodic checkpoint interval (epochs)',
        'act_learning_rate': 'ACT learning rate', 'dp_learning_rate': 'DP learning rate',
        'prediction_length': 'ACT chunk length' if algorithm == 'act' else 'DP prediction horizon',
        'dp_observation_length': 'DP observation history',
        'dp_action_length': 'DP executed action horizon', 'act_kl_weight': 'ACT KL weight',
        'act_qpos_noise_std': 'ACT joint-input noise std (training only)',
        'dp_unet_dimensions': 'DP U-Net dimensions',
        'dp_training_diffusion_steps': 'DP training diffusion steps',
        'dp_inference_diffusion_steps': 'DP inference diffusion steps',
        'act_hidden_dim': 'ACT hidden dimension', 'act_feedforward_dim': 'ACT feedforward dimension',
        'act_encoder_layers': 'ACT encoder layers', 'act_decoder_layers': 'ACT decoder layers',
        'act_heads': 'ACT attention heads', 'act_latent_dim': 'ACT latent dimension',
        'act_pretrained': 'ACT pretrained image backbone', 'image_size': 'Image size (square pixels)',
        'act_temporal_ensemble': 'ACT temporal ensembling (rollout)',
        'act_temporal_ensemble_coeff': 'ACT ensemble coefficient (+ older, - newer)',
        'act_query_frequency': 'ACT replan interval when ensembling is off (0 = full chunk)',
        'device': 'Training device',
    }
    lines.extend('  {}: {}'.format(labels[key], value) for key, value in asdict(settings).items()
                 if not key.startswith('dp_' if algorithm == 'act' else 'act_'))
    return '\n'.join(lines) + '\n'


def create_training_jobs(prepared, settings, names, model_root, smoke=False,
                         dataset=None, split_file=None):
    """Reserve new model names and hide generated trainer files inside each model."""
    for algorithm in names:
        settings.validate(algorithm)
    model_root, prepared = Path(model_root), Path(prepared)
    _refuse_symlink_path(model_root)
    for algorithm, name in names.items():
        if algorithm not in ('act', 'diffusion_policy') or not model_name_valid(name):
            raise ValueError('Model names may contain letters, numbers, periods, underscores, and hyphens')
        if (model_root / name).exists():
            raise ValueError('Model name already exists; choose a new name: ' + name)
    if len(set(names.values())) != len(names):
        raise ValueError('Give ACT and DP different model names')
    from robomimic.scripts.config_gen.parcel_sorting_gen import generate_configs
    dataset = Path(dataset) if dataset is not None else prepared / 'dataset.hdf5'
    split_file = Path(split_file) if split_file is not None else prepared / 'split.json'
    split = json.loads(split_file.read_text())
    datasets = sorted({source['id'].split('/')[0] for source in split['sources']})
    jobs = []
    for algorithm, name in names.items():
        folder = model_root / name
        folder.mkdir(parents=True, exist_ok=False)
        options = {
            'experiment.epoch_every_n_steps': settings.train_steps,
            'experiment.validation_epoch_every_n_steps': settings.validation_steps,
            'experiment.save.every_n_epochs': settings.save_every,
            'train.output_dir': str((folder / 'runs').resolve()),
            'train.batch_size': settings.batch_size,
            'train.num_epochs': settings.epochs,
            'train.seed': settings.seed,
            'experiment.env_meta_update_dict': {'env_kwargs': {'medium': split['recipe']['medium']}},
            'train.seq_length': settings.prediction_length,
            'algo.optim_params.policy.learning_rate.initial': settings.act_learning_rate if algorithm == 'act' else settings.dp_learning_rate,
        }
        if algorithm == 'act':
            options.update({'algo.act.kl_weight': settings.act_kl_weight,
                            'algo.act.qpos_noise_std': settings.act_qpos_noise_std,
                            'algo.act.pretrained_backbone': settings.act_pretrained,
                            'algo.act.temporal_agg': settings.act_temporal_ensemble,
                            'algo.act.temporal_ensemble_coeff': settings.act_temporal_ensemble_coeff,
                            'algo.act.query_frequency': settings.act_query_frequency,
                            'algo.act.hidden_dim': settings.act_hidden_dim,
                            'algo.act.dim_feedforward': settings.act_feedforward_dim,
                            'algo.act.enc_layers': settings.act_encoder_layers,
                            'algo.act.dec_layers': settings.act_decoder_layers,
                            'algo.act.nheads': settings.act_heads,
                            'algo.act.latent_dim': settings.act_latent_dim})
        else:
            options.update({'algo.horizon.observation_horizon': settings.dp_observation_length,
                            'algo.horizon.action_horizon': settings.dp_action_length,
                            'algo.horizon.prediction_horizon': settings.prediction_length,
                            'train.frame_stack': settings.dp_observation_length,
                            'train.seq_length': settings.prediction_length - settings.dp_observation_length + 1})
            # Retain the tiny architecture used by explicit software smoke checks.
            if not smoke:
                options.update({'algo.unet.down_dims': list(settings.dp_unet_dimensions),
                                'algo.ddpm.num_train_timesteps': settings.dp_training_diffusion_steps,
                                'algo.ddpm.num_inference_timesteps': settings.dp_inference_diffusion_steps})
        experiment_name = name + ('_smoke' if smoke else '')
        # ConfigGenerator prints manual shell commands, which this menu runs itself.
        with redirect_stdout(io.StringIO()):
            config = generate_configs(dataset, split_file, folder / '.training',
                                      smoke=smoke, cpu=settings.device == 'cpu',
                                      overrides={algorithm: options}, names={algorithm: experiment_name},
                                      algorithms=(algorithm,))[0]
        job = dict(name=name, algorithm=algorithm, folder=str(folder.resolve()), config=str(config.resolve()),
                   dataset=str(dataset.resolve()), medium=split['recipe']['medium'],
                   datasets=datasets, settings=asdict(settings), train_count=len(split['train']),
                   valid_count=len(split['valid']), status='ready', smoke=smoke)
        write_metadata(folder / '.training' / 'job.json', job)
        (folder / 'training_summary.txt').write_text(summary_text(name, algorithm, datasets, split, settings))
        jobs.append(job)
    return jobs


def check_training_device(settings):
    import torch
    if settings.device == 'cuda' and not torch.cuda.is_available():
        raise ValueError('GPU unavailable. Fix the CUDA environment, or choose CPU in advanced settings')


def publish_checkpoint(job, checkpoint):
    """Expose complete saved checkpoints through short, relative symbolic links."""
    folder, checkpoint = Path(job['folder']).resolve(), Path(checkpoint).resolve()
    try:
        checkpoint.relative_to(folder / 'runs')
    except ValueError:
        raise ValueError('Checkpoint is outside this model run')
    match = re.fullmatch(r'model_epoch_(\d+)(?:_best_validation_([\d.eE+\-]+))?\.pth', checkpoint.name)
    if not checkpoint.is_file() or match is None:
        raise ValueError('Expected a saved training checkpoint: ' + str(checkpoint))
    epoch = int(match[1])
    loss = float(match[2]) if match[2] is not None else None
    if loss is not None and not math.isfinite(loss):
        raise ValueError('Checkpoint validation loss must be finite')

    def link(name):
        destination = folder / name
        if destination.exists() and not destination.is_symlink():
            raise ValueError('Refusing to replace an existing checkpoint file: ' + str(destination))
        temporary = folder / ('.' + name + '-' + uuid.uuid4().hex)
        try:
            temporary.symlink_to(os.path.relpath(str(checkpoint), str(folder)))
            os.replace(str(temporary), str(destination))
        finally:
            if temporary.is_symlink():
                temporary.unlink()
        return str(destination)

    if epoch >= job.get('latest_checkpoint_epoch', -1):
        job['latest_checkpoint'] = link('latest.pth')
        job['latest_checkpoint_epoch'] = epoch
    if loss is not None and loss <= job.get('best_checkpoint_loss', float('inf')):
        job['best_checkpoint'] = link('best.pth')
        job['best_checkpoint_epoch'] = epoch
        job['best_checkpoint_loss'] = loss


def run_training_job(job, progress=print):
    """Run one model, retain full logs, and show epoch progress with an ETA."""
    folder = Path(job['folder'])
    config = json.loads(Path(job['config']).read_text())
    if job['status'] != 'ready' or (folder / 'runs' / config['experiment']['name']).exists():
        raise ValueError('This model already started; choose a new model name for another training run')
    environment = dict(os.environ, PYTHONPATH=str(ROOT) + os.pathsep + str(ROOT / 'robomimic-r2d2'),
                       OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    process = None
    recent, tail = deque(maxlen=10), deque(maxlen=20)
    metric_section = None
    from parcel_sorting.training.report import EpochMetrics, generate_training_report
    parser, records = EpochMetrics(), []

    def update_report():
        try:
            generate_training_report(job, records=records)
        except Exception as error:
            progress('Training report could not be updated: ' + str(error))
    job.update(status='running', started_at=datetime.now(timezone.utc).isoformat(), epoch=0)
    write_metadata(folder / '.training/job.json', job)
    try:
        with (folder / 'training.log').open('w') as log, (folder / 'metrics.jsonl').open('w') as metrics:
            process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'robomimic-r2d2/robomimic/scripts/train.py'),
                                        '--config', job['config']], cwd=str(ROOT), env=environment,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in process.stdout:
                log.write(line)
                log.flush()
                tail.append(line.rstrip())
                match = re.fullmatch(r'Train Epoch (\d+)\s*', line)
                if match:
                    metric_section = 'train'
                    epoch = int(match[1])
                    recent.append((epoch, time.monotonic()))
                    estimate = ''
                    if len(recent) > 1:
                        seconds = (recent[-1][1] - recent[0][1]) / (recent[-1][0] - recent[0][0])
                        estimate = ' | about {:.0f} minutes remaining'.format(seconds * (job['settings']['epochs'] - epoch) / 60)
                    progress('{}: epoch {}/{}{}'.format(job['name'], epoch, job['settings']['epochs'], estimate))
                    job['epoch'] = epoch
                    write_metadata(folder / '.training/job.json', job)
                if re.fullmatch(r'Validation Epoch (\d+)\s*', line):
                    metric_section = 'validation'
                loss = re.fullmatch(r'\s*"Loss": ([\d.eE+\-]+),?\s*', line)
                if loss and metric_section:
                    value = float(loss[1])
                    if math.isfinite(value):
                        job[metric_section + '_loss'] = value
                        if metric_section == 'validation':
                            job['best_validation_loss'] = min(value, job.get('best_validation_loss', value))
                            progress('{}: training loss {:.5g} | validation loss {:.5g} | best {:.5g}'.format(
                                job['name'], job.get('train_loss', float('nan')), value, job['best_validation_loss']))
                        write_metadata(folder / '.training/job.json', job)
                if line.startswith('save checkpoint to '):
                    # The trainer prints this only after torch.save has completed.
                    publish_checkpoint(job, line[len('save checkpoint to '):].strip())
                    write_metadata(folder / '.training/job.json', job)
                record = parser.feed(line)
                if record is not None:
                    records.append(record)
                    metrics.write(json.dumps(record, sort_keys=True) + '\n')
                    metrics.flush()
                    if record['phase'] == 'valid' and (record['epoch'] == 1 or record['epoch'] % 25 == 0):
                        update_report()
            if process.wait() != 0:
                raise RuntimeError('Training failed. Recent output:\n' + '\n'.join(tail))
        job['status'] = 'completed'
        progress(job['name'] + ': training completed.')
        for label, key in (('Best checkpoint', 'best_checkpoint'), ('Latest saved checkpoint', 'latest_checkpoint')):
            if key in job:
                progress(label + ': ' + job[key])
    except BaseException:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        job['status'] = 'interrupted' if isinstance(sys.exc_info()[1], KeyboardInterrupt) else 'failed'
        raise
    finally:
        job['ended_at'] = datetime.now(timezone.utc).isoformat()
        write_metadata(folder / '.training/job.json', job)
        update_report()
        if (folder / 'training_report.html').exists():
            progress('Training report: ' + str(folder / 'training_report.html'))


def find_models(root):
    result = []
    root = Path(root)
    if not root.exists():
        return result
    for folder in sorted(root.iterdir()):
        job_file = folder / '.training/job.json'
        if job_file.exists():
            result.append(json.loads(job_file.read_text()))
        elif folder.is_dir():
            configs = sorted(folder.glob('*/*/config.json'))
            if configs:
                config = json.loads(configs[-1].read_text())
                result.append(dict(name=folder.name, status='existing run', folder=str(folder),
                                   legacy_config=config, config=str(configs[-1])))
    return result
