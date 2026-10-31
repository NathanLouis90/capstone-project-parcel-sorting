"""Guard curation against mixing policy rollouts into demonstration projects."""
from pathlib import Path
import re


def explicit_rollout_name(name):
    return 'rollout' in re.split(r'[^a-z0-9]+', str(name).lower()) or 'rollouts' in re.split(
        r'[^a-z0-9]+', str(name).lower())


def require_rollout_opt_in(metadata, project, allow_rollouts=False):
    if metadata.get('source') == 'rollout' and not (allow_rollouts and explicit_rollout_name(Path(project).name)):
        raise ValueError('Rollout requires --allow-rollouts and a project name containing rollout or rollouts: {}'.format(project))
