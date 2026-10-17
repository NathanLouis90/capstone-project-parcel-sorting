"""Synthetic files only: curation must never open robot or camera interfaces."""
import json
from pathlib import Path
import pickle

import h5py
import numpy as np
import pytest

from scripts import curate_datasets as curate
from scripts import prepare_act_datasets as prepare
from scripts.dataset_integrity import require_fresh, require_training_folders
from scripts.count_episodes import count_project
from scripts.scripts_config import MANIPULATE_UTILS


def config(stage='A', medium='poly_mailer', bin_index=None, length=400):
    return dict(policy_stage=stage, medium=medium, bin_index=bin_index,
                episode_len=length, camera_names=list(curate.CAMERAS), control_period_ms=40)


def episode(root, project, identifier, status='accepted', stage='A', medium='poly_mailer',
            bin_index=None, frames=1, period=40, source=None, started=None):
    path = root / project / 'collect_data' / identifier
    path.mkdir(parents=True)
    home = np.concatenate([np.deg2rad(MANIPULATE_UTILS['stage2_left_deg']),
                           np.deg2rad(MANIPULATE_UTILS['stage2_right_deg'])])
    home[[6, 13]] = 1
    m = dict(episode_id=identifier, cycle_id='cycle-' + identifier, recording_complete=True,
             frame_count=frames, review_status=status, policy_stage=stage, medium=medium,
             capture_barcode=False, scan=None, scanner_error=None,
             started_at=float(identifier) if started is None else started,
             ended_at=(float(identifier) if started is None else started) + frames * .04,
             control_period_ms=period, demonstrated_bin=bin_index,
             destination=None if bin_index is None else dict(bin_index=bin_index, source='manual'))
    if source:
        m['source'] = source
    (path / 'episode_metadata.json').write_text(json.dumps(m))
    for folder in ('observation', 'topImg', 'leftImg', 'rightImg'):
        (path / folder).mkdir()
        for i in range(frames):
            target = path / folder / (str(i) + ('.pkl' if folder == 'observation' else '.jpg'))
            target.write_bytes(pickle.dumps(dict(joint_positions=home)) if folder == 'observation' else b'synthetic-image')
    return path


def project(root, name):
    (root / name / 'collect_data').mkdir(parents=True, exist_ok=True)


def plan(root, command, registry):
    return curate.build_plan(curate.parser().parse_args(['--root', str(root)] + command), registry)


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None for p in root.rglob('*')}


def artifact(path, index=0):
    project = path.parent.parent
    (project / 'train_data').mkdir(exist_ok=True)
    hdf5 = project / 'train_data' / 'episode_init_{}.hdf5'.format(index)
    with h5py.File(str(hdf5), 'w') as output:
        output.attrs['episode_metadata_json'] = json.dumps(curate.metadata(path))
    video = project / 'output_videos' / (path.name + '_video.mp4')
    video.parent.mkdir(exist_ok=True)
    video.write_bytes(b'synthetic-video')
    return hdf5, video


def test_quarantine_restore_preserves_content_status_and_converted_names(tmp_path):
    e = episode(tmp_path, 'A', '1', 'rejected')
    episode(tmp_path, 'A', '2')
    hdf5, video = artifact(e, 17)
    original = curate.hashes(e)
    converted_hash = curate.hashes(hdf5)
    p = plan(tmp_path, ['quarantine', '--project', 'A'], {})
    curate.execute(p, yes=True)
    q = tmp_path / 'A/rejected_data/1'
    assert curate.hashes(q) == original
    assert not hdf5.exists() and not video.exists()
    assert (tmp_path / 'A/rejected_data/converted/train_data' / hdf5.name).exists()
    assert count_project(tmp_path / 'A/collect_data')[1]['total'] == 1
    status = curate.project_status(tmp_path / 'A')
    assert status['counts']['quarantined'] == 1 and status['train_data_stale']
    curate.execute(plan(tmp_path, ['restore', '--project', 'A', '--episodes', '1'], {}), yes=True)
    assert curate.hashes(e) == original and curate.hashes(hdf5) == converted_hash
    assert curate.metadata(e)['review_status'] == 'rejected'
    records = [json.loads(line) for line in (tmp_path / 'A/curation_log.jsonl').read_text().splitlines()]
    assert len(records) == 2
    assert records[0]['operations'][0]['sha256'] == original


def test_worked_example_24_plus_rejected_top_up_to_25(tmp_path):
    for i in range(1, 25):
        episode(tmp_path, 'A', str(i))
    episode(tmp_path, 'A', '25', 'rejected')
    for i in range(30, 35):
        episode(tmp_path, 'B', str(i))
    registry = dict(A=config(), B=config())
    curate.execute(plan(tmp_path, ['quarantine', '--project', 'A'], registry), yes=True)
    p = plan(tmp_path, ['top-up', '--from', 'B', '--to', 'A', '--target', '25'], registry)
    assert [op.source.name for op in p.operations] == ['30']
    curate.execute(p, yes=True)
    assert len(curate.accepted(tmp_path / 'A')) == 25
    assert len(curate.accepted(tmp_path / 'B')) == 4
    assert (tmp_path / 'A/rejected_data/25').exists()


def test_transfer_oldest_timestamp_not_folder_sort(tmp_path):
    episode(tmp_path, 'B', '1', started=100)
    oldest = episode(tmp_path, 'B', '2', started=10)
    project(tmp_path, 'A')
    p = plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--count', '1'], dict(A=config(), B=config()))
    assert p.operations[0].source == oldest
    raw = curate.hashes(oldest)
    curate.execute(p, yes=True)
    assert curate.hashes(tmp_path / 'A/collect_data/2') == raw
    for name in ('A', 'B'):
        with pytest.raises(ValueError, match='Stale train_data'):
            require_fresh(tmp_path / name)


@pytest.mark.parametrize('move', [False, True])
def test_merge_copy_and_move(tmp_path, move):
    a = episode(tmp_path, 'A', '1')
    b = episode(tmp_path, 'B', '2')
    registry = {name: config() for name in ('A', 'B', 'NEW')}
    command = ['merge', '--from', 'A', 'B', '--to', 'NEW'] + (['--move'] if move else [])
    p = plan(tmp_path, command, registry)
    curate.execute(p, yes=True)
    assert len(curate.accepted(tmp_path / 'NEW')) == 2
    assert a.exists() == (not move) and b.exists() == (not move)
    assert (tmp_path / 'A/train_data/STALE.json').exists() == move
    assert (tmp_path / 'A/curation_log.jsonl').exists()


@pytest.mark.parametrize('status', ['rejected', 'unreviewed'])
def test_explicit_transfer_refuses_nonaccepted(tmp_path, status):
    episode(tmp_path, 'B', '1', status)
    project(tmp_path, 'A')
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='requires accepted'):
        plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--episodes', '1'], dict(A=config(), B=config()))
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('field,value', [
    ('policy_stage', 'B'), ('medium', 'carton'), ('bin_index', 1),
    ('camera_names', ['top']), ('control_period_ms', 20), ('episode_len', 0),
])
def test_incompatible_destination_names_field_without_moves(tmp_path, field, value):
    episode(tmp_path, 'B', '1')
    project(tmp_path, 'A')
    destination = config()
    destination[field] = value
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match=field):
        plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--count', '1'], dict(A=destination, B=config()))
    assert snapshot(tmp_path) == before


def test_id_collision_and_partial_frame_refused(tmp_path):
    e = episode(tmp_path, 'B', '1')
    episode(tmp_path, 'A', '1')
    registry = dict(A=config(), B=config())
    with pytest.raises(ValueError, match='collision'):
        plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--count', '1'], registry)
    (e / 'topImg/0.jpg').unlink()
    with pytest.raises(ValueError, match='camera set'):
        plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--count', '1'], registry)


def test_rollout_requires_both_flag_and_explicit_project(tmp_path):
    episode(tmp_path, 'B', '1', source='rollout')
    for name in ('A', 'rollout_A'):
        project(tmp_path, name)
    registry = {name: config() for name in ('A', 'B', 'rollout_A')}
    for target, flag in [('A', []), ('A', ['--allow-rollouts']), ('rollout_A', [])]:
        with pytest.raises(ValueError, match='Rollout requires'):
            plan(tmp_path, ['transfer', '--from', 'B', '--to', target, '--count', '1'] + flag, registry)
    p = plan(tmp_path, ['transfer', '--from', 'B', '--to', 'rollout_A', '--count', '1', '--allow-rollouts'], registry)
    assert len(p.operations) == 1


def test_dry_run_and_declined_confirmation_change_nothing(tmp_path):
    episode(tmp_path, 'B', '1')
    project(tmp_path, 'A')
    p = plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--count', '1'], dict(A=config(), B=config()))
    before = snapshot(tmp_path)
    assert not curate.execute(p, dry_run=True)
    assert snapshot(tmp_path) == before
    assert not curate.execute(p, input_fn=lambda _: 'no')
    assert snapshot(tmp_path) == before


def test_full_plan_preflight_and_runtime_rollback(tmp_path, monkeypatch):
    episode(tmp_path, 'B', '1')
    episode(tmp_path, 'B', '2')
    project(tmp_path, 'A')
    registry = dict(A=config(), B=config())
    p = plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--count', '2'], registry)
    before = snapshot(tmp_path)
    rename = curate.os.rename
    count = []

    def fail_second(source, destination):
        count.append(source)
        if len(count) == 2:
            raise OSError('synthetic rename error')
        rename(source, destination)

    monkeypatch.setattr(curate.os, 'rename', fail_second)
    with pytest.raises(OSError, match='synthetic rename error'):
        curate.execute(p, yes=True)
    assert snapshot(tmp_path) == before


def test_source_changes_after_plan_refused(tmp_path):
    e = episode(tmp_path, 'B', '1')
    project(tmp_path, 'A')
    p = plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--count', '1'], dict(A=config(), B=config()))
    (e / 'topImg/0.jpg').write_bytes(b'changed')
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='Source changed'):
        curate.execute(p, yes=True)
    assert snapshot(tmp_path) == before


def test_stale_blocks_preparation_training_and_robomimic(tmp_path, monkeypatch):
    episode(tmp_path, 'A', '1')
    marker = tmp_path / 'A/train_data/STALE.json'
    marker.parent.mkdir()
    marker.write_text('{}')
    monkeypatch.setattr(prepare, 'PROJECTS', dict(A=config()))
    with pytest.raises(SystemExit):
        prepare.main(['--root', str(tmp_path), '--dataset-name', 'A', '--convert'])
    with pytest.raises(ValueError, match='Stale train_data'):
        require_training_folders([tmp_path / 'A/train_data'])
    from scripts.convert_to_robomimic import inspect_sources
    with pytest.raises(ValueError, match='Stale train_data'):
        inspect_sources([tmp_path / 'A'], dict(stage='A', medium='poly_mailer', bin=None))


def test_fresh_rebuild_copies_only_accepted_and_leaves_source_untouched(tmp_path, monkeypatch):
    e = episode(tmp_path, 'A', '1')
    episode(tmp_path, 'A', '2', 'rejected')
    marker = tmp_path / 'A/train_data/STALE.json'
    marker.parent.mkdir()
    marker.write_text('{}')
    monkeypatch.setattr(prepare, 'PROJECTS', dict(A=config(), NEW=config()))
    before = snapshot(tmp_path / 'A')
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(prepare.subprocess, 'run', run)
    assert prepare.main(['--root', str(tmp_path), '--dataset-name', 'A', '--rebuild-to', 'NEW', '--convert']) == 0
    assert len(calls) == 1
    assert curate.hashes(tmp_path / 'NEW/collect_data/1') == curate.hashes(e)
    assert not (tmp_path / 'NEW/collect_data/2').exists()
    assert snapshot(tmp_path / 'A') == before
    assert not (tmp_path / 'NEW/train_data/BUILDING.json').exists()


def test_legacy_rate_warning_and_renamed_episode_refusal(tmp_path):
    e = episode(tmp_path, 'B', '1')
    m = curate.metadata(e)
    del m['control_period_ms']
    (e / 'episode_metadata.json').write_text(json.dumps(m))
    project(tmp_path, 'A')
    registry = dict(A=config(), B=config())
    p = plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--count', '1'], registry)
    assert any('legacy metadata' in warning for warning in p.warnings)
    e.rename(e.with_name('1_update_policy'))
    with pytest.raises(ValueError, match='episode_id differs'):
        plan(tmp_path, ['transfer', '--from', 'B', '--to', 'A', '--count', '1'], registry)


def test_quarantined_folders_excluded_from_review_and_conversion(tmp_path):
    e = episode(tmp_path, 'A', '1', 'rejected')
    curate.execute(plan(tmp_path, ['quarantine', '--project', 'A'], {}), yes=True)
    from scripts.review_episodes import review_project
    assert review_project(tmp_path / 'A', dry_run=True)['accepted'] == 0
    assert count_project(tmp_path / 'A/collect_data')[1]['total'] == 0
    assert not e.exists()


@pytest.mark.parametrize('stage,bin_index', [('A', None), ('B', 1)])
def test_real_fresh_conversion_and_review_round_trip(tmp_path, monkeypatch, stage, bin_index):
    import cv2
    episode(tmp_path, 'A', '1', 'rejected', stage=stage, bin_index=bin_index)
    e = episode(tmp_path, 'A', '2', stage=stage, bin_index=bin_index, frames=2)
    for p in (e / 'observation').glob('*.pkl'):
        obs = pickle.loads(p.read_bytes())
        obs.update(control=obs['joint_positions'].copy(), joint_velocities=np.zeros(14))
        p.write_bytes(pickle.dumps(obs))
    for folder in curate.CAMERAS.values():
        for p in (e / folder).glob('*.jpg'):
            assert cv2.imwrite(str(p), np.full((480, 640, 3), 80, dtype=np.uint8))
    stale = tmp_path / 'A/train_data/STALE.json'
    stale.parent.mkdir()
    stale.write_text('{}')
    cfg = config(stage=stage, bin_index=bin_index)
    monkeypatch.setattr(prepare, 'PROJECTS', dict(A=cfg, NEW=cfg))
    assert prepare.main(['--root', str(tmp_path), '--dataset-name', 'A', '--rebuild-to', 'NEW', '--convert']) == 0
    hdf5 = tmp_path / 'NEW/train_data/episode_init_0.hdf5'
    assert list(hdf5.parent.glob('*.hdf5')) == [hdf5]
    with h5py.File(str(hdf5), 'r') as converted:
        assert converted['action'].shape == (2, 14)
        assert json.loads(converted.attrs['episode_metadata_json']) == curate.metadata(e)
        if stage == 'B':
            np.testing.assert_array_equal(converted['observations/destination'][:], [[0, 1], [0, 1]])
    video = tmp_path / 'NEW/output_videos/2_video.mp4'
    assert video.is_file() and video.stat().st_size > 0
    from scripts.review_episodes import set_review_status
    assert set_review_status(tmp_path / 'NEW/collect_data/2', 'accepted', dry_run=True) == 1


def test_insufficient_accepted_and_wrong_quarantine_fail_without_changes(tmp_path):
    episode(tmp_path, 'A', '1')
    project(tmp_path, 'B')
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='Not enough accepted'):
        plan(tmp_path, ['top-up', '--to', 'B', '--from', 'A', '--target', '2'], dict(A=config(), B=config()))
    with pytest.raises(ValueError, match='requires rejected'):
        plan(tmp_path, ['quarantine', '--project', 'A', '--episodes', '1'], {})
    assert snapshot(tmp_path) == before


def test_symlink_and_cross_filesystem_moves_refused(tmp_path, monkeypatch):
    e = episode(tmp_path, 'A', '1')
    p = curate.Plan('test')
    (e / 'link').symlink_to(e / 'episode_metadata.json')
    with pytest.raises(ValueError, match='Symlink'):
        p.add(e, tmp_path / 'B/collect_data/1')
    (e / 'link').unlink()
    from types import SimpleNamespace
    monkeypatch.setattr(curate, 'nearest_parent', lambda _: SimpleNamespace(stat=lambda: SimpleNamespace(st_dev=-1)))
    with pytest.raises(ValueError, match='Cross-filesystem'):
        p.add(e, tmp_path / 'B/collect_data/1')


def test_b_bin_mismatch_and_source_metadata_links_preserved(tmp_path):
    a = episode(tmp_path, 'source_A', '1')
    b = episode(tmp_path, 'source_B', '2', stage='B', bin_index=0)
    m = curate.metadata(b)
    m['source_metadata_path'] = str(a / 'episode_metadata.json')
    (b / 'episode_metadata.json').write_text(json.dumps(m))
    project(tmp_path, 'target_A')
    project(tmp_path, 'target_B')
    registry = dict(source_A=config(), target_A=config(), source_B=config('B', bin_index=0),
                    target_B=config('B', bin_index=1))
    with pytest.raises(ValueError, match='bin_index mismatch'):
        plan(tmp_path, ['transfer', '--from', 'source_B', '--to', 'target_B', '--count', '1'], registry)
    original = (b / 'episode_metadata.json').read_bytes()
    p = plan(tmp_path, ['transfer', '--from', 'source_A', '--to', 'target_A', '--count', '1'], registry)
    assert any('Link is preserved' in warning for warning in p.warnings)
    curate.execute(p, yes=True)
    assert (b / 'episode_metadata.json').read_bytes() == original


def test_frozen_dataset_and_split_warn_but_never_change(tmp_path):
    e = episode(tmp_path, 'A', '1')
    artifact(e)
    project(tmp_path, 'B')
    frozen = tmp_path / 'training'
    frozen.mkdir()
    split = frozen / 'split.json'
    split.write_text(json.dumps(dict(sources=[dict(id='A/episode_init_0.hdf5')])))
    dataset = frozen / 'dataset.hdf5'
    with h5py.File(str(dataset), 'w') as output:
        demo = output.create_group('data/demo_0')
        demo.attrs['episode_metadata_json'] = json.dumps(curate.metadata(e))
    before = snapshot(frozen)
    p = plan(tmp_path, ['transfer', '--from', 'A', '--to', 'B', '--count', '1'], dict(A=config(), B=config()))
    assert any('Frozen dataset/split/config' in warning for warning in p.warnings)
    assert any('robomimic dataset' in warning for warning in p.warnings)
    curate.execute(p, yes=True)
    assert snapshot(frozen) == before


def test_failed_fresh_conversion_keeps_training_blocked(tmp_path, monkeypatch):
    episode(tmp_path, 'A', '1')
    monkeypatch.setattr(prepare, 'PROJECTS', dict(A=config(), NEW=config()))
    from types import SimpleNamespace
    monkeypatch.setattr(prepare.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=1))
    assert prepare.main(['--root', str(tmp_path), '--dataset-name', 'A', '--rebuild-to', 'NEW', '--convert']) == 1
    assert (tmp_path / 'NEW/train_data/BUILDING.json').exists()
    with pytest.raises(ValueError, match='BUILDING.json'):
        require_training_folders(tmp_path / 'NEW/train_data')


def test_rollback_preserves_prior_audit_and_stale_marker(tmp_path, monkeypatch):
    episode(tmp_path, 'A', '1')
    episode(tmp_path, 'A', '2')
    project(tmp_path, 'B')
    registry = dict(A=config(), B=config())
    curate.execute(plan(tmp_path, ['transfer', '--from', 'A', '--to', 'B', '--count', '1'], registry), yes=True)
    p = plan(tmp_path, ['transfer', '--from', 'A', '--to', 'B', '--count', '1'], registry)
    before = snapshot(tmp_path)
    original = Path.write_text

    def fail_marker(path, *args, **kwargs):
        if path.name == 'STALE.json':
            raise OSError('synthetic marker failure')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', fail_marker)
    with pytest.raises(OSError, match='synthetic marker failure'):
        curate.execute(p, yes=True)
    assert snapshot(tmp_path) == before
