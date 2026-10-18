"""Shared offline guards for curated training folders."""
from pathlib import Path
import re


def require_fresh(project, allow_building=False):
    project = Path(project)
    marker = project / 'train_data' / 'STALE.json'
    if not marker.exists() and not allow_building:
        marker = project / 'train_data' / 'BUILDING.json'
    if marker.exists():
        raise ValueError('Stale train_data: {}; rebuild into a fresh project with '
                         'prepare_act_datasets.py --dataset-name {} --rebuild-to NEW --convert'.format(
                             marker, project.name))


def require_training_folders(paths):
    """Check single and combined Dobot task folders before importing the trainer."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    for path in paths:
        path = Path(path).expanduser()
        require_fresh(path.parent if path.name == 'train_data' else path)


def explicit_rollout_name(name):
    return 'rollout' in re.split(r'[^a-z0-9]+', str(name).lower()) or 'rollouts' in re.split(
        r'[^a-z0-9]+', str(name).lower())


def require_rollout_opt_in(metadata, project, allow_rollouts=False):
    if metadata.get('source') == 'rollout' and not (allow_rollouts and explicit_rollout_name(Path(project).name)):
        raise ValueError('Rollout requires --allow-rollouts and a project name containing rollout or rollouts: {}'.format(project))
