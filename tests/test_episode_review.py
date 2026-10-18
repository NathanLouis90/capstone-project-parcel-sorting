import json
from pathlib import Path
import pickle

import cv2
import h5py
import numpy as np
import pytest

from barcode_scanning.recording import RecordingSession
from barcode_scanning.dataset_metadata import write_hdf5_metadata
from barcode_scanning.barcode_scanning_config import RECORDING
from scripts import review_episodes as review
from scripts import prepare_act_datasets as prepare
from scripts.scripts_config import SCRIPT_COLLECT2TRAIN


def recording(project, identifier, status='unreviewed'):
    episode = project / 'collect_data' / identifier
    session = RecordingSession('poly_mailer', 'bottom')
    session.start(episode)
    qpos, actions, images = [], [], []
    for i in range(2):
        joints = np.arange(14, dtype=float) / 10 + i / 100
        action = joints + 0.01
        qpos.append(joints)
        actions.append(action)
        folder = episode / 'observation'
        folder.mkdir(exist_ok=True)
        with (folder / '{}.pkl'.format(i)).open('wb') as stream:
            pickle.dump({'joint_positions': joints, 'control': action}, stream)
        for camera, folder in review.CAMERA_FOLDERS:
            directory = episode / folder
            directory.mkdir(exist_ok=True)
            image = np.full((8, 12, 3), [50 + i, 100, 150], dtype=np.uint8)
            assert cv2.imwrite(str(directory / '{}.jpg'.format(i)), image)
        images.append(cv2.imread(str(episode / 'topImg' / '{}.jpg'.format(i))))
        session.record_frame()
    session.metadata['review_status'] = status
    session.stop()
    data = project / 'train_data'
    data.mkdir(exist_ok=True)
    index = len(list(data.glob('*.hdf5')))
    converted = data / 'episode_init_{}.hdf5'.format(index)
    with h5py.File(str(converted), 'w') as source:
        write_hdf5_metadata(source, session.metadata, 2)
        source.attrs['compress'] = True
        source.attrs['jpeg_quality'] = SCRIPT_COLLECT2TRAIN['jpeg_quality']
        source.attrs['mirror_state_multiply'] = SCRIPT_COLLECT2TRAIN['MIRROR_STATE_MULTIPLY']
        source.create_dataset('observations/qpos', data=np.asarray(qpos, dtype=np.float32))
        source.create_dataset('action', data=np.asarray(actions, dtype=np.float32))
        encoded = [cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, source.attrs['jpeg_quality']])[1].ravel()
                   for image in images]
        size = max(len(value) for value in encoded)
        padded = np.zeros((2, size), dtype=np.uint8)
        for i, value in enumerate(encoded):
            padded[i, :len(value)] = value
        for camera, folder in review.CAMERA_FOLDERS:
            source.create_dataset('observations/images/' + camera, data=padded)
    return episode, converted


def statuses(episode, converted):
    raw = review.read_metadata(episode)['review_status']
    with h5py.File(str(converted), 'r') as source:
        saved = json.loads(source.attrs['episode_metadata_json'])['review_status']
    return raw, saved


def payload(path):
    result = {}
    with h5py.File(str(path), 'r') as source:
        source.visititems(lambda key, node: result.update({key: node[:]}) if isinstance(node, h5py.Dataset) else None)
    return result


def test_accept_updates_both_statuses_and_preserves_payload(tmp_path):
    episode, converted = recording(tmp_path / 'project', '001')
    before = payload(converted)
    raw_frame = (episode / 'observation/0.pkl').read_bytes()
    assert review.set_review_status(episode, 'accepted') == 1
    assert statuses(episode, converted) == ('accepted', 'accepted')
    assert raw_frame == (episode / 'observation/0.pkl').read_bytes()
    after = payload(converted)
    assert before.keys() == after.keys()
    for key in before:
        np.testing.assert_array_equal(before[key], after[key])


def test_dry_run_never_changes_files(tmp_path):
    project = tmp_path / 'project'
    episode, converted = recording(project, '001')
    raw_before = (episode / RECORDING['metadata_filename']).read_bytes()
    hdf5_before = converted.read_bytes()
    result = review.review_project(project, status='accepted', dry_run=True)
    assert result['accepted'] == 1
    assert (episode / RECORDING['metadata_filename']).read_bytes() == raw_before
    assert converted.read_bytes() == hdf5_before


@pytest.mark.parametrize('changed', ['action', 'observations/qpos', 'observations/images/top'])
def test_changed_payload_refused_before_raw_status_changes(tmp_path, changed):
    episode, converted = recording(tmp_path / 'project', '001')
    with h5py.File(str(converted), 'r+') as source:
        source[changed][0, 0] += 1
    with pytest.raises(ValueError, match='differs'):
        review.set_review_status(episode, 'accepted')
    assert statuses(episode, converted) == ('unreviewed', 'unreviewed')


def test_batch_preflight_blocks_all_updates_on_mismatch(tmp_path):
    project = tmp_path / 'project'
    first, first_file = recording(project, '001')
    second, second_file = recording(project, '002')
    with h5py.File(str(second_file), 'r+') as source:
        source['action'][0, 0] += 1
    with pytest.raises(ValueError):
        review.review_project(project, status='accepted')
    assert statuses(first, first_file) == ('unreviewed', 'unreviewed')
    assert statuses(second, second_file) == ('unreviewed', 'unreviewed')


def test_batch_defaults_keep_prior_rejection(tmp_path):
    project = tmp_path / 'project'
    pending, pending_file = recording(project, '001')
    rejected, rejected_file = recording(project, '002', 'rejected')
    result = review.review_project(project, status='accepted')
    assert result['accepted'] == 1
    assert statuses(pending, pending_file) == ('accepted', 'accepted')
    assert statuses(rejected, rejected_file) == ('rejected', 'rejected')


def test_only_rejected_cli_accepts_rejections_and_keeps_other_files(tmp_path, monkeypatch, capsys):
    project = tmp_path / 'project'
    accepted = recording(project, '001', 'accepted')
    pending = recording(project, '002')
    rejected = recording(project, '003', 'rejected')
    untouched = [(episode / RECORDING['metadata_filename'], converted)
                 for episode, converted in (accepted, pending)]
    before = {path: path.read_bytes() for pair in untouched for path in pair}
    seen = []
    monkeypatch.setattr(review, 'play_episode',
                        lambda episode, metadata: seen.append(episode.name) or 'accepted')
    assert review.main(['--project', str(project), '--only-rejected']) == 0
    assert seen == ['003']
    assert statuses(*rejected) == ('accepted', 'accepted')
    assert all(path.read_bytes() == content for path, content in before.items())
    # Running again excludes the recording just accepted and opens no window.
    assert review.main(['--project', str(project), '--only-rejected']) == 0
    assert seen == ['003']
    assert 'No rejected episodes selected.' in capsys.readouterr().out


def test_only_rejected_intersects_explicit_episode_selection(tmp_path):
    project = tmp_path / 'project'
    recording(project, '001', 'accepted')
    selected = recording(project, '002', 'rejected')
    excluded = recording(project, '003', 'rejected')
    seen = []
    review.review_project(project, episode_ids=['001', '002'], only_rejected=True,
                          decision_fn=lambda episode, metadata: seen.append(episode.name) or 'accepted')
    assert seen == ['002']
    assert statuses(*selected) == ('accepted', 'accepted')
    assert statuses(*excluded) == ('rejected', 'rejected')


def test_only_rejected_conflicts_with_include_reviewed(tmp_path):
    with pytest.raises(SystemExit) as error:
        review.main(['--project', str(tmp_path), '--only-rejected', '--include-reviewed'])
    assert error.value.code == 2


def test_sync_uses_existing_decision_without_modifying_raw_file(tmp_path):
    project = tmp_path / 'project'
    episode, converted = recording(project, '001')
    path = episode / RECORDING['metadata_filename']
    metadata = json.loads(path.read_text())
    metadata['review_status'] = 'accepted'
    path.write_text(json.dumps(metadata))
    original = path.read_bytes()
    result = review.review_project(project, sync=True)
    assert result['accepted'] == 1
    assert statuses(episode, converted) == ('accepted', 'accepted')
    assert path.read_bytes() == original


def test_individual_prepare_command_also_syncs_existing_hdf5(tmp_path):
    episode, converted = recording(tmp_path / 'project', '001')
    assert prepare.main(['--review-episode', str(episode), '--review-status', 'accepted']) == 0
    assert statuses(episode, converted) == ('accepted', 'accepted')


def test_interactive_skip_quit_and_resume(tmp_path):
    project = tmp_path / 'project'
    entries = [recording(project, str(i)) for i in range(3)]
    decisions = iter(['accepted', 'skip', 'quit'])
    result = review.review_project(project, decision_fn=lambda *args: next(decisions))
    assert result['accepted'] == 1
    assert result['skipped'] == 1
    assert result['remaining_unreviewed'] == 2
    seen = []
    review.review_project(project, decision_fn=lambda episode, metadata: seen.append(episode.name) or 'rejected')
    assert seen == ['1', '2']
    assert statuses(*entries[0]) == ('accepted', 'accepted')




def test_rejection_can_exclude_an_incomplete_episode(tmp_path):
    episode, converted = recording(tmp_path / 'project', '001')
    path = episode / RECORDING['metadata_filename']
    metadata = json.loads(path.read_text())
    metadata['recording_complete'] = False
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match='interrupted'):
        review.set_review_status(episode, 'accepted')
    review.set_review_status(episode, 'rejected')
    assert statuses(episode, converted) == ('rejected', 'rejected')


def test_playback_controls_and_rate():
    assert review.key_decision(ord('a')) == 'accepted'
    assert review.key_decision(ord('R')) == 'rejected'
    assert review.key_decision(ord('q')) == 'quit'
    assert review.key_decision(-1) is None
    assert review.frame_delay_ms({'frame_count': 25, 'started_at': 0, 'ended_at': 1}) == 40


def test_gui_review_decision_and_cleanup_without_opening_window(tmp_path, monkeypatch):
    episode, converted = recording(tmp_path / 'project', '001')
    monkeypatch.setenv('DISPLAY', ':fake-test-display')
    commands = iter([ord(' '), ord('p'), ord('a')])
    displayed, closed = [], []
    monkeypatch.setattr(review.cv2, 'imshow', lambda name, frame: displayed.append(frame.shape))
    monkeypatch.setattr(review.cv2, 'waitKey', lambda delay: next(commands))
    monkeypatch.setattr(review.cv2, 'getWindowProperty', lambda *args: 1)
    monkeypatch.setattr(review.cv2, 'destroyAllWindows', lambda: closed.append(True))
    assert review.play_episode(episode, review.read_metadata(episode)) == 'accepted'
    assert displayed and closed == [True]
    assert statuses(episode, converted) == ('unreviewed', 'unreviewed')


def test_sync_unchanged_status_does_not_rewrite_hdf5(tmp_path):
    project = tmp_path / 'project'
    episode, converted = recording(project, '001')
    before = converted.read_bytes()
    review.review_project(project, sync=True)
    assert converted.read_bytes() == before


def test_interactive_error_leaves_episode_unreviewed(tmp_path):
    project = tmp_path / 'project'
    episode, converted = recording(project, '001')
    with h5py.File(str(converted), 'r+') as source:
        source['action'][0, 0] += 1
    result = review.review_project(project, decision_fn=lambda *args: 'accepted')
    assert result['errors'] == 1
    assert statuses(episode, converted) == ('unreviewed', 'unreviewed')
