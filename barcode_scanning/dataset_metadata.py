"""Read current or legacy episodes and write observation-independent provenance."""
import json
from pathlib import Path
from .barcode_scanning_config import RECORDING

MEDIA = ('envelope', 'poly_mailer', 'carton')


def validate_medium_face(medium, label_face):
    if medium not in MEDIA:
        raise ValueError('Choose medium envelope, poly_mailer, or carton')
    faces = ('top', 'bottom', 'front', 'rear') if medium == 'carton' else ('top', 'bottom')
    if label_face not in faces:
        raise ValueError('Invalid label face for {}: {}'.format(medium, label_face))


def read_episode_metadata(episode_dir):
    path = Path(episode_dir) / RECORDING['metadata_filename']
    if not path.exists():
        path = Path(episode_dir) / 'metadata.json'
    if not path.exists():
        return None
    metadata = json.loads(path.read_text())
    if metadata.get('schema_version', 0) < 3:
        from .legacy_metadata import read_legacy_metadata
        metadata = read_legacy_metadata(episode_dir)
        if metadata is not None:
            metadata = dict(metadata, legacy_recording=True)
        return metadata
    validate_medium_face(metadata.get('medium'), metadata.get('label_face'))
    if not metadata.get('recording_complete'):
        raise ValueError('Recording was interrupted; review it before conversion')
    if not metadata.get('cycle_id') or not metadata.get('episode_id'):
        raise ValueError('Recording requires episode and cycle IDs')
    return metadata


def write_hdf5_metadata(root, metadata, timesteps):
    if metadata is None:
        return
    # New training files never receive scanner or legacy task fields.
    keys = ('schema_version', 'episode_id', 'cycle_id', 'medium', 'label_face',
            'started_at', 'ended_at', 'recording_complete', 'review_status', 'reviewed_at',
            'frame_count', 'control_period_ms', 'control_overruns', 'source', 'legacy_recording')
    saved = {key: metadata[key] for key in keys if key in metadata}
    root.attrs['episode_metadata_json'] = json.dumps(saved)
    for key in ('medium', 'label_face', 'cycle_id'):
        if saved.get(key) is not None:
            root.attrs[key] = saved[key]
