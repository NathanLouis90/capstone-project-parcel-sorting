"""Training reports preserve observed metrics and reuse frozen comparison data."""

from dataclasses import replace
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from scripts import train_models, training_workflow
from scripts.training_report import EpochMetrics, generate_training_report, read_metrics
from scripts.training_workflow import TrainingSettings, create_training_jobs


def configured_job(tmp_path, algorithm='act'):
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    dataset, split_file = prepared / 'snapshot.hdf5', prepared / 'split.json'
    split = dict(recipe={'medium': 'poly_mailer'}, seed=13, train=['demo_0'], valid=['demo_1'],
                 sources=[{'id': 'bottom/1'}, {'id': 'top/2'}])
    split_file.write_text(json.dumps(split))
    with h5py.File(str(dataset), 'w') as target:
        data = target.create_group('data')
        data.attrs.update(recipe='poly_mailer', split_json=json.dumps(split), split_file=str(split_file), total=4)
        for name in ('demo_0', 'demo_1'):
            demo = data.create_group(name)
            demo.attrs['num_samples'] = 2
            demo.create_dataset('obs/top', shape=(2, 80, 80, 3), dtype=np.uint8)
        for key in ('train', 'valid'):
            target.create_dataset('mask/' + key, data=np.asarray(split[key], dtype='S'))
    settings = TrainingSettings(device='cpu', epochs=2, image_size=80, seed=13, act_learning_rate=0.0002)
    return create_training_jobs(prepared, settings, {algorithm: 'named_' + algorithm}, tmp_path / 'models',
                                dataset=dataset, split_file=split_file)[0]


def record(phase, epoch, loss):
    return dict(phase=phase, epoch=epoch, metrics={'Loss': loss, 'Reconstruction_Loss': loss - 0.01,
                'KL_Loss': 0.0005, 'Optimizer/policy0_lr': 0.0002, 'Time_Epoch': 0.1})


def test_epoch_parser_ignores_progress_and_preserves_finite_scalars():
    parser = EpochMetrics()
    lines = ['100%| progress bar\n', 'Train Epoch 1\n', '{\n', '"Loss": 0.2,\n',
             '"KL_Loss": 0.001,\n', '"bad": NaN\n', '}\n']
    records = [result for line in lines for result in [parser.feed(line)] if result]
    assert records == [dict(phase='train', epoch=1, metrics={'Loss': 0.2, 'KL_Loss': 0.001})]


def test_full_report_uses_saved_hyperparameters_and_all_metrics(tmp_path):
    job = configured_job(tmp_path)
    folder = Path(job['folder'])
    records = [record('train', 1, .2), record('valid', 1, .3), record('train', 2, .1), record('valid', 2, .5)]
    (folder / 'metrics.jsonl').write_text('\n'.join(json.dumps(r) for r in records) + '\n')
    report = generate_training_report(job)
    assert report.exists() and 'data:image/png;base64,' in report.read_text()
    assert 'Recorded epoch metrics: 2 training, 2 validation' in report.read_text()
    assert (folder / 'loss_curves.png').read_bytes().startswith(b'\x89PNG')
    assert 'valid/KL_Loss' in (folder / 'metrics.csv').read_text()
    metadata = json.loads((folder / '.training/report.json').read_text())
    assert dict(metadata['settings'])['Learning rate'] == 0.0002
    assert metadata['dataset']['train_count'] == metadata['dataset']['valid_count'] == 1
    assert any('does not establish its cause' in note for note in metadata['findings'])
    assert len(read_metrics(folder)) == 4


def test_sparse_legacy_report_does_not_fabricate_training_curve(tmp_path):
    job = configured_job(tmp_path)
    folder = Path(job['folder'])
    models = folder / 'runs/experiment/date/models'
    models.mkdir(parents=True)
    (models / 'model_epoch_5_best_validation_0.1.pth').write_bytes(b'saved weights')
    observations = [dict(phase='valid', epoch=10, metrics={'Loss': .4}, source='terminal excerpt')]
    (folder / '.training/observations.json').write_text(json.dumps(observations))
    generate_training_report(job)
    metadata = json.loads((folder / '.training/report.json').read_text())
    assert metadata['records'] == 0 and 'Incomplete history' in metadata['coverage']
    assert any('Overfitting cannot be confirmed' in note for note in metadata['findings'])
    assert any('4.00 times' in note for note in metadata['findings'])
    assert (folder / 'metrics.csv').read_text().strip() == 'epoch'


@pytest.mark.parametrize('exit_code', [0, 1])
def test_training_retains_metrics_and_report_after_success_or_failure(tmp_path, monkeypatch, exit_code):
    job = configured_job(tmp_path, 'diffusion_policy')
    records = [record('train', 2, .2), record('valid', 2, .3)]
    lines = []
    for r in records:
        lines.append(('Train' if r['phase'] == 'train' else 'Validation') + ' Epoch 2\n')
        lines.extend(line + '\n' for line in json.dumps(r['metrics'], indent=4).splitlines())

    class Process:
        stdout = iter(lines)

        def wait(self):
            return exit_code

        def poll(self):
            return exit_code

    monkeypatch.setattr(training_workflow.subprocess, 'Popen', lambda *args, **kwargs: Process())
    if exit_code:
        with pytest.raises(RuntimeError, match='Training failed'):
            training_workflow.run_training_job(job, progress=lambda message: None)
    else:
        training_workflow.run_training_job(job, progress=lambda message: None)
    folder = Path(job['folder'])
    assert read_metrics(folder) == records
    assert job['status'] == ('failed' if exit_code else 'completed')
    assert (folder / 'training_report.html').exists()
    assert job['status'] in (folder / 'training_report.html').read_text()


def test_dp_comparison_reuses_exact_snapshot_and_split_without_config_helpers(tmp_path, monkeypatch):
    source = configured_job(tmp_path)
    models = tmp_path / 'models'
    defaults = train_models.load_hyperparameter_defaults(tmp_path / 'missing-preferences.json')
    defaults['diffusion_policy'] = replace(defaults['diffusion_policy'], device='cpu', epochs=3)
    monkeypatch.setattr(train_models, 'find_models', lambda path: [source])
    monkeypatch.setattr(train_models, 'check_training_device', lambda settings: None)
    trained = []
    monkeypatch.setattr(train_models, 'run_training_job', lambda job: trained.append(job))
    answers = iter(['1', '2', 'dp_poly_mailer_v1.0', 'TRAIN'])
    train_models.train_frozen_action(models, defaults, tmp_path / 'preferences.json', lambda prompt: next(answers))
    assert trained[0]['dataset'] == source['dataset']
    assert trained[0]['settings']['seed'] == 13 and trained[0]['settings']['image_size'] == 80
    config = json.loads(Path(trained[0]['config']).read_text())
    assert config['experiment']['env_meta_update_dict']['env_kwargs']['medium'] == 'poly_mailer'
    assert config['train']['num_epochs'] == 3
    assert trained[0]['train_count'] == trained[0]['valid_count'] == 1
