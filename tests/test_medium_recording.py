import json
import pytest
from barcode_scanning.recording import RecordingSession
from barcode_scanning.dataset_metadata import read_episode_metadata


def test_new_metadata_has_no_scanner_input(tmp_path):
    session = RecordingSession('poly_mailer', 'top')
    episode = tmp_path / 'demo'
    session.start(episode)
    session.record_frame()
    session.stop()
    metadata = read_episode_metadata(episode)
    assert metadata['schema_version'] == 3
    assert metadata['medium'] == 'poly_mailer'
    assert metadata['label_face'] == 'top'
    assert metadata['frame_count'] == 1
    assert set(metadata) == {'schema_version', 'medium', 'label_face', 'episode_id',
                             'cycle_id', 'started_at', 'ended_at', 'recording_complete',
                             'review_status', 'frame_count', 'control_overruns', 'control_period_ms'}
    with pytest.raises(ValueError):
        session.start(episode)


@pytest.mark.parametrize('medium,face', [('carton','rear'),('envelope','bottom')])
def test_valid_faces(medium, face):
    RecordingSession(medium, face)


def test_invalid_face_rejected():
    with pytest.raises(ValueError):
        RecordingSession('envelope', 'front')


def test_archived_metadata_stays_readable_and_unchanged(tmp_path):
    from pathlib import Path
    original=Path('old_architecture_folder/fixtures/legacy_episode_metadata.json').read_bytes()
    episode=tmp_path/'legacy'; episode.mkdir()
    path=episode/'metadata.json'; path.write_bytes(original)
    loaded=read_episode_metadata(episode)
    assert loaded['legacy_recording']
    assert loaded['medium']=='poly_mailer'
    assert path.read_bytes()==original


def test_legacy_conversion_never_writes_retired_observations(tmp_path):
    from pathlib import Path
    import h5py
    from barcode_scanning.dataset_metadata import write_hdf5_metadata
    metadata=json.loads(Path('old_architecture_folder/fixtures/legacy_episode_metadata.json').read_text())
    with h5py.File(str(tmp_path/'legacy.hdf5'),'w') as f:
        write_hdf5_metadata(f,metadata,1)
        assert set(f.attrs)=={'episode_metadata_json','medium','cycle_id'}
        assert not len(f)
