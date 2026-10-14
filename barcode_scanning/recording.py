"""Attach barcode destinations to paired A/B teleoperation recordings.

This module records provenance, not physical task success. Operator review is
still required to confirm staging and placement before demonstrations are used.
"""
import json
import os
from pathlib import Path
import tempfile
import time
import uuid

from .barcode_scanning_config import RECORDING
from experiments.experiments_config import CONTROL
from .scanner_reader import ScanWindow, destination_mapping


def write_metadata(path, metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.metadata-', suffix='.json', dir=str(path.parent))
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(metadata, stream, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_source_episode(path, medium, demonstrated_bin):
    path = Path(path).expanduser().resolve()
    if path.is_dir():
        path = path / RECORDING['metadata_filename']
    with path.open() as stream:
        metadata = json.load(stream)
    if (metadata.get('policy_stage') != 'A' or not metadata.get('recording_complete')
            or metadata.get('frame_count', 0) <= 0):
        raise ValueError('Source must be a completed Policy A recording')
    if metadata.get('medium') != medium:
        raise ValueError('B medium must match the source A medium')
    scan = metadata.get('scan')
    mapping = destination_mapping()
    if scan is not None:
        if metadata.get('scanner_error'):
            raise ValueError('Source A has no usable accepted scan')
        if mapping.get(scan.get('barcode')) != scan.get('bin_index'):
            raise ValueError('Source barcode/bin does not match the current destination mapping')
        if scan.get('cycle_id') != metadata.get('cycle_id'):
            raise ValueError('Source scan belongs to another parcel cycle')
        if type(demonstrated_bin) is not int or demonstrated_bin != scan['bin_index']:
            raise ValueError('--demonstrated-bin must match scanned bin {}'.format(scan['bin_index']))
    else:
        if metadata.get('capture_barcode', True):
            raise ValueError('Source A has no usable accepted scan')
        if type(demonstrated_bin) is not int or demonstrated_bin not in mapping.values():
            raise ValueError('Choose --demonstrated-bin from the configured destination bins')
    metadata['source_metadata_path'] = str(path)
    return metadata


class RecordingSession:
    def __init__(self, stage, medium, scan_window_s=30, source_episode=None,
                 demonstrated_bin=None, window=None, capture_barcode=False):
        if stage not in ('A', 'B'):
            raise ValueError('Policy stage must be A or B')
        if medium not in ('envelope', 'poly_mailer', 'carton'):
            raise ValueError('Choose --medium envelope, poly_mailer, or carton')
        self.stage, self.medium = stage, medium
        self.capture_barcode = capture_barcode
        if stage == 'B' and capture_barcode:
            raise ValueError('Policy B labels its destination manually or inherits A; it does not capture scans')
        self.scan_window_s = scan_window_s
        self.window = ScanWindow() if window is None else window
        # Validate duration before any devices or robot connections are opened.
        self.window.arm('validation', scan_window_s)
        self.window.close()
        self.source = None
        if stage == 'B':
            if source_episode is not None:
                self.source = load_source_episode(source_episode, medium, demonstrated_bin)
            elif type(demonstrated_bin) is not int or demonstrated_bin not in destination_mapping().values():
                raise ValueError('Policy B requires a configured --demonstrated-bin, e.g. 0 or 1')
        elif source_episode is not None or demonstrated_bin is not None:
            raise ValueError('--source-episode and --demonstrated-bin apply only to Policy B')
        self.demonstrated_bin = demonstrated_bin
        self.metadata = None
        self.path = None
        self.active = False
        self.reader = None
        self.last_status = None

    def start(self, episode_dir):
        episode_dir = Path(episode_dir)
        if self.active:
            raise RuntimeError('A recording is already active')
        if episode_dir.exists():
            raise ValueError('Episode folder already exists; refuse to overwrite: {}'.format(episode_dir))
        cycle = uuid.uuid4().hex if self.source is None else self.source['cycle_id']
        self.path = episode_dir / RECORDING['metadata_filename']
        self.metadata = {
            'schema_version': 2, 'control_overruns': 0,
            'control_period_ms': CONTROL['control_period_ms'], 'episode_id': episode_dir.name, 'cycle_id': cycle,
            'policy_stage': self.stage, 'medium': self.medium,
            'started_at': time.time(), 'recording_complete': False,
            'review_status': 'unreviewed', 'scanner_error': None, 'frame_count': 0,
            'destination_mapping': destination_mapping(),
            'scan': None if self.source is None else self.source['scan'],
            'source_episode_id': None if self.source is None else self.source['episode_id'],
            'source_metadata_path': None if self.source is None else self.source['source_metadata_path'],
            'demonstrated_bin': self.demonstrated_bin,
            'capture_barcode': self.capture_barcode,
            'destination': None,
        }
        self.active = True
        if self.stage == 'B':
            self.metadata['destination'] = {
                'bin_index': self.demonstrated_bin,
                'source': 'scanner' if self.metadata['scan'] is not None else 'manual',
                'recorded_at': time.time(),
            }
        if self.stage == 'A' and self.capture_barcode:
            self.window.arm(cycle, self.scan_window_s)
            self.metadata['scan_windows'] = []
            self._save_window()
        self._save()
        print('Recording {}: {}'.format(self.stage, episode_dir), flush=True)
        if self.stage == 'B':
            print('B destination fixed: bin {}. Demonstrate placement into this bin.'.format(self.metadata['destination']['bin_index']), flush=True)
        elif self.capture_barcode:
            print('Scan window open for {} s; press s in camera preview to retry before acceptance.'.format(self.scan_window_s), flush=True)
        else:
            print('A manipulation recording: scanner capture disabled', flush=True)

    def _save(self):
        write_metadata(self.path, self.metadata)

    def _save_window(self):
        self.metadata['scan_windows'].append({
            'opened_at': self.window.opened_timestamp,
            'duration_s': self.scan_window_s,
        })

    def rearm(self):
        with self.window.lock:
            self.poll()
            if not self.active or self.stage != 'A' or not self.capture_barcode:
                print('Scan retry requires an active A recording with --capture-barcode', flush=True)
                return
            if self.metadata['scan'] is not None:
                print('Destination already accepted; finish or discard this cycle before scanning another parcel', flush=True)
                return
            if self.metadata['scanner_error']:
                print('Scanner failed; stop recording and restart capture', flush=True)
                return
            self.window.arm(self.metadata['cycle_id'], self.scan_window_s)
            self._save_window()
            self.last_status = None
            self._save()
            print('New scan window open for {} s'.format(self.scan_window_s), flush=True)

    def poll(self):
        if not self.active:
            return
        if self.stage == 'A' and self.capture_barcode:
            if self.reader is not None and self.reader.error is not None:
                if self.metadata['scanner_error'] is None:
                    self.metadata['scanner_error'] = self.reader.error
                    self._save()
                    print('Scanner failed: {}. Recording is invalid for B; stop and restart capture.'.format(self.reader.error), flush=True)
            status = self.window.status()
            if status['scan'] is not None and self.metadata['scan'] is None:
                self.metadata['scan'] = status['scan']
                self.metadata['destination'] = {'bin_index': status['scan']['bin_index'],
                                                'source': 'scanner', 'recorded_at': status['scan']['timestamp']}
                self._save()
                print('BARCODE ACCEPTED: {} -> bin {}'.format(status['scan']['barcode'], status['scan']['bin_index']), flush=True)
            if status['reason'] != self.last_status:
                self.last_status = status['reason']
                print('Scanner: {}'.format(status['reason']), flush=True)

    def record_frame(self):
        if self.active:
            self.metadata['frame_count'] += 1

    def stop(self, complete=True):
        if not self.active:
            return
        self.poll()
        self.window.close('recording stopped')
        self.metadata['ended_at'] = time.time()
        self.metadata['recording_complete'] = complete
        self.metadata['scan_status'] = self.window.status()['reason'] if self.capture_barcode else 'capture disabled'
        if self.stage == 'A':
            self.metadata['destination_resolved'] = self.metadata['scan'] is not None and not self.metadata['scanner_error']
        else:
            self.metadata['destination_resolved'] = True
        self._save()
        self.active = False
        print('Saved episode metadata: {}'.format(self.path), flush=True)


def inspect_episode(episode_dir):
    """Check destination metadata and matching raw-frame filenames, no hardware."""
    from .dataset_metadata import read_episode_metadata
    episode_dir = Path(episode_dir).expanduser().resolve()
    metadata = read_episode_metadata(episode_dir)
    if metadata is None:
        raise ValueError('No A/B metadata found')
    identifiers = {}
    for folder, extension in [('observation', '.pkl'), ('topImg', '.jpg'),
                              ('leftImg', '.jpg'), ('rightImg', '.jpg')]:
        identifiers[folder] = {path.stem for path in (episode_dir / folder).glob('*' + extension)}
    observations = identifiers['observation']
    if not observations or any(value != observations for value in identifiers.values()):
        raise ValueError('Missing frames or camera/observation identifiers do not match')
    if len(observations) != metadata.get('frame_count'):
        raise ValueError('Frame count differs from metadata')
    return {'episode': str(episode_dir), 'policy_stage': metadata['policy_stage'],
            'medium': metadata['medium'], 'frames': len(observations),
            'barcode': None if metadata.get('scan') is None else metadata['scan']['barcode'],
            'bin_index': None if metadata.get('destination') is None else metadata['destination']['bin_index'],
            'cycle_id': metadata['cycle_id'], 'review_status': metadata['review_status']}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Inspect an A/B recording without opening hardware')
    parser.add_argument('--inspect-episode', required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(inspect_episode(args.inspect_episode), indent=2))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print('Episode check failed: {}'.format(error))
        return 2


if __name__ == '__main__':
    import sys
    sys.exit(main())
