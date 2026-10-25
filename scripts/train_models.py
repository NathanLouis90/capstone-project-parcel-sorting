"""Menu for managing reviewed recordings and training named ACT/DP models."""

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from barcode_scanning.recording import write_metadata
from scripts.training_workflow import (
    TrainingSettings, accepted_episodes, check_training_device, collect_accepted,
    create_training_jobs, dataset_path, delete_rejected, discover_datasets,
    find_models, model_name_valid, move_recordings, next_model_name,
    plan_rejected_deletion, prepare_dataset, run_training_job, split_recordings,
)


class QuitMenu(Exception):
    pass


class BackToMenu(Exception):
    pass


def ask(prompt, input_fn):
    value = input_fn(prompt).strip()
    if value.lower() == 'q':
        raise QuitMenu()
    if value.lower() == 'b':
        raise BackToMenu()
    return value


def choose_numbers(value, count):
    if value.lower() in ('all', 'a'):
        return list(range(count))
    selected = set()
    for part in value.replace(',', ' ').split():
        bounds = part.split('-')
        if len(bounds) == 1:
            selected.add(int(bounds[0]) - 1)
        elif len(bounds) == 2:
            start, end = map(int, bounds)
            if start > end:
                raise ValueError('Enter a range in increasing order')
            selected.update(range(start - 1, end))
        else:
            raise ValueError('Choose numbers such as 1,3 or 1-3')
    if not selected or min(selected) < 0 or max(selected) >= count:
        raise ValueError('Choose numbers from the displayed list')
    return sorted(selected)


def show_datasets(root):
    datasets = discover_datasets(root)
    if not datasets:
        print('No recording datasets found. Record and review episodes first.')
    for index, dataset in enumerate(datasets, 1):
        c = dataset['counts']
        print('{:2d}. {} | accepted {} | rejected {} | unreviewed {} | incomplete {} | invalid {}'.format(
            index, dataset['name'], c.get('accepted', 0), c.get('rejected', 0),
            c.get('unreviewed', 0), c.get('incomplete', 0), c.get('invalid', 0)))
    return datasets


def select_datasets(root, input_fn, multiple=True):
    datasets = show_datasets(root)
    if not datasets:
        raise BackToMenu()
    value = ask('Dataset numbers (for example 1,3), or b to return: ' if multiple
                else 'Dataset number, or b to return: ', input_fn)
    selected = choose_numbers(value, len(datasets))
    if not multiple and len(selected) != 1:
        raise ValueError('Choose one dataset')
    return [datasets[index] for index in selected]


def delete_action(root, input_fn):
    datasets = select_datasets(root, input_fn)
    plans = [plan_rejected_deletion(dataset['path']) for dataset in datasets]
    count = sum(len(plan['episodes']) for plan in plans)
    if not count:
        print('There are no rejected recordings in these datasets.')
        return
    for dataset, plan in zip(datasets, plans):
        print('{}: delete {} rejected recordings and their matching old conversions/videos.'.format(
            dataset['name'], len(plan['episodes'])))
    print('This permanently deletes the files. It does not create a quarantine.')
    if ask('Type DELETE to permanently remove these {} recordings: '.format(count), input_fn) != 'DELETE':
        print('Cancelled.')
        return
    for plan in plans:
        delete_rejected(plan)
    print('Deleted {} rejected recordings.'.format(count))


def move_action(root, input_fn):
    source = select_datasets(root, input_fn, multiple=False)[0]
    episodes = accepted_episodes(source['path'])
    if not episodes:
        raise ValueError('The source has no accepted recordings to move')
    print('{} has {} accepted recordings.'.format(source['name'], len(episodes)))
    print('1. Keep the earliest N accepted recordings here; move the overflow\n'
          '2. Move N newest accepted recordings\n3. Select recordings individually')
    method = ask('Choose how to move [1]: ', input_fn) or '1'
    if method == '1':
        keep = int(ask('How many accepted recordings should remain? [50]: ', input_fn) or '50')
        if keep < 0:
            raise ValueError('Count must be nonnegative')
        selected = episodes[keep:]
    elif method == '2':
        count = int(ask('How many newest accepted recordings should move? ', input_fn))
        if not 1 <= count <= len(episodes):
            raise ValueError('Choose a count from 1 through {}'.format(len(episodes)))
        selected = episodes[-count:]
    elif method == '3':
        for index, episode in enumerate(episodes, 1):
            print('{:3d}. {}'.format(index, episode.name))
        selected = [episodes[i] for i in choose_numbers(ask('Recording numbers: ', input_fn), len(episodes))]
    else:
        raise ValueError('Choose 1, 2, or 3')
    if not selected:
        print('No overflow to move.')
        return
    print('Existing destinations:')
    destinations = [d for d in discover_datasets(root) if d['name'] != source['name']]
    for index, dataset in enumerate(destinations, 1):
        print('{}. {}'.format(index, dataset['name']))
    value = ask('Destination number, or type a dataset name to create it automatically: ', input_fn)
    destination = destinations[int(value) - 1]['name'] if value.isdecimal() and 1 <= int(value) <= len(destinations) else value
    dataset_path(root, destination)
    print('Move {} accepted recordings from {} to {}. Destination folders are automatic.'.format(
        len(selected), source['name'], destination))
    if ask('Type MOVE to apply: ', input_fn) != 'MOVE':
        print('Cancelled.')
        return
    moved = move_recordings(root, source['name'], destination, [p.name for p in selected])
    print('Moved {} recordings. {} accepted remain in {}.'.format(moved, len(episodes) - moved, source['name']))


ALGORITHM_LABELS = {'act': 'ACT', 'diffusion_policy': 'DP'}
SHARED_SPLIT_FIELDS = ('validation_percent', 'seed')
ACT_FIELDS = [
    ('act_kl_weight', 'ACT KL weight', float), ('act_hidden_dim', 'ACT hidden dimension', int),
    ('act_feedforward_dim', 'ACT feedforward dimension', int), ('act_encoder_layers', 'ACT encoder layers', int),
    ('act_decoder_layers', 'ACT decoder layers', int), ('act_heads', 'ACT attention heads', int),
    ('act_latent_dim', 'ACT latent dimension', int), ('act_pretrained', 'ACT pretrained image backbone', bool),
]
DP_FIELDS = [
    ('dp_observation_length', 'DP observation history', int),
    ('dp_action_length', 'DP executed action horizon', int),
    ('dp_unet_dimensions', 'DP U-Net dimensions (comma-separated)', list),
    ('dp_training_diffusion_steps', 'DP training diffusion steps', int),
    ('dp_inference_diffusion_steps', 'DP inference diffusion steps', int),
]


def load_hyperparameter_defaults(preferences):
    if not Path(preferences).exists():
        return {algorithm: TrainingSettings() for algorithm in ALGORITHM_LABELS}
    saved = json.loads(Path(preferences).read_text())
    # Existing single-profile preferences seed both algorithms without losing edits.
    profiles = saved['algorithms'] if saved.get('version') == 2 else {
        algorithm: saved for algorithm in ALGORITHM_LABELS}
    defaults = {algorithm: TrainingSettings(**profiles[algorithm]) for algorithm in ALGORITHM_LABELS}
    for algorithm, settings in defaults.items():
        settings.validate(algorithm)
    if any(getattr(defaults['act'], key) != getattr(defaults['diffusion_policy'], key)
           for key in SHARED_SPLIT_FIELDS):
        raise ValueError('ACT and DP must share the validation percentage and split seed')
    return defaults


def save_hyperparameter_defaults(preferences, defaults):
    write_metadata(preferences, {'version': 2, 'algorithms': {
        algorithm: asdict(settings) for algorithm, settings in defaults.items()}})


def hyperparameter_fields(algorithm, advanced=False):
    if advanced:
        return (ACT_FIELDS if algorithm == 'act' else DP_FIELDS) + [
            ('save_every', 'Save a periodic checkpoint every N epochs', int),
            ('image_size', 'Image size (square pixels)', int),
            ('device', 'Training device (cuda or cpu)', str),
        ]
    return [
        ('epochs', 'Epochs', int), ('batch_size', 'Batch size', int),
        ('act_learning_rate' if algorithm == 'act' else 'dp_learning_rate', 'Learning rate', float),
        ('train_steps', 'Training batches per epoch', int),
        ('validation_steps', 'Validation batches per epoch', int),
        ('prediction_length', 'ACT chunk length' if algorithm == 'act' else 'DP prediction horizon', int),
        ('validation_percent', 'Validation percentage (shared split)', float),
        ('seed', 'Random seed (shared split)', int),
    ]


def edit_hyperparameters(defaults, preferences, input_fn):
    print('\nEdit hyperparameter defaults:\n1. ACT\n2. DP')
    choice = ask('Algorithm number, or b to return: ', input_fn).lower()
    algorithm = {'1': 'act', 'act': 'act', '2': 'diffusion_policy', 'dp': 'diffusion_policy'}.get(choice)
    if algorithm is None:
        raise ValueError('Choose ACT (1) or DP (2)')
    return edit_algorithm_hyperparameters(defaults, algorithm, preferences, input_fn)


def edit_algorithm_hyperparameters(defaults, algorithm, preferences, input_fn, advanced=False):
    fields = hyperparameter_fields(algorithm, advanced)
    while True:
        settings = defaults[algorithm]
        print('\n{} hyperparameter defaults:'.format(ALGORITHM_LABELS[algorithm]))
        for index, (key, label, _) in enumerate(fields, 1):
            print('{}. {}: {}'.format(index, label, getattr(settings, key)))
        if not advanced:
            print('a. Advanced {} settings'.format(ALGORITHM_LABELS[algorithm]))
        value = ask('Setting number, Enter to finish' + (', or a for advanced: ' if not advanced else ': '), input_fn)
        if not value:
            return defaults
        if value.lower() == 'a' and not advanced:
            edit_algorithm_hyperparameters(defaults, algorithm, preferences, input_fn, True)
            continue
        try:
            index = int(value) - 1
            if not 0 <= index < len(fields):
                raise ValueError('Choose a displayed setting')
            key, label, kind = fields[index]
            value = ask('{}: '.format(label), input_fn)
            if kind is bool:
                if value.lower() not in ('yes', 'no', 'true', 'false', '1', '0'):
                    raise ValueError('Enter yes or no')
                value = value.lower() in ('yes', 'true', '1')
            elif kind is list:
                value = [int(part) for part in value.replace(',', ' ').split()]
            else:
                value = kind(value)
            candidate = replace(settings, **{key: value})
            candidate.validate(algorithm)
            defaults[algorithm] = candidate
            if key in SHARED_SPLIT_FIELDS:
                for other in defaults:
                    defaults[other] = replace(defaults[other], **{key: value})
                print('Updated the shared split for ACT and DP.')
            save_hyperparameter_defaults(preferences, defaults)
        except ValueError as error:
            print(error)


def train_action(root, models, defaults, preferences, input_fn):
    datasets = select_datasets(root, input_fn)
    projects = [dataset['path'] for dataset in datasets]
    entries = collect_accepted(projects)
    medium = entries[0]['medium']
    print('1. ACT\n2. Diffusion Policy\n3. Both, using the same recordings and split')
    choice = ask('Train which models? [3]: ', input_fn) or '3'
    algorithms = {'1': ('act',), '2': ('diffusion_policy',), '3': ('act', 'diffusion_policy')}.get(choice)
    if algorithms is None:
        raise ValueError('Choose 1, 2, or 3')
    names = {}
    for algorithm in algorithms:
        default = next_model_name(models, algorithm, medium)
        name = ask('{} model name [{}]: '.format('ACT' if algorithm == 'act' else 'DP', default), input_fn) or default
        if not model_name_valid(name) or (Path(models) / name).exists():
            raise ValueError('Choose a new model name using letters, numbers, periods, underscores, and hyphens')
        names[algorithm] = name
    if len(set(names.values())) != len(names):
        raise ValueError('Give ACT and DP different model names')
    while True:
        for algorithm in algorithms:
            defaults[algorithm].validate(algorithm)
        settings = defaults[algorithms[0]]
        split = split_recordings(entries, settings.validation_percent, settings.seed)
        print('\nDatasets: ' + ', '.join(d['name'] for d in datasets))
        print('{} accepted recordings: {} training / {} validation.'.format(
            len(entries), len(split['train']), len(split['valid'])))
        print('Models: ' + ', '.join(names.values()))
        for algorithm in algorithms:
            model_settings = defaults[algorithm]
            print('{}: epochs {} | batch size {} | batches/epoch {} | learning rate {} | {} {} | device {}'.format(
                ALGORITHM_LABELS[algorithm], model_settings.epochs, model_settings.batch_size, model_settings.train_steps,
                model_settings.act_learning_rate if algorithm == 'act' else model_settings.dp_learning_rate,
                'chunk length' if algorithm == 'act' else 'prediction horizon',
                model_settings.prediction_length, model_settings.device))
        answer = ask('Type TRAIN to prepare and train, e to edit settings, or b to return: ', input_fn)
        if answer.lower() == 'e':
            defaults = edit_hyperparameters(defaults, preferences, input_fn)
            continue
        if answer != 'TRAIN':
            continue
        for algorithm in algorithms:
            check_training_device(defaults[algorithm])
        prepared_by_size, jobs = {}, []
        for algorithm in algorithms:
            model_settings = defaults[algorithm]
            if model_settings.image_size not in prepared_by_size:
                prepared_by_size[model_settings.image_size] = prepare_dataset(
                    projects, model_settings, Path(root) / '.training_cache', algorithm=algorithm)
        splits = [json.loads((prepared / 'split.json').read_text()) for prepared in prepared_by_size.values()]
        if any(split != splits[0] for split in splits[1:]):
            raise ValueError('Recordings changed during preparation; stop recording and retry')
        for algorithm in algorithms:
            model_settings = defaults[algorithm]
            jobs.extend(create_training_jobs(prepared_by_size[model_settings.image_size], model_settings,
                                             {algorithm: names[algorithm]}, models))
        for job in jobs:
            print('\nStarting ' + job['name'])
            run_training_job(job)
        print('Training finished. Use Models and saved settings to inspect the results.')
        return defaults


def model_action(models, input_fn):
    found = find_models(models)
    if not found:
        print('No models found yet.')
        return
    for index, job in enumerate(found, 1):
        print('{}. {} | {}'.format(index, job['name'], job['status']))
    selected = choose_numbers(ask('Model number: ', input_fn), len(found))
    if len(selected) != 1:
        raise ValueError('Choose one model')
    job = found[selected[0]]
    summary = Path(job['folder']) / 'training_summary.txt'
    if summary.exists():
        print(summary.read_text())
    else:
        config = job['legacy_config']
        print('Existing model: ' + job['name'])
        print('Algorithm: ' + config['algo_name'])
        for key, label in (('num_epochs', 'Epochs'), ('batch_size', 'Batch size'),
                           ('seq_length', 'Sequence length'), ('frame_stack', 'Observation history'),
                           ('seed', 'Random seed')):
            print('{}: {}'.format(label, config['train'].get(key)))
        print('Learning rate: {}'.format(config['algo']['optim_params']['policy']['learning_rate']['initial']))
        print('Training batches per epoch: {}'.format(config['experiment']['epoch_every_n_steps']))
        print('Validation batches per epoch: {}'.format(config['experiment']['validation_epoch_every_n_steps']))
        details = config['algo'].get('act', {}) if config['algo_name'] == 'act' else config['algo'].get('horizon', {})
        for key, value in details.items():
            print('{}: {}'.format(key.replace('_', ' ').capitalize(), value))
    print('Status: {} | Most recent completed training epoch: {}'.format(job['status'], job.get('epoch', 'see run output')))
    if 'validation_loss' in job:
        print('Validation loss: {:.5g} | Best: {:.5g}'.format(job['validation_loss'], job['best_validation_loss']))
    for label, key in (('Best checkpoint', 'best_checkpoint'), ('Latest saved checkpoint', 'latest_checkpoint')):
        if key in job:
            print('{}: {} (epoch {})'.format(label, job[key], job[key + '_epoch']))
    from scripts.training_report import generate_training_report
    report = generate_training_report(job)
    print('Training report (graphs, actual hyperparameters, findings): ' + str(report))
    if job['status'] == 'ready' and ask('This model is prepared but not started. Type TRAIN to start, or Enter to return: ', input_fn) == 'TRAIN':
        run_training_job(job)


def train_frozen_action(models, defaults, preferences, input_fn):
    """Train a comparison model on exactly the selected run's frozen data."""
    from scripts.training_report import dataset_details, saved_config
    found = find_models(models)
    if not found:
        raise ValueError('Train a model first, then reuse its frozen dataset here')
    for index, job in enumerate(found, 1):
        print('{}. {}'.format(index, job['name']))
    selected = choose_numbers(ask('Use which model\'s frozen recordings and split? ', input_fn), len(found))
    if len(selected) != 1:
        raise ValueError('Choose one source model')
    source = found[selected[0]]
    source_config = saved_config(source)
    details = dataset_details(source_config)
    if not details.get('split') or not details.get('image_size'):
        raise ValueError('This model does not have an available frozen parcel dataset')
    dataset = Path(details['path'])
    split_file = Path(details.get('split_file') or dataset.with_suffix('.split.json'))
    if not split_file.is_file() or json.loads(split_file.read_text()) != details['split']:
        raise ValueError('The saved split is missing or differs from the frozen dataset')
    if details['image_size'][0] != details['image_size'][1]:
        raise ValueError('The frozen dataset must have square images')
    print('1. ACT\n2. DP\n3. Both')
    default = '2' if source_config['algo_name'] == 'act' else '1'
    choice = ask('Train which algorithm? [{}]: '.format(default), input_fn) or default
    algorithms = {'1': ('act',), '2': ('diffusion_policy',), '3': ('act', 'diffusion_policy')}.get(choice)
    if algorithms is None:
        raise ValueError('Choose 1, 2, or 3')
    names = {}
    for algorithm in algorithms:
        default = next_model_name(models, algorithm, details['medium'])
        name = ask('{} model name [{}]: '.format(ALGORITHM_LABELS[algorithm], default), input_fn) or default
        if not model_name_valid(name) or (Path(models) / name).exists() or name in names.values():
            raise ValueError('Choose a new, different model name for each algorithm')
        names[algorithm] = name
    while True:
        effective = {algorithm: replace(defaults[algorithm], image_size=details['image_size'][0],
                     seed=int(details['split'].get('seed', source_config['train']['seed'])),
                     validation_percent=100 * details['valid_count'] / (details['train_count'] + details['valid_count']))
                     for algorithm in algorithms}
        print('\nFrozen data from {}: {} training / {} validation recordings.'.format(
            source['name'], details['train_count'], details['valid_count']))
        print('Datasets: ' + ', '.join(details['datasets']))
        print('The original split, seed, and image size are retained for comparison.')
        for algorithm, settings in effective.items():
            settings.validate(algorithm)
            print('{}: {} | epochs {} | batch {} | learning rate {} | prediction length {}'.format(
                ALGORITHM_LABELS[algorithm], names[algorithm], settings.epochs, settings.batch_size,
                settings.act_learning_rate if algorithm == 'act' else settings.dp_learning_rate, settings.prediction_length))
        answer = ask('Type TRAIN to start, e to edit hyperparameter defaults, or b to return: ', input_fn)
        if answer.lower() == 'e':
            defaults = edit_hyperparameters(defaults, preferences, input_fn)
            continue
        if answer != 'TRAIN':
            continue
        for settings in effective.values():
            check_training_device(settings)
        jobs = []
        for algorithm, settings in effective.items():
            jobs.extend(create_training_jobs(dataset.parent, settings, {algorithm: names[algorithm]}, models,
                        dataset=dataset, split_file=split_file))
        for job in jobs:
            run_training_job(job)
        return defaults


def run_menu(root=ROOT / 'datasets', models=ROOT / 'ckpt', input_fn=None):
    input_fn = input if input_fn is None else input_fn
    preferences = Path(root) / '.training_cache/preferences.json'
    defaults = {algorithm: TrainingSettings() for algorithm in ALGORITHM_LABELS}
    print('Review episodes as usual, then use this menu. Stop recording before changing datasets.')
    while True:
        # Edits are saved immediately, including when the user returns with b.
        if preferences.exists():
            try:
                defaults = load_hyperparameter_defaults(preferences)
            except (OSError, TypeError, ValueError, KeyError) as error:
                print('Saved defaults could not be loaded; keeping valid defaults: ' + str(error))
        print('\n1. Show datasets and review counts\n2. Delete rejected recordings permanently\n'
              '3. Move recordings (destination folders are automatic)\n4. Train ACT / DP / both\n'
              '5. Edit hyperparameter defaults\n6. Models, reports and saved settings\n'
              '7. Train using an existing model\'s frozen dataset and split\nq. Quit')
        try:
            choice = ask('Choose: ', input_fn)
            if choice == '1':
                show_datasets(root)
            elif choice == '2':
                delete_action(root, input_fn)
            elif choice == '3':
                move_action(root, input_fn)
            elif choice == '4':
                defaults = train_action(root, models, defaults, preferences, input_fn)
            elif choice == '5':
                defaults = edit_hyperparameters(defaults, preferences, input_fn)
            elif choice == '6':
                model_action(models, input_fn)
            elif choice == '7':
                defaults = train_frozen_action(models, defaults, preferences, input_fn)
            else:
                print('Choose a listed action or q.')
        except BackToMenu:
            continue
        except (QuitMenu, EOFError):
            return 0
        except KeyboardInterrupt:
            print('\nStopped. Completed training outputs are preserved.')
            return 130
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            print('Could not complete that action: ' + str(error))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Manage reviewed recordings and train named ACT/DP models from one menu.')
    parser.parse_args(argv)
    return run_menu()


if __name__ == '__main__':
    sys.exit(main())
