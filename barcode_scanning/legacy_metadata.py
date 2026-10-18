"""Read-only validation of recordings from the superseded design."""
import json
from pathlib import Path

from .barcode_scanning_config import RECORDING
from .scanner_reader import destination_mapping


def read_legacy_metadata(episode_dir):
    path = Path(episode_dir) / RECORDING['metadata_filename']
    if not path.exists():
        return None  # Older recordings remain convertible.
    with path.open() as stream:
        metadata = json.load(stream)
    if not metadata.get('recording_complete'):
        raise ValueError('Recording was interrupted; review it before conversion')
    if metadata.get('policy_stage') not in ('A', 'B'):
        raise ValueError('Unrecognised recording stage')
    scan = metadata.get('scan')
    if metadata.get('scanner_error'):
        raise ValueError('Recording has a scanner error')
    if scan is not None:
        if destination_mapping().get(scan.get('barcode')) != scan.get('bin_index'):
            raise ValueError('Recording barcode/bin differs from the current mapping')
        if scan.get('cycle_id') != metadata.get('cycle_id'):
            raise ValueError('Scan and recording cycle IDs differ')
        # Older scan-only episodes have no explicit destination object.
        if metadata.get('destination') is None:
            metadata['destination'] = {'bin_index': scan['bin_index'], 'source': 'scanner'}
        if metadata['destination']['bin_index'] != scan['bin_index']:
            raise ValueError('Destination differs from accepted scan')
    elif metadata.get('capture_barcode', True):
        raise ValueError('Recording has no valid scanner destination')
    if metadata['policy_stage'] == 'B':
        destination = metadata.get('destination')
        if (not destination or type(destination.get('bin_index')) is not int
                or destination['bin_index'] not in destination_mapping().values()):
            raise ValueError('Policy B requires a valid destination label')
        if metadata.get('demonstrated_bin') != destination['bin_index']:
            raise ValueError('Policy B demonstrated bin differs from its destination')
    return metadata

