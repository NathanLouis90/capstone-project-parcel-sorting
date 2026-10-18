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
