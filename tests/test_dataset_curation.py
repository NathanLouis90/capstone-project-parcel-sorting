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


def config(medium='poly_mailer', length=400):
    return dict(schema_version=3, medium=medium,
                episode_len=length, camera_names=list(curate.CAMERAS), control_period_ms=40)


def test_transfer_respects_face_project_constraints(tmp_path):
    source = episode(tmp_path, 'poly_mailer_bottom', '1')
    registry = {
        'poly_mailer_bottom': dict(config(), label_face='bottom'),
        'poly_mailer_top': dict(config(), label_face='top'),
        'poly_mailer': config(),
    }
    with pytest.raises(ValueError, match='label_face mismatch'):
        curate.add_transfer(curate.Plan('copy'), [source], tmp_path / 'poly_mailer_top', registry, copy=True)
    plan = curate.Plan('copy')
    curate.add_transfer(plan, [source], tmp_path / 'poly_mailer', registry, copy=True)
    assert len(plan.operations) == 1
    assert source.exists()


def episode(root, project, identifier, status='accepted', medium='poly_mailer',
            frames=1, period=40, source=None, started=None):
    path = root / project / 'collect_data' / identifier
    path.mkdir(parents=True)
    home = np.concatenate([np.deg2rad(MANIPULATE_UTILS['stage2_left_deg']),
                           np.deg2rad(MANIPULATE_UTILS['stage2_right_deg'])])
    home[[6, 13]] = 1
    m = dict(episode_id=identifier, cycle_id='cycle-' + identifier, recording_complete=True,
             frame_count=frames, review_status=status, schema_version=3, medium=medium, label_face='bottom',
             started_at=float(identifier) if started is None else started,
             ended_at=(float(identifier) if started is None else started) + frames * .04,
             control_period_ms=period)
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
    e = episode(tmp_path, 'primary', '1', 'rejected')
    episode(tmp_path, 'primary', '2')
    hdf5, video = artifact(e, 17)
    original = curate.hashes(e)
    converted_hash = curate.hashes(hdf5)
    p = plan(tmp_path, ['quarantine', '--project', 'primary'], {})
    curate.execute(p, yes=True)
    q = tmp_path / 'primary/rejected_data/1'
    assert curate.hashes(q) == original
    assert not hdf5.exists() and not video.exists()
    assert (tmp_path / 'primary/rejected_data/converted/train_data' / hdf5.name).exists()
    assert count_project(tmp_path / 'primary/collect_data')[1]['total'] == 1
    status = curate.project_status(tmp_path / 'primary')
    assert status['counts']['quarantined'] == 1 and status['train_data_stale']
    curate.execute(plan(tmp_path, ['restore', '--project', 'primary', '--episodes', '1'], {}), yes=True)
    assert curate.hashes(e) == original and curate.hashes(hdf5) == converted_hash
    assert curate.metadata(e)['review_status'] == 'rejected'
    records = [json.loads(line) for line in (tmp_path / 'primary/curation_log.jsonl').read_text().splitlines()]
    assert len(records) == 2
    assert records[0]['operations'][0]['sha256'] == original


def test_worked_example_24_plus_rejected_top_up_to_25(tmp_path):
    for i in range(1, 25):
        episode(tmp_path, 'primary', str(i))
    episode(tmp_path, 'primary', '25', 'rejected')
    for i in range(30, 35):
        episode(tmp_path, 'extra', str(i))
    registry = dict(primary=config(), extra=config())
    curate.execute(plan(tmp_path, ['quarantine', '--project', 'primary'], registry), yes=True)
    p = plan(tmp_path, ['top-up', '--from', 'extra', '--to', 'primary', '--target', '25'], registry)
    assert [op.source.name for op in p.operations] == ['30']
    curate.execute(p, yes=True)
    assert len(curate.accepted(tmp_path / 'primary')) == 25
    assert len(curate.accepted(tmp_path / 'extra')) == 4
    assert (tmp_path / 'primary/rejected_data/25').exists()


def test_transfer_oldest_timestamp_not_folder_sort(tmp_path):
    episode(tmp_path, 'extra', '1', started=100)
    oldest = episode(tmp_path, 'extra', '2', started=10)
    project(tmp_path, 'primary')
    p = plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--count', '1'], dict(primary=config(), extra=config()))
    assert p.operations[0].source == oldest
    raw = curate.hashes(oldest)
    curate.execute(p, yes=True)
    assert curate.hashes(tmp_path / 'primary/collect_data/2') == raw
    for name in ('primary', 'extra'):
        with pytest.raises(ValueError, match='Stale train_data'):
            require_fresh(tmp_path / name)


@pytest.mark.parametrize('move', [False, True])
def test_merge_copy_and_move(tmp_path, move):
    a = episode(tmp_path, 'primary', '1')
    b = episode(tmp_path, 'extra', '2')
    registry = {name: config() for name in ('primary', 'extra', 'NEW')}
    command = ['merge', '--from', 'primary', 'extra', '--to', 'NEW'] + (['--move'] if move else [])
    p = plan(tmp_path, command, registry)
    curate.execute(p, yes=True)
    assert len(curate.accepted(tmp_path / 'NEW')) == 2
    assert a.exists() == (not move) and b.exists() == (not move)
    assert (tmp_path / 'primary/train_data/STALE.json').exists() == move
    assert (tmp_path / 'primary/curation_log.jsonl').exists()


@pytest.mark.parametrize('status', ['rejected', 'unreviewed'])
def test_explicit_transfer_refuses_nonaccepted(tmp_path, status):
    episode(tmp_path, 'extra', '1', status)
    project(tmp_path, 'primary')
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='requires accepted'):
        plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--episodes', '1'], dict(primary=config(), extra=config()))
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('field,value', [
    ('schema_version', 2), ('medium', 'carton'),
    ('camera_names', ['top']), ('control_period_ms', 20), ('episode_len', 0),
])
def test_incompatible_destination_names_field_without_moves(tmp_path, field, value):
    episode(tmp_path, 'extra', '1')
    project(tmp_path, 'primary')
    destination = config()
    destination[field] = value
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match=field):
        plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--count', '1'], dict(primary=destination, extra=config()))
    assert snapshot(tmp_path) == before


def test_id_collision_and_partial_frame_refused(tmp_path):
    e = episode(tmp_path, 'extra', '1')
    episode(tmp_path, 'primary', '1')
    registry = dict(primary=config(), extra=config())
    with pytest.raises(ValueError, match='collision'):
        plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--count', '1'], registry)
    (e / 'topImg/0.jpg').unlink()
    with pytest.raises(ValueError, match='camera set'):
        plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--count', '1'], registry)


def test_rollout_requires_both_flag_and_explicit_project(tmp_path):
    episode(tmp_path, 'extra', '1', source='rollout')
    for name in ('primary', 'rollout_primary'):
        project(tmp_path, name)
    registry = {name: config() for name in ('primary', 'extra', 'rollout_primary')}
    for target, flag in [('primary', []), ('primary', ['--allow-rollouts']), ('rollout_primary', [])]:
        with pytest.raises(ValueError, match='Rollout requires'):
            plan(tmp_path, ['transfer', '--from', 'extra', '--to', target, '--count', '1'] + flag, registry)
    p = plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'rollout_primary', '--count', '1', '--allow-rollouts'], registry)
    assert len(p.operations) == 1


def test_dry_run_and_declined_confirmation_change_nothing(tmp_path):
    episode(tmp_path, 'extra', '1')
    project(tmp_path, 'primary')
    p = plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--count', '1'], dict(primary=config(), extra=config()))
    before = snapshot(tmp_path)
    assert not curate.execute(p, dry_run=True)
    assert snapshot(tmp_path) == before
    assert not curate.execute(p, input_fn=lambda _: 'no')
    assert snapshot(tmp_path) == before


def test_full_plan_preflight_and_runtime_rollback(tmp_path, monkeypatch):
    episode(tmp_path, 'extra', '1')
    episode(tmp_path, 'extra', '2')
    project(tmp_path, 'primary')
    registry = dict(primary=config(), extra=config())
    p = plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--count', '2'], registry)
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
    e = episode(tmp_path, 'extra', '1')
    project(tmp_path, 'primary')
    p = plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--count', '1'], dict(primary=config(), extra=config()))
    (e / 'topImg/0.jpg').write_bytes(b'changed')
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='Source changed'):
        curate.execute(p, yes=True)
    assert snapshot(tmp_path) == before


def test_stale_blocks_preparation_training_and_robomimic(tmp_path, monkeypatch):
    episode(tmp_path, 'primary', '1')
    marker = tmp_path / 'primary/train_data/STALE.json'
    marker.parent.mkdir()
    marker.write_text('{}')
    monkeypatch.setattr(prepare, 'PROJECTS', dict(primary=config()))
    with pytest.raises(SystemExit):
        prepare.main(['--root', str(tmp_path), '--dataset-name', 'primary', '--convert'])
    with pytest.raises(ValueError, match='Stale train_data'):
        require_training_folders([tmp_path / 'primary/train_data'])
    from scripts.convert_to_robomimic import inspect_sources
    with pytest.raises(ValueError, match='Stale train_data'):
        inspect_sources([tmp_path / 'primary'], dict(medium='poly_mailer'))


def test_fresh_rebuild_copies_only_accepted_and_leaves_source_untouched(tmp_path, monkeypatch):
    e = episode(tmp_path, 'primary', '1')
    episode(tmp_path, 'primary', '2', 'rejected')
    marker = tmp_path / 'primary/train_data/STALE.json'
    marker.parent.mkdir()
    marker.write_text('{}')
    monkeypatch.setattr(prepare, 'PROJECTS', dict(primary=config(), NEW=config()))
    before = snapshot(tmp_path / 'primary')
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(prepare.subprocess, 'run', run)
    assert prepare.main(['--root', str(tmp_path), '--dataset-name', 'primary', '--rebuild-to', 'NEW', '--convert']) == 0
    assert len(calls) == 1
    assert curate.hashes(tmp_path / 'NEW/collect_data/1') == curate.hashes(e)
    assert not (tmp_path / 'NEW/collect_data/2').exists()
    assert snapshot(tmp_path / 'primary') == before
    assert not (tmp_path / 'NEW/train_data/BUILDING.json').exists()


def test_missing_recording_rate_refused_without_changes(tmp_path):
    e = episode(tmp_path, 'extra', '1')
    m = curate.metadata(e)
    del m['control_period_ms']
    (e / 'episode_metadata.json').write_text(json.dumps(m))
    project(tmp_path, 'primary')
    registry = dict(primary=config(), extra=config())
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='Invalid recording rate'):
        plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--count', '1'], registry)
    assert snapshot(tmp_path) == before


def test_renamed_episode_refused(tmp_path):
    e = episode(tmp_path, 'extra', '1')
    project(tmp_path, 'primary')
    registry = dict(primary=config(), extra=config())
    e.rename(e.with_name('1_update_policy'))
    with pytest.raises(ValueError, match='episode_id differs'):
        plan(tmp_path, ['transfer', '--from', 'extra', '--to', 'primary', '--count', '1'], registry)


def test_quarantined_folders_excluded_from_review_and_conversion(tmp_path):
    e = episode(tmp_path, 'primary', '1', 'rejected')
    curate.execute(plan(tmp_path, ['quarantine', '--project', 'primary'], {}), yes=True)
    from scripts.review_episodes import review_project
    assert review_project(tmp_path / 'primary', dry_run=True)['accepted'] == 0
    assert count_project(tmp_path / 'primary/collect_data')[1]['total'] == 0
    assert not e.exists()


@pytest.mark.parametrize('medium', ['envelope', 'poly_mailer', 'carton'])
def test_real_fresh_conversion_and_review_round_trip(tmp_path, monkeypatch, medium):
    import cv2
    episode(tmp_path, 'primary', '1', 'rejected', medium=medium)
    e = episode(tmp_path, 'primary', '2', medium=medium, frames=2)
    for p in (e / 'observation').glob('*.pkl'):
        obs = pickle.loads(p.read_bytes())
        obs.update(control=obs['joint_positions'].copy(), joint_velocities=np.zeros(14))
        p.write_bytes(pickle.dumps(obs))
    for folder in curate.CAMERAS.values():
        for p in (e / folder).glob('*.jpg'):
            assert cv2.imwrite(str(p), np.full((480, 640, 3), 80, dtype=np.uint8))
    stale = tmp_path / 'primary/train_data/STALE.json'
    stale.parent.mkdir()
    stale.write_text('{}')
    cfg = config(medium=medium)
    monkeypatch.setattr(prepare, 'PROJECTS', dict(primary=cfg, NEW=cfg))
    assert prepare.main(['--root', str(tmp_path), '--dataset-name', 'primary', '--rebuild-to', 'NEW', '--convert']) == 0
    hdf5 = tmp_path / 'NEW/train_data/episode_init_0.hdf5'
    assert list(hdf5.parent.glob('*.hdf5')) == [hdf5]
    with h5py.File(str(hdf5), 'r') as converted:
        assert converted['action'].shape == (2, 14)
        assert json.loads(converted.attrs['episode_metadata_json']) == curate.metadata(e)
        assert set(converted['observations']) == {'qpos', 'qvel', 'images'}
    video = tmp_path / 'NEW/output_videos/2_video.mp4'
    assert video.is_file() and video.stat().st_size > 0
    from scripts.review_episodes import set_review_status
    assert set_review_status(tmp_path / 'NEW/collect_data/2', 'accepted', dry_run=True) == 1


def test_insufficient_accepted_and_wrong_quarantine_fail_without_changes(tmp_path):
    episode(tmp_path, 'primary', '1')
    project(tmp_path, 'extra')
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='Not enough accepted'):
        plan(tmp_path, ['top-up', '--to', 'extra', '--from', 'primary', '--target', '2'], dict(primary=config(), extra=config()))
    with pytest.raises(ValueError, match='requires rejected'):
        plan(tmp_path, ['quarantine', '--project', 'primary', '--episodes', '1'], {})
    assert snapshot(tmp_path) == before


def test_symlink_and_cross_filesystem_moves_refused(tmp_path, monkeypatch):
    e = episode(tmp_path, 'primary', '1')
    p = curate.Plan('test')
    (e / 'link').symlink_to(e / 'episode_metadata.json')
    with pytest.raises(ValueError, match='Symlink'):
        p.add(e, tmp_path / 'extra/collect_data/1')
    (e / 'link').unlink()
    from types import SimpleNamespace
    monkeypatch.setattr(curate, 'nearest_parent', lambda _: SimpleNamespace(stat=lambda: SimpleNamespace(st_dev=-1)))
    with pytest.raises(ValueError, match='Cross-filesystem'):
        p.add(e, tmp_path / 'extra/collect_data/1')


def test_transfer_refuses_mixed_media(tmp_path):
    episode(tmp_path, 'source', '1', medium='carton')
    project(tmp_path, 'target')
    with pytest.raises(ValueError, match='medium mismatch'):
        plan(tmp_path, ['transfer', '--from', 'source', '--to', 'target', '--count', '1'],
             dict(source=config(medium='carton'), target=config()))


def test_frozen_dataset_and_split_warn_but_never_change(tmp_path):
    e = episode(tmp_path, 'primary', '1')
    artifact(e)
    project(tmp_path, 'extra')
    frozen = tmp_path / 'training'
    frozen.mkdir()
    split = frozen / 'split.json'
    split.write_text(json.dumps(dict(sources=[dict(id='primary/episode_init_0.hdf5')])))
    dataset = frozen / 'dataset.hdf5'
    with h5py.File(str(dataset), 'w') as output:
        demo = output.create_group('data/demo_0')
        demo.attrs['episode_metadata_json'] = json.dumps(curate.metadata(e))
    before = snapshot(frozen)
    p = plan(tmp_path, ['transfer', '--from', 'primary', '--to', 'extra', '--count', '1'], dict(primary=config(), extra=config()))
    assert any('Frozen dataset/split/config' in warning for warning in p.warnings)
    assert any('robomimic dataset' in warning for warning in p.warnings)
    curate.execute(p, yes=True)
    assert snapshot(frozen) == before


def test_failed_fresh_conversion_keeps_training_blocked(tmp_path, monkeypatch):
    episode(tmp_path, 'primary', '1')
    monkeypatch.setattr(prepare, 'PROJECTS', dict(primary=config(), NEW=config()))
    from types import SimpleNamespace
    monkeypatch.setattr(prepare.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=1))
    assert prepare.main(['--root', str(tmp_path), '--dataset-name', 'primary', '--rebuild-to', 'NEW', '--convert']) == 1
    assert (tmp_path / 'NEW/train_data/BUILDING.json').exists()
    with pytest.raises(ValueError, match='BUILDING.json'):
        require_training_folders(tmp_path / 'NEW/train_data')


def test_rollback_preserves_prior_audit_and_stale_marker(tmp_path, monkeypatch):
    episode(tmp_path, 'primary', '1')
    episode(tmp_path, 'primary', '2')
    project(tmp_path, 'extra')
    registry = dict(primary=config(), extra=config())
    curate.execute(plan(tmp_path, ['transfer', '--from', 'primary', '--to', 'extra', '--count', '1'], registry), yes=True)
    p = plan(tmp_path, ['transfer', '--from', 'primary', '--to', 'extra', '--count', '1'], registry)
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
