"""Plan, audit and reversibly curate reviewed local demonstration projects.

Episode metadata is never rewritten. Converted training files stay in their
original project except when quarantined together with a rejected recording.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
import pickletools
from pathlib import Path
import shutil
import sys
import uuid

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from barcode_scanning.barcode_scanning_config import RECORDING
from experiments.experiments_config import CONTROL
from scripts.dataset_integrity import require_rollout_opt_in
from scripts.scripts_config import PREPARE_ACT_DATASETS

CAMERAS = {'top': 'topImg', 'left_wrist': 'leftImg', 'right_wrist': 'rightImg'}


def metadata(episode):
    value = json.loads((episode / RECORDING['metadata_filename']).read_text())
    if not isinstance(value, dict):
        raise ValueError('Metadata must be an object: {}'.format(episode))
    return value


def episodes(project, quarantined=False):
    folder = project / ('rejected_data' if quarantined else 'collect_data')
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith('.')
                  and (not quarantined or p.name != 'converted'))


def select(project, identifiers=None, quarantined=False):
    found = episodes(project, quarantined)
    if identifiers is None:
        return found
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate episode IDs in selection')
    if any(Path(i).name != i or i in ('.', '..', 'converted') for i in identifiers):
        raise ValueError('Use episode folder names, not paths')
    missing = set(identifiers) - {p.name for p in found}
    if missing:
        raise ValueError('Unknown episode IDs in {}: {}'.format(project, ', '.join(sorted(missing))))
    return [p for p in found if p.name in identifiers]


def hashes(path):
    """Hash every regular file and refuse symlinks, including directory links."""
    if path.is_symlink():
        raise ValueError('Symlink is not supported: {}'.format(path))
    files = [path] if path.is_file() else sorted(path.rglob('*'))
    result = {}
    for item in files:
        if item.is_symlink():
            raise ValueError('Symlink is not supported: {}'.format(item))
        if not item.is_file():
            if not item.is_dir():
                raise ValueError('Only regular files and directories are supported: {}'.format(item))
            continue
        digest = hashlib.sha256()
        with item.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        result[str(item.relative_to(path)) if item != path else path.name] = digest.hexdigest()
    return result


def nearest_parent(path):
    while not path.exists():
        path = path.parent
    return path


def settings(project, registry):
    if project.name not in registry:
        raise ValueError('Unregistered project: {}; add its exact name to PREPARE_ACT_DATASETS["projects"]'.format(project.name))
    return registry[project.name]


def signature(episode, warnings):
    m = metadata(episode)
    if m.get('episode_id') != episode.name:
        raise ValueError('episode_id differs from folder name: {}'.format(episode))
    if not m.get('recording_complete') or not m.get('frame_count', 0):
        raise ValueError('Incomplete recording: {}'.format(episode))
    if m.get('policy_stage') not in ('A', 'B') or m.get('medium') not in ('poly_mailer', 'carton', 'envelope'):
        raise ValueError('Missing policy_stage or medium: {}'.format(episode))
    ids = {p.stem for p in (episode / 'observation').glob('*.pkl')}
    if any(not identifier.isdigit() for identifier in ids):
        raise ValueError('Observation frame names must be numeric: {}'.format(episode))
    if len(ids) != m['frame_count']:
        raise ValueError('frame_count differs from observation files: {}'.format(episode))
    cameras = []
    for camera, folder in CAMERAS.items():
        if (episode / folder).is_dir():
            cameras.append(camera)
            if {p.stem for p in (episode / folder).glob('*.jpg')} != ids:
                raise ValueError('camera set/frame identifiers mismatch: {}'.format(episode))
    rate = m.get('control_period_ms')
    if rate is None:
        rate = CONTROL['control_period_ms']
        warnings.add('{}: legacy metadata has no control_period_ms; assume configured {} ms. '
                     'Measured playback rate still needs review.'.format(episode, rate))
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
        raise ValueError('Invalid recording rate: {}'.format(episode))
    destination = m.get('destination') or m.get('scan') or {}
    bin_index = destination.get('bin_index') if m['policy_stage'] == 'B' else None
    if m['policy_stage'] == 'B' and (type(bin_index) is not int or bin_index not in (0, 1)):
        raise ValueError('Invalid bin_index: {}'.format(episode))
    return dict(policy_stage=m['policy_stage'], medium=m['medium'], bin_index=bin_index,
                camera_names=sorted(cameras), control_period_ms=rate, frames=len(ids))


def compatible(actual, expected, episode):
    for key in ('policy_stage', 'medium', 'bin_index', 'camera_names', 'control_period_ms'):
        wanted = expected.get(key, CONTROL['control_period_ms'] if key == 'control_period_ms' else None)
        if key == 'camera_names':
            wanted = sorted(wanted or CAMERAS)
        if actual[key] != wanted:
            raise ValueError('{} mismatch for {}: recorded {!r}, expected {!r}'.format(key, episode, actual[key], wanted))
    if actual['frames'] > expected['episode_len']:
        raise ValueError('episode_len exceeded for {}: {} > {}'.format(episode, actual['frames'], expected['episode_len']))


def accepted(project):
    return [p for p in episodes(project) if metadata(p).get('review_status') == 'accepted']


def ordered(paths):
    def key(path):
        started = metadata(path).get('started_at')
        if not isinstance(started, (float, int)) or not math.isfinite(started):
            raise ValueError('Missing/invalid started_at for deterministic selection: {}'.format(path))
        return started, path.name, str(path)
    return sorted(paths, key=key)


@dataclass
class Operation:
    source: Path
    destination: Path
    copy: bool = False
    sha256: dict = field(default_factory=dict)


@dataclass
class Plan:
    command: str
    operations: list = field(default_factory=list)
    projects: set = field(default_factory=set)
    warnings: set = field(default_factory=set)
    new_projects: set = field(default_factory=set)

    def add(self, source, destination, copy=False):
        source, destination = Path(source), Path(destination)
        if not source.exists():
            raise ValueError('Missing source: {}'.format(source))
        if destination.exists() or destination.is_symlink() or any(o.destination == destination for o in self.operations):
            raise ValueError('episode_id/path collision: {}'.format(destination))
        if source.is_symlink() or any(p.is_symlink() for p in (*source.parents, *destination.parents)):
            raise ValueError('Symlink is not supported: {}'.format(destination))
        if not copy and source.stat().st_dev != nearest_parent(destination.parent).stat().st_dev:
            raise ValueError('Cross-filesystem move refused; use a copy merge: {}'.format(source))
        self.operations.append(Operation(source, destination, copy, hashes(source)))

    def show(self):
        print('{}: {} operations'.format(self.command, len(self.operations)))
        for op in self.operations:
            print('{} {}\n  to {}'.format('COPY' if op.copy else 'MOVE', op.source, op.destination))
        for project in sorted(self.projects):
            print('MARK STALE: {}'.format(project / 'train_data' / 'STALE.json'))
        for project in sorted(self.audit_projects()):
            print('APPEND AUDIT: {}'.format(project / 'curation_log.jsonl'))
        for warning in sorted(self.warnings):
            print('[Warn]: ' + warning)

    def audit_projects(self):
        return self.projects | {op.source.parent.parent for op in self.operations
                                if op.source.parent.name == 'collect_data'}


def converted(project):
    """Use embedded episode IDs, never numeric HDF5 indices, for attribution."""
    import h5py
    index = {}
    for path in sorted((project / 'train_data').glob('*.hdf5')):
        with h5py.File(str(path), 'r') as stream:
            text = stream.attrs.get('episode_metadata_json')
            if text is None:
                raise ValueError('Converted file lacks episode provenance: {}'.format(path))
            identifier = json.loads(text).get('episode_id')
            if not identifier:
                raise ValueError('Converted file lacks episode_id: {}'.format(path))
            index.setdefault(identifier, []).append(path)
    return index


def add_quarantine(plan, project, paths):
    index = converted(project)
    for path in paths:
        if metadata(path).get('review_status') != 'rejected':
            raise ValueError('Quarantine requires rejected review status: {}'.format(path))
        plan.add(path, project / 'rejected_data' / path.name)
        for artifact in index.get(path.name, []):
            plan.add(artifact, project / 'rejected_data' / 'converted' / 'train_data' / artifact.name)
        for artifact in sorted((project / 'output_videos').glob(path.name + '_video*.mp4')):
            plan.add(artifact, project / 'rejected_data' / 'converted' / 'output_videos' / artifact.name)
    if paths:
        plan.projects.add(project)


def add_restore(plan, project, paths):
    import h5py
    index = {}
    for path in sorted((project / 'rejected_data' / 'converted' / 'train_data').glob('*.hdf5')):
        with h5py.File(str(path), 'r') as stream:
            identifier = json.loads(stream.attrs['episode_metadata_json'])['episode_id']
        index.setdefault(identifier, []).append(path)
    for path in paths:
        plan.add(path, project / 'collect_data' / path.name)
        for artifact in index.get(path.name, []):
            plan.add(artifact, project / 'train_data' / artifact.name)
        videos = project / 'rejected_data' / 'converted' / 'output_videos'
        for artifact in sorted(videos.glob(path.name + '_video*.mp4')):
            plan.add(artifact, project / 'output_videos' / artifact.name)
    if paths:
        plan.projects.add(project)


def add_transfer(plan, sources, destination, registry, copy=False, allow_rollouts=False):
    expected = settings(destination, registry)
    # Check retained episodes too; destination folder names do not prove compatibility.
    for path in episodes(destination):
        compatible(signature(path, plan.warnings), expected, path)
    for source in sources:
        m = metadata(source)
        if m.get('review_status') != 'accepted':
            raise ValueError('Transfer/merge requires accepted review status, got {}: {}'.format(m.get('review_status'), source))
        require_rollout_opt_in(m, destination, allow_rollouts)
        actual = signature(source, plan.warnings)
        source_project = source.parent.parent
        if source_project == destination:
            raise ValueError('Source and destination must differ: {}'.format(destination))
        if source_project.name in registry:
            compatible(actual, registry[source_project.name], source)
        compatible(actual, expected, source)
        target = destination / 'collect_data' / source.name
        if (destination / 'rejected_data' / source.name).exists():
            raise ValueError('episode_id collision with quarantined episode: {}'.format(source.name))
        plan.add(source, target, copy)
        plan.projects.add(destination)
        # Copy merges also append provenance at the source, but do not stale its data.
        if not copy:
            plan.projects.add(source_project)


def reference_warnings(plan, root):
    """Read only metadata/manifests; never alter trained data or source links."""
    raw = [op for op in plan.operations if op.source.parent.name == 'collect_data']
    if not raw:
        return
    moved = {str(op.source / RECORDING['metadata_filename']): op for op in raw if not op.copy}
    for path in root.glob('*/collect_data/*/' + RECORDING['metadata_filename']):
        m = json.loads(path.read_text())
        link = m.get('source_metadata_path')
        if link and str(Path(link).expanduser().resolve()) in moved:
            op = moved[str(Path(link).expanduser().resolve())]
            plan.warnings.add('Policy B {} keeps source_metadata_path {}; A moves to {}. '
                              'Link is preserved and may need the curation log to resolve.'.format(path.parent, link, op.destination))
    tokens = {str(op.source) for op in raw} | {op.source.name for op in raw}
    for op in raw:
        m = metadata(op.source)
        if m.get('source_metadata_path'):
            plan.warnings.add('{}: Policy B source link stays unchanged: {}'.format(op.source.name, m['source_metadata_path']))
        if (op.source.parent.parent / 'train_data').exists():
            plan.warnings.add('{}: existing conversions/splits/checkpoints are not rebuilt; use fresh training outputs.'.format(op.source.parent.parent))
    # Frozen split files identify converted source paths rather than raw IDs.
    for project in {op.source.parent.parent for op in raw}:
        for identifier, paths in converted(project).items():
            if identifier in tokens:
                for path in paths:
                    tokens.update((str(path.resolve()), project.name + '/' + path.name))
    for path in root.rglob('*.json'):
        if any(part in ('collect_data', 'rejected_data', 'train_data', 'conversion_logs') for part in path.relative_to(root).parts):
            continue
        text = path.read_text()
        if any(token in text for token in tokens):
            plan.warnings.add('Frozen dataset/split/config references selected episodes: {}; left unchanged.'.format(path))
    # Robomimic embeds original episode metadata on each demo.
    import h5py
    for path in root.rglob('*.hdf5'):
        if any(part in ('collect_data', 'rejected_data', 'train_data') for part in path.relative_to(root).parts):
            continue
        with h5py.File(str(path), 'r') as stream:
            if 'data' in stream:
                for demo in stream['data'].values():
                    if any(token in str(dict(demo.attrs)) for token in tokens):
                        plan.warnings.add('Existing robomimic dataset includes selected episodes: {}; left unchanged.'.format(path))
                        break
    source_names = {op.source.parent.parent.name for op in raw}
    for path in (root.parent / 'ckpt').rglob('config.pkl'):
        # Inspect pickle strings without unpickling model objects or importing
        # hardware/model modules. Configs often name a project rather than IDs.
        strings = [arg for _, arg, _ in pickletools.genops(path.read_bytes()) if isinstance(arg, str)]
        if any(name in value for name in source_names for value in strings):
            plan.warnings.add('Checkpoint config references an affected source project: {}; left unchanged.'.format(path))


def execute(plan, dry_run=False, yes=False, input_fn=input):
    """Preflight everything, then rename, rolling back a failed transaction."""
    plan.show()
    if dry_run or not plan.operations:
        return False
    if not yes and input_fn('Apply this complete plan? [y/N] ').strip().lower() not in ('y', 'yes'):
        print('Cancelled; no files changed.')
        return False
    done, created, saved_files, locks = [], [], {}, []

    def mkdir(path):
        if path.exists():
            return
        mkdir(path.parent)
        path.mkdir()
        created.append(path)

    def remember(path):
        saved_files[path] = path.read_bytes() if path.exists() else None

    try:
        # Lock directory descriptors so a failed lock never touches an audit log.
        audit_projects = plan.audit_projects()
        for project in sorted(audit_projects):
            if project in plan.new_projects and project.exists():
                raise ValueError('Merge destination already exists: {}'.format(project))
            mkdir(project)
            descriptor = os.open(str(project), os.O_RDONLY)
            locks.append(descriptor)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for project in sorted(audit_projects):
            remember(project / 'curation_log.jsonl')
        for op in plan.operations:
            if op.destination.exists() or op.destination.is_symlink():
                raise ValueError('episode_id/path collision: {}'.format(op.destination))
            if hashes(op.source) != op.sha256:
                raise ValueError('Source changed since planning: {}'.format(op.source))
        # Copy first so disk-space failures happen before any source rename.
        for op in sorted(plan.operations, key=lambda op: not op.copy):
            mkdir(op.destination.parent)
            if op.copy:
                done.append(op)
                if op.source.is_dir():
                    shutil.copytree(str(op.source), str(op.destination))
                else:
                    shutil.copy2(str(op.source), str(op.destination))
                if hashes(op.destination) != op.sha256:
                    raise OSError('Copied content hash mismatch: {}'.format(op.destination))
            else:
                os.rename(str(op.source), str(op.destination))
                done.append(op)
        stamp = datetime.now(timezone.utc).isoformat()
        transaction = uuid.uuid4().hex
        record = dict(timestamp=stamp, transaction_id=transaction, command=plan.command,
                      episode_ids=[op.source.name for op in plan.operations if op.source.is_dir()
                                   or op.destination.is_dir()], operations=[dict(
                          source=str(op.source), destination=str(op.destination),
                          operation='copy' if op.copy else 'move', sha256=op.sha256) for op in plan.operations])
        for project in sorted(plan.projects):
            marker = project / 'train_data' / 'STALE.json'
            mkdir(marker.parent)
            remember(marker)
            marker.write_text(json.dumps(dict(timestamp=stamp, transaction_id=transaction,
                                              reason='Raw episode set changed: ' + plan.command), indent=2) + '\n')
        for project in sorted(audit_projects):
            with (project / 'curation_log.jsonl').open('a') as handle:
                handle.write(json.dumps(record, sort_keys=True) + '\n')
                handle.flush()
                os.fsync(handle.fileno())
    except BaseException:
        for op in reversed(done):
            if op.copy:
                if op.destination.is_dir():
                    shutil.rmtree(str(op.destination))
                elif op.destination.exists():
                    op.destination.unlink()
            else:
                os.rename(str(op.destination), str(op.source))
        for path, content in saved_files.items():
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(content)
        for path in reversed(created):
            path.rmdir()
        raise
    finally:
        for descriptor in locks:
            os.close(descriptor)
    print('Applied {} operations. Episode metadata unchanged; rebuild stale training folders.'.format(len(plan.operations)))
    return True


def project_status(project):
    counts = Counter(accepted=0, rejected=0, unreviewed=0, invalid=0)
    details, issues = Counter(), []
    for path in episodes(project):
        try:
            m = metadata(path)
            status = m.get('review_status', 'unreviewed')
            counts[status if status in ('accepted', 'rejected', 'unreviewed') else 'invalid'] += 1
            details['stage={}, medium={}, bin={}'.format(m.get('policy_stage'), m.get('medium'),
                                                       (m.get('destination') or {}).get('bin_index'))] += 1
            if m.get('episode_id') != path.name:
                issues.append('episode_id differs from folder name: ' + path.name)
            expected = PREPARE_ACT_DATASETS['projects'].get(project.name)
            if expected:
                for field in ('policy_stage', 'medium'):
                    if m.get(field) != expected[field]:
                        issues.append('{} mismatch: {} records {!r}, project expects {!r}'.format(
                            field, path.name, m.get(field), expected[field]))
        except (OSError, ValueError) as error:
            counts['invalid'] += 1
            issues.append('{}: {}'.format(path.name, error))
    counts['quarantined'] = len(episodes(project, True))
    result = dict(project=str(project), counts=dict(counts), stages_media_bins=dict(details),
                  train_data_stale=any((project / 'train_data' / name).exists() for name in ('STALE.json', 'BUILDING.json')), issues=issues)
    print(json.dumps(result, indent=2))
    return result


def build_plan(args, registry=None):
    registry = PREPARE_ACT_DATASETS['projects'] if registry is None else registry
    root = args.root.expanduser().resolve()

    def project(name, exists=True):
        value = Path(name).expanduser()
        value = (root / value if not value.is_absolute() and len(value.parts) == 1 else value).absolute()
        if value.is_symlink() or any(p.is_symlink() for p in value.parents):
            raise ValueError('Symlink project is not supported: {}'.format(value))
        value = value.resolve()
        if exists and not (value / 'collect_data').is_dir():
            raise ValueError('Missing collect_data: {}'.format(value))
        return value

    if args.command == 'status':
        return project_status(project(args.project))
    plan = Plan(args.command)
    if args.command in ('quarantine', 'restore'):
        p = project(args.project)
        paths = select(p, args.episodes, args.command == 'restore')
        if args.command == 'quarantine':
            if args.episodes is None:
                paths = [p for p in paths if metadata(p).get('review_status') == 'rejected']
            add_quarantine(plan, p, paths)
        else:
            add_restore(plan, p, paths)
    else:
        destination = project(args.to, exists=args.command != 'merge')
        sources = [project(name) for name in args.sources]
        if len(set(sources)) != len(sources) or destination in sources:
            raise ValueError('Source and destination projects must differ and sources must be unique')
        if args.command == 'merge':
            if destination.exists():
                raise ValueError('Merge destination already exists: {}'.format(destination))
            plan.new_projects.add(destination)
        if args.command == 'transfer' and args.episodes:
            paths = select(sources[0], args.episodes)
        else:
            paths = ordered([p for source in sources for p in accepted(source)])
            count = getattr(args, 'count', None)
            if args.command == 'top-up':
                if args.target < 0:
                    raise ValueError('Target must be nonnegative')
                count = max(0, args.target - len(accepted(destination)))
            if count is not None:
                if count < 0 or (args.command == 'transfer' and count == 0):
                    raise ValueError('Count must be positive')
                if len(paths) < count:
                    raise ValueError('Not enough accepted episodes: need {}, found {}'.format(count, len(paths)))
                paths = paths[:count]
        if not paths and args.command == 'merge':
            raise ValueError('No accepted episodes to merge')
        add_transfer(plan, paths, destination, registry, copy=args.command == 'merge' and not args.move,
                     allow_rollouts=args.allow_rollouts)
    if plan.operations:
        reference_warnings(plan, root)
    return plan


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--root', type=Path, default=Path(PREPARE_ACT_DATASETS['root_dir']))
    sub = result.add_subparsers(dest='command', required=True)
    for command in ('status', 'quarantine', 'restore', 'transfer', 'top-up', 'merge'):
        p = sub.add_parser(command)
        # Also accept --root after the subcommand.
        p.add_argument('--root', type=Path, default=argparse.SUPPRESS)
        if command in ('status', 'quarantine', 'restore'):
            p.add_argument('--project', required=True)
        else:
            p.add_argument('--from', dest='sources', required=True, nargs='+' if command != 'transfer' else 1)
            p.add_argument('--to', required=True)
            p.add_argument('--allow-rollouts', action='store_true')
        if command in ('quarantine', 'restore'):
            p.add_argument('--episodes', nargs='+', required=command == 'restore')
        if command == 'transfer':
            group = p.add_mutually_exclusive_group(required=True)
            group.add_argument('--episodes', nargs='+')
            group.add_argument('--count', type=int)
        if command == 'top-up':
            p.add_argument('--target', required=True, type=int)
        if command == 'merge':
            p.add_argument('--move', action='store_true')
        if command != 'status':
            p.add_argument('--dry-run', action='store_true')
            p.add_argument('--yes', action='store_true')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        plan = build_plan(args)
        if isinstance(plan, Plan):
            execute(plan, args.dry_run, args.yes)
        return 0
    except (OSError, ValueError, KeyError) as error:
        print('Curation refused: {}'.format(error), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('Curation cancelled.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
