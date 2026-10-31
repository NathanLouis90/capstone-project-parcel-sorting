"""Offline training reports from recorded metrics, saved settings, and checkpoints."""

import base64
from collections import defaultdict
import csv
from datetime import datetime, timezone
import html
import io
import json
import math
from pathlib import Path
import re

from parcel_sorting.data.recording import write_metadata
from parcel_sorting.training.parameters import act_build_defaults, configuration_catalog


class EpochMetrics:
    """Read the trainer's complete epoch JSON blocks without parsing progress bars."""

    def __init__(self):
        self.header = None
        self.buffer = []

    def feed(self, line):
        line = re.sub(r'\x1b\[[0-9;]*m', '', line).strip()
        match = re.fullmatch(r'(Train|Validation) Epoch (\d+)', line)
        if match:
            self.header = ('train' if match[1] == 'Train' else 'valid', int(match[2]))
            self.buffer = []
            return None
        if self.header is None or (not self.buffer and line != '{'):
            return None
        self.buffer.append(line)
        if line != '}':
            return None
        header, self.header = self.header, None
        try:
            values = json.loads('\n'.join(self.buffer))
        except ValueError:
            return None
        metrics = {key: value for key, value in values.items()
                   if type(value) in (float, int) and math.isfinite(value)}
        return dict(phase=header[0], epoch=header[1], metrics=metrics)


def read_metrics(folder):
    folder = Path(folder)
    records = {}
    parser = EpochMetrics()
    log = folder / 'training.log'
    if log.exists():
        with log.open(errors='replace') as stream:
            for line in stream:
                record = parser.feed(line)
                if record:
                    records[(record['phase'], record['epoch'])] = record
    saved = folder / 'metrics.jsonl'
    if saved.exists():
        for line in saved.read_text().splitlines():
            try:
                record = json.loads(line)
                records[(record['phase'], record['epoch'])] = record
            except (ValueError, KeyError):
                continue  # A running process may be between writing and flushing a line.
    return [records[key] for key in sorted(records, key=lambda key: (key[1], key[0]))]


def checkpoint_scores(folder):
    result = []
    for path in Path(folder).glob('**/models/model_epoch_*_best_validation_*.pth'):
        match = re.fullmatch(r'model_epoch_(\d+)_best_validation_([\d.eE+\-]+)\.pth', path.name)
        if match:
            loss = float(match[2])
            if math.isfinite(loss):
                result.append(dict(epoch=int(match[1]), loss=loss, path=str(path.resolve())))
    return sorted(result, key=lambda item: item['epoch'])


def saved_config(job):
    # The run copy records what the trainer actually used. Prefer it to an input
    # configuration that could have been edited after the run started.
    captured = sorted((Path(job['folder']) / 'runs').glob('*/*/config.json'))
    if captured:
        return json.loads(captured[-1].read_text())
    if 'config' in job:
        return json.loads(Path(job['config']).read_text())
    return job['legacy_config']


def dataset_details(config):
    """Read frozen provenance without loading images or depending on config helpers."""
    import h5py
    details = dict(datasets=[], train_count=None, valid_count=None, frames=None, split=None)
    data = config.get('train', {}).get('data') or []
    if len(data) != 1 or not isinstance(data[0], dict):
        return details
    path = Path(data[0]['path'])
    details['path'] = str(path)
    if not path.is_file():
        details['note'] = 'The original training dataset is unavailable; its counts cannot be verified.'
        return details
    with h5py.File(str(path), 'r') as stream:
        data = stream['data']
        split = json.loads(data.attrs.get('split_json', '{}'))
        details.update(train_count=len(stream['mask/train']), valid_count=len(stream['mask/valid']),
                       frames=int(data.attrs.get('total', sum(int(demo.attrs.get('num_samples', 0)) for demo in data.values()))),
                       split=split, medium=data.attrs.get('recipe', ''), split_file=data.attrs.get('split_file'),
                       datasets=sorted({source['id'].split('/')[0] for source in split.get('sources', [])}))
        if len(data):
            demo = next(iter(data.values()))
            if 'obs/top' in demo:
                details['image_size'] = list(demo['obs/top'].shape[1:3])
    return details


def settings_rows(config, details):
    train, experiment, algo = config['train'], config['experiment'], config['algo']
    rows = [('Algorithm', 'ACT' if config['algo_name'] == 'act' else 'Diffusion Policy'),
            ('Epoch budget', train['num_epochs']), ('Batch size', train['batch_size']),
            ('Training batches per epoch', experiment.get('epoch_every_n_steps')),
            ('Validation batches per epoch', experiment.get('validation_epoch_every_n_steps')),
            ('Optimizer', algo['optim_params']['policy'].get('optimizer_type', 'adam')),
            ('Learning rate', algo['optim_params']['policy']['learning_rate']['initial']),
            ('Learning-rate scheduler type', algo['optim_params']['policy']['learning_rate'].get('scheduler_type', 'multistep')),
            ('Learning-rate scheduler active', bool(algo['optim_params']['policy']['learning_rate'].get('epoch_schedule'))),
            ('Learning-rate decay epochs', algo['optim_params']['policy']['learning_rate'].get('epoch_schedule', [])),
            ('Learning-rate decay factor', algo['optim_params']['policy']['learning_rate'].get('decay_factor')),
            ('Weight decay', algo['optim_params']['policy'].get('regularization', {}).get('L2', 0)),
            ('Gradient clipping norm', train.get('max_grad_norm')),
            ('Random seed', train['seed']), ('Device requested', 'CUDA' if train.get('cuda') else 'CPU'),
            ('Image size', details.get('image_size', 'Unavailable')),
            ('Cameras', ', '.join(config['observation']['modalities']['obs']['rgb'])),
            ('Action normalization', train.get('action_config', {}).get('actions', {}).get('normalization')),
            ('Observation normalization', train.get('hdf5_normalize_obs')),
            ('Periodic checkpoint interval (epochs)', experiment.get('save', {}).get('every_n_epochs'))]
    if config['algo_name'] == 'act':
        rows.append(('ACT chunk length', train['seq_length']))
        labels = {'kl_weight': 'KL weight', 'hidden_dim': 'Hidden dimension', 'dim_feedforward': 'Feedforward dimension',
                  'enc_layers': 'Encoder layers', 'dec_layers': 'Decoder layers', 'nheads': 'Attention heads',
                  'latent_dim': 'Latent dimension', 'backbone': 'Image backbone', 'pretrained_backbone': 'Pretrained backbone'}
        rows.extend((label, algo['act'].get(key)) for key, label in labels.items())
        rows.append(('Joint-input noise std (training only)', algo['act'].get('qpos_noise_std', 0.0)))
        temporal = algo['act'].get('temporal_agg', False)
        interval = algo['act'].get('query_frequency', 0)
        rows.extend([('ACT temporal ensembling (rollout default)', temporal),
                     ('ACT ensemble coefficient (+ older, - newer)', algo['act'].get('temporal_ensemble_coeff', 0.01)),
                     ('ACT replan interval when ensembling is off (0 = full chunk)', interval),
                     ('Effective ACT replan interval (control steps)', 1 if temporal else interval or train['seq_length'])])
    else:
        rows.extend((key.replace('_', ' ').capitalize(), value) for key, value in algo['horizon'].items())
        rows.append(('U-Net dimensions', algo['unet']['down_dims']))
        scheduler = 'ddpm' if algo['ddpm']['enabled'] else 'ddim'
        rows.append(('Diffusion scheduler', scheduler.upper()))
        rows.extend((key.replace('_', ' ').capitalize(), algo[scheduler][key])
                    for key in ('num_train_timesteps', 'num_inference_timesteps', 'beta_schedule', 'prediction_type'))
        rows.append(('EMA enabled', algo.get('ema', {}).get('enabled')))
    return rows


def training_analysis(config, records, scores, observations, details):
    valid = [dict(epoch=r['epoch'], loss=r['metrics']['Loss']) for r in records
             if r['phase'] == 'valid' and 'Loss' in r['metrics']]
    observed = [dict(epoch=r['epoch'], loss=r['metrics']['Loss']) for r in observations
                if r.get('phase') == 'valid' and 'Loss' in r.get('metrics', {})]
    evidence = sorted(scores + valid + observed, key=lambda point: point['epoch'])
    notes = []
    if evidence:
        best = min(evidence, key=lambda point: point['loss'])
        last = evidence[-1]
        notes.append('Lowest observed validation loss: {:.6g} at epoch {}. Latest available validation loss: {:.6g} at epoch {}.'.format(
            best['loss'], best['epoch'], last['loss'], last['epoch']))
        if best['loss'] > 0 and last['loss'] > best['loss'] * 1.15:
            notes.append('The latest validation loss is {:.2f} times the minimum. This is late validation deterioration; it does not establish its cause.'.format(last['loss'] / best['loss']))
        else:
            notes.append('The latest available validation score is close to the minimum. Check the complete curve and physical trials before selecting a model.')
    else:
        notes.append('No completed validation metrics are available yet.')
    train = [record for record in records if record['phase'] == 'train' and 'Loss' in record['metrics']]
    if not train:
        notes.append('The training-loss curve is unavailable. Overfitting cannot be confirmed from saved best-checkpoint scores alone.')
    else:
        notes.append('A sustained fall in training loss while validation loss rises is consistent with overfitting. Noisy or rising losses in both curves can instead indicate optimization instability.')
    train_count, valid_count = details.get('train_count'), details.get('valid_count')
    if train_count is not None:
        notes.append('This snapshot has {} training and {} validation recordings. Nearby frames are correlated; recording count and placement/session diversity matter more than raw frame count.'.format(train_count, valid_count))
    steps = config['experiment'].get('epoch_every_n_steps')
    if steps:
        notes.append('The configured budget is {:,} optimizer updates ({} epochs x {} batches). One configured epoch is a fixed batch budget, not necessarily one pass over every recording.'.format(
            config['train']['num_epochs'] * steps, config['train']['num_epochs'], steps))
    notes.append('Validation is sampled for {} batches per epoch. A minimum from one epoch may reflect sampling noise; inspect several neighboring epochs.'.format(
        config['experiment'].get('validation_epoch_every_n_steps')))
    if config['algo_name'] == 'act':
        notes.append('ACT total loss is reconstruction L1 loss on normalized actions plus KL weight times KL loss. Near-zero KL alone does not establish useful grasping behavior.')
        temporal = config['algo']['act'].get('temporal_agg', False)
        interval = 1 if temporal else config['algo']['act'].get('query_frequency', 0) or config['train']['seq_length']
        notes.append('Saved ACT rollout defaults: temporal ensembling {}, replan every {} control steps. These inference settings do not change the training loss; evaluate their effect on physical corrections and inference time.'.format(
            'enabled' if temporal else 'disabled', interval))
    else:
        notes.append('DP loss measures its configured denoising objective. Stochastic diffusion noise can make validation loss fluctuate.')
    notes.append('ACT and DP optimize different losses; their numerical loss values cannot rank the algorithms. Compare held-out physical grasp/scan success, drops, and cycle time.')
    actions = [
        'Start physical evaluation with the lowest-validation checkpoint. Keep the same held-out placements and frozen train/validation split when comparing runs.',
        'If the train/validation gap keeps widening, test a shorter update budget or smaller network while holding other settings fixed.',
        'If both losses are unstable, test a lower learning rate as a separate experiment. Log the setting and compare multiple epochs rather than one minimum.',
        'Collect more varied successful demonstrations across bag positions, orientations, sessions, and lighting. Keep related parcel cycles in one partition.',
        'Change one factor at a time. Use validation to choose settings, then use separate physical test placements for final evaluation.',
    ]
    return notes, actions


def learning_rate_history(records):
    groups = defaultdict(list)
    for record in records:
        if record['phase'] != 'train':
            continue
        for key, value in record['metrics'].items():
            if key.startswith('Optimizer/') and key.endswith('_lr') and type(value) in (int, float) and math.isfinite(value):
                groups[key].append((record['epoch'], value))
    changing = any(any(not math.isclose(value, points[0][1], rel_tol=1e-9, abs_tol=0)
                       for _, value in points[1:]) for points in groups.values())
    return groups, changing


def learning_rate_note(config, records):
    groups, changing = learning_rate_history(records)
    initial = config['algo']['optim_params']['policy']['learning_rate']['initial']
    if not groups:
        return 'Configured initial learning rate: {:.8g}. No epoch learning-rate history was recorded, so a constant rate cannot be verified. No learning-rate graph is shown.'.format(initial)
    descriptions = []
    for key, points in groups.items():
        values = [value for _, value in points]
        if changing:
            descriptions.append('{} ranged from {:.8g} to {:.8g} over {} recorded training epochs'.format(key, min(values), max(values), len(points)))
        else:
            descriptions.append('{} stayed at {:.8g} across {} recorded training epochs'.format(key, values[0], len(points)))
    return '; '.join(descriptions) + ('. The graph shows actual optimizer rates, including schedule changes.' if changing
        else '. The flat learning-rate graph is omitted; the configured value remains in the settings table.')


def _value_text(value):
    return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value


def _plot(records, scores, observations, algorithm):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    if not records:
        figure = Figure(figsize=(11, 5), constrained_layout=True)
        axis = figure.subplots()
        if scores:
            axis.scatter([p['epoch'] for p in scores], [p['loss'] for p in scores], color='#c15313',
                         label='Saved best-validation scores only')
            best = min(scores, key=lambda point: point['loss'])
            axis.annotate('Best saved: epoch {} ({:.5g})'.format(best['epoch'], best['loss']),
                          xy=(best['epoch'], best['loss']), xytext=(20, 30), textcoords='offset points',
                          arrowprops={'arrowstyle': '->'}, fontsize=9)
        observed = [r for r in observations if 'Loss' in r.get('metrics', {})]
        if observed:
            axis.scatter([r['epoch'] for r in observed], [r['metrics']['Loss'] for r in observed],
                         marker='*', s=110, color='#9c287c', label='User-provided terminal excerpt')
        axis.set(title='Available validation evidence — incomplete history', xlabel='Epoch', ylabel='Validation loss')
        axis.grid(alpha=.2)
        if scores or observed:
            axis.legend(fontsize=9)
        else:
            axis.text(.5, .5, 'Waiting for the first completed epoch', transform=axis.transAxes, ha='center')
        buffer = io.BytesIO()
        FigureCanvasAgg(figure).print_png(buffer)
        return buffer.getvalue()
    figure = Figure(figsize=(12, 11), constrained_layout=True)
    grid = figure.add_gridspec(3, 2)
    total = figure.add_subplot(grid[0, 0])
    gap = figure.add_subplot(grid[0, 1])
    components = figure.add_subplot(grid[1, 0])
    extra = figure.add_subplot(grid[1, 1])
    rates, changing_rate = learning_rate_history(records)
    if changing_rate:
        rate = figure.add_subplot(grid[2, 0])
        for key, points in rates.items():
            rate.plot([epoch for epoch, _ in points], [value for _, value in points], label=key)
        rate.set_title('Actual learning rate')
        rate.set_ylabel('Learning rate')
        timing = figure.add_subplot(grid[2, 1])
    else:
        timing = figure.add_subplot(grid[2, :])
    grouped = defaultdict(list)
    for record in records:
        grouped[record['phase']].append(record)

    def series(axis, metric, phase, label, color):
        points = [r for r in grouped[phase] if metric in r['metrics']]
        if points:
            axis.plot([r['epoch'] for r in points], [r['metrics'][metric] for r in points], label=label, color=color)
        return bool(points)

    series(total, 'Loss', 'train', 'Training', '#2459a6')
    series(total, 'Loss', 'valid', 'Validation', '#c15313')
    if not grouped['valid'] and scores:
        total.scatter([p['epoch'] for p in scores], [p['loss'] for p in scores], label='Saved best scores only', color='#c15313', s=22)
    points = [r for r in observations if 'Loss' in r.get('metrics', {})]
    if points:
        total.scatter([r['epoch'] for r in points], [r['metrics']['Loss'] for r in points], marker='*', s=100,
                      color='#9c287c', label='User-provided terminal excerpt')
    total.set_title('Total objective loss' if grouped['valid'] else 'Available validation evidence (incomplete history)')
    total.set_ylabel('Loss (normalized objective)')
    training = {r['epoch']: r['metrics']['Loss'] for r in grouped['train'] if 'Loss' in r['metrics']}
    validation = {r['epoch']: r['metrics']['Loss'] for r in grouped['valid'] if 'Loss' in r['metrics']}
    epochs = sorted(set(training) & set(validation))
    if epochs:
        gap.plot(epochs, [validation[e] - training[e] for e in epochs], color='#7657a0', label='Validation minus training')
        gap.axhline(0, color='grey', linewidth=0.8)
    else:
        gap.text(.5, .5, 'Full training/validation pairs unavailable', transform=gap.transAxes, ha='center', wrap=True)
    gap.set_title('Train/validation loss gap')
    gap.set_ylabel('Loss difference')
    if algorithm == 'act':
        series(components, 'Reconstruction_Loss', 'train', 'Training reconstruction', '#2459a6')
        series(components, 'Reconstruction_Loss', 'valid', 'Validation reconstruction', '#c15313')
        components.set_title('ACT reconstruction loss')
        components.set_ylabel('Normalized action L1')
        series(extra, 'KL_Loss', 'train', 'Training KL', '#2459a6')
        series(extra, 'KL_Loss', 'valid', 'Validation KL', '#c15313')
        extra.set_title('ACT KL loss')
        extra.set_ylabel('KL divergence')
    else:
        series(components, 'Policy_Grad_Norms', 'train', 'Gradient norm', '#2459a6')
        components.set_title('DP policy gradient norm')
        components.set_ylabel('Gradient norm')
        series(extra, 'Time_Data_Loading', 'train', 'Training', '#2459a6')
        series(extra, 'Time_Data_Loading', 'valid', 'Validation', '#c15313')
        extra.set_title('Reported data-loading time')
        extra.set_ylabel('Minutes')
    series(timing, 'Time_Epoch', 'train', 'Training', '#2459a6')
    series(timing, 'Time_Epoch', 'valid', 'Validation', '#c15313')
    timing.set_title('Reported epoch duration')
    timing.set_ylabel('Minutes')
    for axis in figure.axes:
        axis.set_xlabel('Epoch')
        axis.grid(alpha=.2)
        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend(fontsize=8)
        elif not axis.texts:
            axis.text(.5, .5, 'No recorded metrics', transform=axis.transAxes, ha='center')
    buffer = io.BytesIO()
    FigureCanvasAgg(figure).print_png(buffer)
    return buffer.getvalue()


def generate_training_report(job, records=None):
    """Write a standalone HTML report, Markdown summary, graph, and metrics CSV."""
    folder = Path(job['folder'])
    config = saved_config(job)
    records = read_metrics(folder) if records is None else records
    observation_file = folder / '.training/observations.json'
    observations = json.loads(observation_file.read_text()) if observation_file.exists() else []
    scores = checkpoint_scores(folder)
    details = dataset_details(config)
    notes, actions = training_analysis(config, records, scores, observations, details)
    settings = settings_rows(config, details)
    catalog = configuration_catalog(config, details)
    build_defaults = act_build_defaults() if config['algo_name'] == 'act' else []
    rate_note = learning_rate_note(config, records)
    notes.append(rate_note)
    coverage = ('Recorded epoch metrics: {} training, {} validation epochs.'.format(
        sum(r['phase'] == 'train' for r in records), sum(r['phase'] == 'valid' for r in records))
        if records else 'Incomplete history: only saved checkpoint scores and explicitly sourced terminal observations are available.'
        if scores or observations else 'No completed epoch metrics yet. Curves appear as training progresses.')
    rows = defaultdict(dict)
    for record in records:
        rows[record['epoch']].update({record['phase'] + '/' + key: value for key, value in record['metrics'].items()})
    columns = ['epoch'] + sorted({key for row in rows.values() for key in row})
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(dict(epoch=epoch, **rows[epoch]) for epoch in sorted(rows))
    (folder / 'metrics.csv').write_text(csv_buffer.getvalue())
    configuration_csv = io.StringIO()
    config_writer = csv.DictWriter(configuration_csv, fieldnames=['section', 'path', 'name', 'value', 'source', 'menu', 'effect'])
    config_writer.writeheader()
    config_writer.writerows(dict(row, value=_value_text(row['value'])) for row in catalog)
    (folder / 'full_configuration.csv').write_text(configuration_csv.getvalue())
    png = _plot(records, scores, observations, config['algo_name'])
    (folder / 'loss_curves.png').write_bytes(png)
    name = job['name']
    lines = ['# Training report: ' + name, '', 'Status: ' + job['status'], '', coverage,
             '', 'Datasets: ' + (', '.join(details['datasets']) or 'Unavailable'),
             'Training recordings: {} | Validation recordings: {}'.format(details['train_count'], details['valid_count']),
             '', '![Training graphs](loss_curves.png)', '', '## Findings', '']
    lines.extend('- ' + note for note in notes)
    lines.extend(['', '## Possible improvements to test', '',
                  'These are hypotheses and controlled experiments, not a diagnosis from loss alone.', ''])
    lines.extend('- ' + action for action in actions)
    lines.extend(['', '## Saved hyperparameters', '', '| Setting | Value |', '| --- | --- |'])
    lines.extend('| {} | {} |'.format(key, value) for key, value in settings)
    lines.extend(['', '## Full saved configuration', '',
                  'Every saved field is listed below, including inactive and bookkeeping settings. Menu access describes the current editor.',
                  'Legacy rollout fallbacks and frozen-data values are marked separately from values recorded in the run configuration.'])
    grouped_catalog = defaultdict(list)
    for row in catalog:
        grouped_catalog[row['section']].append(row)
    for section, section_rows in grouped_catalog.items():
        lines.extend(['', '### ' + section, '', '| Field | Value | Where to edit | Meaning / provenance |',
                      '| --- | --- | --- | --- |'])
        for row in section_rows:
            clean = lambda value: str(value).replace('|', '\\|').replace('\n', ' ')
            lines.append('| `{}` | {} | {} | {} Source: {}. |'.format(row['path'], clean(_value_text(row['value'])),
                         clean(row['menu']), clean(row['effect']), clean(row['source'])))
    if build_defaults:
        lines.extend(['', '## Additional ACT implementation defaults', '',
            'These current bundled-code defaults are not stored in the run configuration. Historical values cannot be verified from the saved config alone; they are not menu controls.',
            '', '| Implementation setting | Current source default |', '| --- | --- |'])
        lines.extend('| {} | {} |'.format(key, _value_text(value)) for key, value in build_defaults)
    lines.extend(['', '## Checkpoints', '', '| Epoch | Saved best validation loss |', '| --- | --- |'])
    lines.extend('| {} | {:.8g} |'.format(score['epoch'], score['loss']) for score in scores)
    if observations:
        lines.extend(['', 'Additional terminal observations:'])
        lines.extend('- Epoch {}: validation loss {}. Source: {}.'.format(r['epoch'], r['metrics'].get('Loss'), r.get('source', 'recorded observation')) for r in observations)
    lines.extend(['', 'Full scalar metrics: [metrics.csv](metrics.csv).',
                  'Generated: ' + datetime.now(timezone.utc).isoformat(), ''])
    markdown = '\n'.join(lines)
    (folder / 'training_report.md').write_text(markdown)
    summary = ['Model: ' + name, 'Status: ' + job['status'],
               'Datasets: ' + ', '.join(details['datasets']), '', 'Main saved settings:']
    summary.extend('  {}: {}'.format(key, value) for key, value in settings)
    summary.extend(['', 'Learning-rate verification: ' + rate_note, '',
                    'Full saved configuration (including inactive and bookkeeping fields):'])
    for row in catalog:
        summary.append('  {} = {} | {} | {} | {}'.format(row['path'], _value_text(row['value']), row['menu'], row['source'], row['effect']))
    if build_defaults:
        summary.extend(['', 'Current implementation defaults (not recorded in this run):'])
        summary.extend('  {}: {}'.format(key, _value_text(value)) for key, value in build_defaults)
    (folder / 'training_summary.txt').write_text('\n'.join(summary) + '\n')
    escape = lambda value: html.escape(str(value))
    table = ''.join('<tr><th>{}</th><td>{}</td></tr>'.format(escape(k), escape(v)) for k, v in settings)
    catalog_html = '<h2>Full saved configuration</h2><p>Every saved field is included. Inactive fields, legacy fallbacks, and metadata are labeled. Menu access describes the current editor.</p>'
    for section, section_rows in grouped_catalog.items():
        catalog_html += '<details><summary>{} ({} fields)</summary><table><tr><th>Field</th><th>Value</th><th>Where to edit</th><th>Meaning / provenance</th></tr>{}</table></details>'.format(
            escape(section), len(section_rows), ''.join('<tr><td>{}<br><small>{}</small></td><td>{}</td><td>{}</td><td>{}<br><small>{}</small></td></tr>'.format(
                escape(r['name']), escape(r['path']), escape(_value_text(r['value'])), escape(r['menu']), escape(r['effect']), escape(r['source'])) for r in section_rows))
    if build_defaults:
        catalog_html += '<h2>Additional ACT implementation defaults</h2><p>Current bundled-code defaults, not recorded in this run. Historical values cannot be verified from the saved config alone. These are not menu controls.</p><table>{}</table>'.format(
            ''.join('<tr><th>{}</th><td>{}</td></tr>'.format(escape(key), escape(_value_text(value))) for key, value in build_defaults))
    content = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Training report: {name}</title><style>body{{font:16px system-ui;max-width:1100px;margin:35px auto;padding:0 20px;color:#182536;background:#fafbfd}}h1,h2{{color:#153b62}}li{{margin:10px 0;line-height:1.5}}table{{border-collapse:collapse;width:100%;background:white;table-layout:fixed}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #ddd;vertical-align:top;overflow-wrap:anywhere}}img{{width:100%;height:auto}}.note{{padding:16px;background:#fff3d8;border-left:4px solid #a06c00}}small{{color:#536273}}details{{margin:12px 0}}summary{{cursor:pointer;padding:10px;background:#e9f0f7}}</style>
<h1>Training report: {name}</h1><p>Status: {status}</p><p class="note">{coverage}</p>
<p>Datasets: {datasets}<br>Training recordings: {train}; validation recordings: {valid}</p>
<img alt="Training loss, validation gap, components and timing" src="data:image/png;base64,{png}">
<h2>Findings</h2><ul>{notes}</ul><h2>Possible improvements to test</h2>
<p>These are hypotheses and controlled experiments, not a diagnosis from loss alone.</p><ul>{actions}</ul>
<h2>Main saved hyperparameters</h2><table>{settings}</table>{catalog}<h2>Saved best-validation checkpoints</h2><table><tr><th>Epoch</th><th>Validation loss</th></tr>{scores}</table>
<p>ACT and DP losses have different definitions. Compare physical success and cycle time on held-out placements.</p>
<small>Source settings are read from this model's saved configuration, not current menu defaults.</small></html>'''.format(
        name=escape(name), status=escape(job['status']), coverage=escape(coverage), datasets=escape(', '.join(details['datasets'])),
        train=details['train_count'], valid=details['valid_count'], png=base64.b64encode(png).decode(),
        notes=''.join('<li>' + escape(note) + '</li>' for note in notes),
        actions=''.join('<li>' + escape(action) + '</li>' for action in actions), settings=table, catalog=catalog_html,
        scores=''.join('<tr><td>{}</td><td>{:.8g}</td></tr>'.format(s['epoch'], s['loss']) for s in scores))
    report = folder / 'training_report.html'
    report.write_text(content)
    write_metadata(folder / '.training/report.json', dict(coverage=coverage, records=len(records), settings=settings,
                   dataset=details, findings=notes, improvements=actions, configuration=catalog,
                   implementation_defaults=build_defaults, learning_rate_note=rate_note,
                   learning_rate_graph_shown=learning_rate_history(records)[1]))
    return report
