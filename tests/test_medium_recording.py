import json
from pathlib import Path
import h5py
import pytest
from barcode_scanning.recording import RecordingSession
from barcode_scanning.dataset_metadata import read_episode_metadata, write_hdf5_metadata
from barcode_scanning.barcode_scanning_config import RECORDING
from experiments.experiments_config import MEDIA


@pytest.mark.parametrize('medium,face', [
    (medium, face) for medium, settings in MEDIA.items() for face in settings['label_faces']
])
def test_recorder_uses_registered_medium_face_project(tmp_path, monkeypatch, medium, face):
    from experiments import run_control
    from scripts.scripts_config import PREPARE_ACT_DATASETS
    from ModelTrain.constants import TASK_CONFIGS

    captured = []
    monkeypatch.setattr(run_control, '_run_control', lambda args, session: captured.append(
        (args.project_name, session.medium, session.label_face)))
    args = run_control.Args(medium=medium, label_face=face, save_data_path=str(tmp_path))
    run_control.main(args)
    name = '{}_{}'.format(medium, face)
    assert captured == [(name, medium, face)]
    assert not list(tmp_path.iterdir())
    assert PREPARE_ACT_DATASETS['projects'][name]['medium'] == medium
    assert PREPARE_ACT_DATASETS['projects'][name]['label_face'] == face
    task = TASK_CONFIGS[name]
    assert task['medium'] == medium
    assert task['dataset_dir'] == str(
        Path(PREPARE_ACT_DATASETS['root_dir']) / name / 'train_data')


@pytest.mark.parametrize('override', [None, 'poly_mailer_session2'])
def test_recorder_dry_run_path_and_custom_project(tmp_path, override):
    from experiments import run_control

    args = run_control.Args(medium='poly_mailer', label_face='bottom',
                            save_data_path=str(tmp_path), project_name=override, dry_run=True)
    run_control.main(args)
    project = override or 'poly_mailer_bottom'
    assert [path.name for path in tmp_path.iterdir()] == [project]
    episodes = list((tmp_path / project / 'collect_data').iterdir())
    assert len(episodes) == 1
    metadata = read_episode_metadata(episodes[0])
    assert metadata['medium'] == 'poly_mailer'
    assert metadata['label_face'] == 'bottom'


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


@pytest.fixture
def completed_episode(tmp_path):
    episode = tmp_path / 'demo'
    session = RecordingSession('poly_mailer', 'bottom')
    session.start(episode)
    session.record_frame()
    session.stop()
    return episode


@pytest.mark.parametrize('schema', [None, 1, 2, 4, '3', True, 3.0])
def test_unsupported_schema_refused_without_rewriting(completed_episode, schema):
    path = completed_episode / RECORDING['metadata_filename']
    metadata = json.loads(path.read_text())
    metadata['schema_version'] = schema
    path.write_text(json.dumps(metadata))
    original = path.read_bytes()
    with pytest.raises(ValueError, match='schema 3'):
        read_episode_metadata(completed_episode)
    assert path.read_bytes() == original


def test_required_metadata_filename_has_no_fallback(completed_episode):
    path = completed_episode / RECORDING['metadata_filename']
    other = completed_episode / 'metadata.json'
    path.rename(other)
    original = other.read_bytes()
    with pytest.raises(ValueError, match='episode_metadata.json'):
        read_episode_metadata(completed_episode)
    assert not path.exists()
    assert other.read_bytes() == original


@pytest.mark.parametrize('value', [None, []])
def test_nonobject_metadata_rejected(completed_episode, value):
    (completed_episode / RECORDING['metadata_filename']).write_text(json.dumps(value))
    with pytest.raises(ValueError, match='schema 3'):
        read_episode_metadata(completed_episode)


@pytest.mark.parametrize('period', [None, 0, True, '40'])
def test_recording_requires_valid_control_period(completed_episode, period):
    path = completed_episode / RECORDING['metadata_filename']
    metadata = json.loads(path.read_text())
    metadata['control_period_ms'] = period
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match='control_period_ms'):
        read_episode_metadata(completed_episode)


def test_hdf5_provenance_excludes_scanner_observations(completed_episode, tmp_path):
    metadata = read_episode_metadata(completed_episode)
    with h5py.File(str(tmp_path / 'current.hdf5'), 'w') as output:
        write_hdf5_metadata(output, dict(metadata, scan={'barcode': 'DEST-A-S138683'}))
        assert json.loads(output.attrs['episode_metadata_json']) == metadata
        assert set(output.attrs) == {'episode_metadata_json', 'medium', 'label_face', 'cycle_id'}
        assert not len(output)


@pytest.mark.parametrize('schema', [None, 2, 4])
def test_hdf5_rejects_unsupported_schema_before_writing(tmp_path, schema):
    with h5py.File(str(tmp_path / 'invalid.hdf5'), 'w') as output:
        with pytest.raises(ValueError, match='schema 3'):
            write_hdf5_metadata(output, {'schema_version': schema})
        assert not len(output.attrs)
