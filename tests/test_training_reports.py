"""Training reports preserve observed metrics and reuse frozen comparison data."""

from dataclasses import replace
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from parcel_sorting.training import menu as train_models, workflow as training_workflow
from parcel_sorting.training.report import EpochMetrics, generate_training_report, read_metrics
from parcel_sorting.training.report import learning_rate_history, learning_rate_note, saved_config
from parcel_sorting.training.parameters import act_build_defaults, configuration_catalog, flatten_configuration
from parcel_sorting.training.workflow import TrainingSettings, create_training_jobs


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
    metadata = json.loads((folder / '.training/report.json').read_text())
    assert metadata['learning_rate_graph_shown'] is False
    assert 'stayed at' in metadata['learning_rate_note']
    assert 'algo.horizon.prediction_horizon' in (folder / 'full_configuration.csv').read_text()
    assert metadata['implementation_defaults'] == []


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


def test_full_configuration_preserves_every_saved_leaf_and_marks_inactive_fields(tmp_path):
    job = configured_job(tmp_path)
    config = saved_config(job)
    config['future_fields'] = {'scalar': 7, 'empty': {}, 'choices': [], 'enabled': False,
                               'objects': [{'name': 'one'}, {'name': 'two'}]}
    for key in ('temporal_agg', 'temporal_ensemble_coeff', 'query_frequency'):
        config['algo']['act'].pop(key, None)
    rows = configuration_catalog(config)
    recorded = {row['path']: row['value'] for row in rows if row['source'] == 'Saved configuration'}
    assert recorded == dict(flatten_configuration(config))
    assert recorded['future_fields.enabled'] is False
    assert recorded['future_fields.objects[1].name'] == 'two'
    by_path = {row['path']: row for row in rows}
    assert 'Unused' in by_path['observation.encoder.rgb.core_class']['effect']
    assert 'Unused' in by_path['algo.loss.l2_weight']['effect']
    assert 'Inactive' in by_path['algo.optim_params.policy.learning_rate.scheduler_type']['effect']
    assert 'Legacy compatibility fallback' in by_path['algo.act.temporal_agg']['source']
    assert by_path['algo.act.temporal_agg']['value'] is False
    assert by_path['train.batch_size']['menu'] == 'Common: Batch size'


@pytest.mark.parametrize('changes', [False, True])
@pytest.mark.parametrize('algorithm', ['act', 'diffusion_policy'])
def test_learning_rate_graph_only_appears_when_recorded_rates_change(tmp_path, monkeypatch, changes, algorithm):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    job = configured_job(tmp_path, algorithm)
    records = [record('train', 1, .2), record('valid', 1, .3), record('train', 2, .1), record('valid', 2, .2)]
    if algorithm == 'diffusion_policy':
        for row in records:
            row['metrics'].pop('Reconstruction_Loss')
            row['metrics'].pop('KL_Loss')
            row['metrics']['Time_Data_Loading'] = 0.01
            if row['phase'] == 'train':
                row['metrics']['Policy_Grad_Norms'] = 0.5
    if changes:
        records[2]['metrics']['Optimizer/policy0_lr'] = 0.0001
    titles = []
    original = FigureCanvasAgg.print_png

    def capture(canvas, *args, **kwargs):
        titles.extend(axis.get_title() for axis in canvas.figure.axes)
        return original(canvas, *args, **kwargs)

    monkeypatch.setattr(FigureCanvasAgg, 'print_png', capture)
    generate_training_report(job, records=records)
    metadata = json.loads((Path(job['folder']) / '.training/report.json').read_text())
    assert metadata['learning_rate_graph_shown'] is changes
    assert ('Actual learning rate' in titles) is changes
    assert 'algo.optim_params.policy.optimizer_type' in (Path(job['folder']) / 'full_configuration.csv').read_text()
    assert 'Full saved configuration' in (Path(job['folder']) / 'training_summary.txt').read_text()
    if algorithm == 'act':
        assert 'not recorded' in (Path(job['folder']) / 'training_report.html').read_text()
        assert 'ACT reconstruction loss' in titles
    else:
        assert 'DP policy gradient norm' in titles
        assert 'Reported data-loading time' in titles
        assert 'ACT KL loss' not in titles
        assert metadata['implementation_defaults'] == []
    recorded = {row['path']: row['value'] for row in metadata['configuration']
                if row['source'] == 'Saved configuration'}
    assert recorded == dict(flatten_configuration(saved_config(job)))
    assert ('ranged from' if changes else 'flat learning-rate graph is omitted') in metadata['learning_rate_note']


def test_missing_learning_rate_history_does_not_invent_a_constant_rate(tmp_path):
    job = configured_job(tmp_path)
    assert learning_rate_history([]) == ({}, False)
    assert 'cannot be verified' in learning_rate_note(saved_config(job), [])


def test_report_reads_trainer_captured_configuration_instead_of_later_input_edits(tmp_path):
    job = configured_job(tmp_path)
    original = saved_config(job)
    captured = Path(job['folder']) / 'runs/named_act/date/config.json'
    captured.parent.mkdir(parents=True)
    captured.write_text(json.dumps(original))
    changed = json.loads(Path(job['config']).read_text())
    changed['train']['batch_size'] = 99
    Path(job['config']).write_text(json.dumps(changed))
    assert saved_config(job)['train']['batch_size'] == original['train']['batch_size']
    assert dict(act_build_defaults())['Transformer dropout'] == 0.1
    assert dict(act_build_defaults())['Transformer activation'] == 'relu'
