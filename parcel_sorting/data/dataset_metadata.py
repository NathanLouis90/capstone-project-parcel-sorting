"""Read schema-3 pick-to-scan episodes and write their provenance."""
import json
import math
from pathlib import Path
from config.settings import RECORDING
from config.settings import MEDIA as MEDIUM_SETTINGS

# Media come from config/settings.py; add a medium there, not here.
MEDIA = tuple(MEDIUM_SETTINGS)
SCHEMA_VERSION = 3


def require_current_schema(metadata):
    if (not isinstance(metadata, dict)
            or type(metadata.get('schema_version')) is not int
            or metadata['schema_version'] != SCHEMA_VERSION):
        raise ValueError('Recording metadata must use pick-to-scan schema {}'.format(SCHEMA_VERSION))


def recording_period_ms(metadata):
    period = metadata.get('control_period_ms')
    if (isinstance(period, bool) or not isinstance(period, (int, float))
            or not math.isfinite(period) or period <= 0):
        raise ValueError('Invalid recording rate: control_period_ms must be positive and finite')
    return period


def validate_medium_face(medium, label_face):
    if medium not in MEDIA:
        raise ValueError('Choose medium envelope, poly_mailer, or carton')
    faces = MEDIUM_SETTINGS[medium]['label_faces']
    if label_face not in faces:
        raise ValueError('Invalid label face for {}: {}'.format(medium, label_face))


def read_episode_metadata(episode_dir):
    path = Path(episode_dir) / RECORDING['metadata_filename']
    if not path.exists():
        raise ValueError('Required recording metadata missing: {}'.format(path))
    metadata = json.loads(path.read_text())
    require_current_schema(metadata)
    recording_period_ms(metadata)
    validate_medium_face(metadata.get('medium'), metadata.get('label_face'))
    if not metadata.get('recording_complete'):
        raise ValueError('Recording was interrupted; review it before conversion')
    if not metadata.get('cycle_id') or not metadata.get('episode_id'):
        raise ValueError('Recording requires episode and cycle IDs')
    return metadata


def write_hdf5_metadata(root, metadata):
    require_current_schema(metadata)
    # Provenance is separate from policy observations and scanner results.
    keys = ('schema_version', 'episode_id', 'cycle_id', 'medium', 'label_face',
            'started_at', 'ended_at', 'recording_complete', 'review_status', 'reviewed_at',
            'frame_count', 'control_period_ms', 'control_overruns', 'source')
    saved = {key: metadata[key] for key in keys if key in metadata}
    root.attrs['episode_metadata_json'] = json.dumps(saved)
    for key in ('medium', 'label_face', 'cycle_id'):
        if saved.get(key) is not None:
            root.attrs[key] = saved[key]
