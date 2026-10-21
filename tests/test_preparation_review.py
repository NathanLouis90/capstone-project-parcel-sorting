import json
import pickle
from types import SimpleNamespace
import numpy as np
import pytest
from barcode_scanning.recording import RecordingSession
from barcode_scanning.barcode_scanning_config import RECORDING
from scripts import prepare_act_datasets as prepare
from scripts.scripts_config import MANIPULATE_UTILS


def raw_episode(root, name, status):
    path = root / 'poly_mailer' / 'collect_data' / name
    session = RecordingSession('poly_mailer', 'bottom')
    session.start(path)
    home = np.concatenate([np.deg2rad(MANIPULATE_UTILS['stage2_left_deg']),
                           np.deg2rad(MANIPULATE_UTILS['stage2_right_deg'])])
    home[[6, 13]] = 1
    for folder, extension in [('observation', '.pkl'), ('topImg', '.jpg'),
                              ('leftImg', '.jpg'), ('rightImg', '.jpg')]:
        directory = path / folder
        directory.mkdir()
        frame = directory / ('0' + extension)
        if folder == 'observation':
            with frame.open('wb') as stream:
                pickle.dump({'joint_positions': home}, stream)
        else:
            frame.write_bytes(b'review-test')
    session.record_frame()
    session.metadata['review_status'] = status
    session.stop()
    return path


def test_conversion_skips_every_status_except_accepted(tmp_path, monkeypatch):
    for name, status in [('01', 'unreviewed'), ('02', 'rejected'), ('03', 'accepted')]:
        raw_episode(tmp_path, name, status)
    monkeypatch.setattr(prepare, 'PROJECTS', {'poly_mailer': dict(schema_version=3, medium='poly_mailer',
                                                     episode_len=400)})
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(prepare.subprocess, 'run', run)
    assert prepare.main(['--root', str(tmp_path), '--convert']) == 0
    assert len(calls) == 1
    assert calls[0][calls[0].index('--date_collect') + 1] == '03'


def test_review_status_persists_without_changing_frames(tmp_path):
    episode = raw_episode(tmp_path, '01', 'unreviewed')
    frame = episode / 'observation/0.pkl'
    original = frame.read_bytes()
    assert prepare.main(['--review-episode', str(episode), '--review-status', 'accepted']) == 0
    assert json.loads((episode / RECORDING['metadata_filename']).read_text())['review_status'] == 'accepted'
    assert frame.read_bytes() == original


def test_rejected_incomplete_episode_skipped(tmp_path, monkeypatch):
    episode = raw_episode(tmp_path, '01', 'rejected')
    metadata_path = episode / RECORDING['metadata_filename']
    metadata = json.loads(metadata_path.read_text())
    metadata['recording_complete'] = False
    metadata_path.write_text(json.dumps(metadata))
    monkeypatch.setattr(prepare, 'PROJECTS', {'poly_mailer': dict(schema_version=3, medium='poly_mailer',
                                                     episode_len=400)})
    assert prepare.main(['--root', str(tmp_path), '--convert']) == 0


@pytest.mark.parametrize('face', ['top', 'bottom'])
def test_prepare_face_project_checks_metadata(tmp_path, monkeypatch, face):
    episode = raw_episode(tmp_path, '01', 'accepted')
    destination = tmp_path / 'poly_mailer_bottom'
    episode.parent.parent.rename(destination)
    path = destination / 'collect_data' / '01' / RECORDING['metadata_filename']
    metadata = json.loads(path.read_text())
    metadata['label_face'] = face
    path.write_text(json.dumps(metadata))
    calls = []
    monkeypatch.setattr(prepare.subprocess, 'run', lambda command, **kwargs: (
        calls.append(command) or SimpleNamespace(returncode=0)))
    command = ['--root', str(tmp_path), '--dataset-name', 'poly_mailer_bottom', '--convert']
    if face == 'top':
        with pytest.raises(SystemExit):
            prepare.main(command)
        assert not calls
    else:
        assert prepare.main(command) == 0
        assert len(calls) == 1
        assert calls[0][calls[0].index('--dataset_name') + 1] == 'poly_mailer_bottom'


def test_direct_converter_refuses_wrong_face_before_writing(tmp_path):
    from click.testing import CliRunner
    from scripts import script_collect2train as converter

    episode = raw_episode(tmp_path, '01', 'accepted')
    destination = tmp_path / 'poly_mailer_top'
    episode.parent.parent.rename(destination)
    result = CliRunner().invoke(converter.main, ['--root_dir', str(tmp_path),
                               '--dataset_name', 'poly_mailer_top', '--date_collect', '01', '--idx', '0'])
    assert isinstance(result.exception, ValueError)
    assert 'label_face mismatch' in str(result.exception)
    assert not (destination / 'train_data').exists()
    assert not (destination / 'output_videos').exists()


@pytest.mark.parametrize('metadata_present', [False, True])
def test_direct_converter_rejects_missing_or_unsupported_metadata(tmp_path, monkeypatch, metadata_present):
    from click.testing import CliRunner
    from scripts import script_collect2train as converter
    episode = raw_episode(tmp_path, '01', 'accepted')
    path = episode / RECORDING['metadata_filename']
    if metadata_present:
        metadata = json.loads(path.read_text())
        metadata['schema_version'] = 2
        path.write_text(json.dumps(metadata))
    else:
        path.unlink()
    monkeypatch.setattr(converter, 'load_data', lambda *args: pytest.fail('Invalid metadata must fail before loading frames'))
    result = CliRunner().invoke(converter.main, ['--root_dir', str(tmp_path),
                               '--dataset_name', 'poly_mailer', '--date_collect', '01', '--idx', '0'])
    assert isinstance(result.exception, ValueError)
    assert not (tmp_path / 'poly_mailer/train_data').exists()
    assert not (tmp_path / 'poly_mailer/output_videos').exists()
