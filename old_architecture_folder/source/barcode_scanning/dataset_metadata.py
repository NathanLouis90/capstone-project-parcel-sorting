"""Preserve episode provenance and destination observations during conversion."""
import json
from pathlib import Path

from .barcode_scanning_config import RECORDING
from .scanner_reader import destination_mapping


def read_episode_metadata(episode_dir):
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


def write_hdf5_metadata(root, metadata, timesteps):
    if metadata is None:
        return
    root.attrs['episode_metadata_json'] = json.dumps(metadata)
    root.attrs['policy_stage'] = metadata['policy_stage']
    root.attrs['medium'] = metadata['medium']
    root.attrs['cycle_id'] = metadata['cycle_id']
    if metadata.get('scan') is not None:
        root.attrs['barcode'] = metadata['scan']['barcode']
    if metadata.get('destination') is not None:
        root.attrs['bin_index'] = metadata['destination']['bin_index']
        root.attrs['destination_source'] = metadata['destination']['source']
    if metadata['policy_stage'] == 'B':
        import numpy as np
        bins = sorted(set(destination_mapping().values()))
        if bins != list(range(len(bins))):
            raise ValueError('Destination bin indices must be contiguous from zero')
        destination = np.zeros((timesteps, len(bins)), dtype=np.float32)
        destination[:, metadata['destination']['bin_index']] = 1
        root.create_dataset('observations/destination', data=destination)
