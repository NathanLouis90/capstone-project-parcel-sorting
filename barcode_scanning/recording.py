"""Record pick-to-scan episode provenance without scanner input."""
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
from .barcode_scanning_config import RECORDING
from .dataset_metadata import validate_medium_face
from experiments.experiments_config import CONTROL


def write_metadata(path, metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.metadata-', suffix='.json', dir=str(path.parent))
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(metadata, stream, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class RecordingSession:
    def __init__(self, medium, label_face):
        validate_medium_face(medium, label_face)
        self.medium, self.label_face = medium, label_face
        self.active, self.metadata, self.path = False, None, None

    def start(self, episode_dir):
        episode_dir = Path(episode_dir)
        if self.active or episode_dir.exists():
            raise ValueError('Recording active or episode already exists: {}'.format(episode_dir))
        self.path = episode_dir / RECORDING['metadata_filename']
        self.metadata = dict(schema_version=3, medium=self.medium, label_face=self.label_face,
                             episode_id=episode_dir.name, cycle_id=uuid.uuid4().hex,
                             started_at=time.time(), recording_complete=False,
                             review_status='unreviewed', frame_count=0, control_overruns=0,
                             control_period_ms=CONTROL['control_period_ms'])
        self._save()
        self.active = True

    def _save(self):
        write_metadata(self.path, self.metadata)

    def poll(self):
        pass  # Scanner ownership belongs exclusively to the runtime supervisor.

    def record_frame(self):
        if self.active:
            self.metadata['frame_count'] += 1

    def stop(self, complete=True):
        if self.active:
            self.metadata.update(ended_at=time.time(), recording_complete=complete)
            self._save()
            self.active = False


def inspect_episode(episode_dir):
    from .dataset_metadata import read_episode_metadata
    episode_dir = Path(episode_dir).expanduser().resolve()
    metadata = read_episode_metadata(episode_dir)
    if metadata is None:
        raise ValueError('No recording metadata found')
    identifiers = []
    for folder, extension in [('observation', '.pkl'), ('topImg', '.jpg'),
                              ('leftImg', '.jpg'), ('rightImg', '.jpg')]:
        identifiers.append({p.stem for p in (episode_dir / folder).glob('*' + extension)})
    observations = identifiers[0]
    if not observations or any(ids != observations for ids in identifiers):
        raise ValueError('Missing frames or camera/observation identifiers do not match')
    if any(not value.isdigit() for value in observations) or len(observations) != metadata.get('frame_count'):
        raise ValueError('Frame count or numeric identifiers differ from metadata')
    return dict(episode=str(episode_dir), medium=metadata['medium'],
                label_face=metadata.get('label_face'), frames=len(observations),
                cycle_id=metadata['cycle_id'], review_status=metadata['review_status'],
                legacy_recording=metadata.get('legacy_recording', False))
