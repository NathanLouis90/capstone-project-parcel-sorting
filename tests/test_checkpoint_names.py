"""Short checkpoint paths must select saved weights without altering history."""

import json
import os
from pathlib import Path

import pytest

from scripts import training_workflow
from scripts.training_workflow import publish_checkpoint, run_training_job


def checkpoint(folder, name):
    path = folder / 'runs/named_model/20261025/models' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(name.encode())
    return path


def test_best_and_latest_follow_different_checkpoints_and_move_with_model(tmp_path):
    folder = tmp_path / 'model'
    job = {'folder': str(folder)}
    first = checkpoint(folder, 'model_epoch_1_best_validation_0.5.pth')
    best = checkpoint(folder, 'model_epoch_4_best_validation_0.1.pth')
    latest = checkpoint(folder, 'model_epoch_10.pth')
    for path in (first, best, latest, first):
        publish_checkpoint(job, path)
    assert (folder / 'best.pth').resolve() == best
    assert (folder / 'latest.pth').resolve() == latest
    assert job['best_checkpoint_epoch'] == 4 and job['latest_checkpoint_epoch'] == 10
    assert job['best_checkpoint_loss'] == 0.1
    assert not os.path.isabs(os.readlink(str(folder / 'best.pth')))
    moved = tmp_path / 'renamed_model'
    folder.rename(moved)
    assert (moved / 'best.pth').read_bytes() == best.name.encode()
    assert (moved / 'latest.pth').read_bytes() == latest.name.encode()
    assert len(list((moved / 'runs').rglob('*.pth'))) == 3


def test_short_paths_refuse_missing_external_or_existing_regular_files(tmp_path):
    folder = tmp_path / 'model'
    job = {'folder': str(folder)}
    good = checkpoint(folder, 'model_epoch_1_best_validation_0.1.pth')
    with pytest.raises(ValueError, match='saved training checkpoint'):
        publish_checkpoint(job, good.parent / 'model_epoch_2.pth')
    external = tmp_path / 'model_epoch_3.pth'
    external.write_bytes(b'external')
    with pytest.raises(ValueError, match='outside'):
        publish_checkpoint(job, external)
    original = folder / 'best.pth'
    original.write_bytes(b'preserve user file')
    with pytest.raises(ValueError, match='Refusing to replace'):
        publish_checkpoint(job, good)
    assert original.read_bytes() == b'preserve user file'
    assert good.read_bytes() == good.name.encode()


@pytest.mark.parametrize('exit_code', [0, 1])
def test_trainer_publishes_completed_saves_even_if_later_training_fails(tmp_path, monkeypatch, exit_code):
    best = checkpoint(tmp_path, 'model_epoch_1_best_validation_0.1.pth')
    latest = checkpoint(tmp_path, 'model_epoch_2.pth')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'experiment': {'name': 'named_model'}}))
    # Existing files above represent checkpoints produced by the child process.
    # Start with an empty destination run so the overwrite guard remains active.
    config.write_text(json.dumps({'experiment': {'name': 'new_run'}}))
    job = {'folder': str(tmp_path), 'name': 'named_model', 'config': str(config),
           'status': 'ready', 'settings': {'epochs': 2}}

    class Process:
        stdout = iter(['save checkpoint to {}\n'.format(best),
                       'save checkpoint to {}\n'.format(latest)])

        def wait(self):
            return exit_code

        def poll(self):
            return exit_code

    monkeypatch.setattr(training_workflow.subprocess, 'Popen', lambda *args, **kwargs: Process())
    if exit_code:
        with pytest.raises(RuntimeError, match='Training failed'):
            run_training_job(job, progress=lambda message: None)
    else:
        run_training_job(job, progress=lambda message: None)
    saved = json.loads((tmp_path / '.training/job.json').read_text())
    assert saved['status'] == ('failed' if exit_code else 'completed')
    assert Path(saved['best_checkpoint']).resolve() == best
    assert Path(saved['latest_checkpoint']).resolve() == latest
