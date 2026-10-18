import json
import pickle
from types import SimpleNamespace
import numpy as np
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
