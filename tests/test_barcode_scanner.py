"""Hardware-free scanner, recording, and conversion contract tests."""
import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import h5py
import numpy as np

from barcode_scanning.scanner_reader import KeyboardDecoder, ScanWindow, ScannerReader, list_devices, main
from barcode_scanning.recording import RecordingSession, load_source_episode
from barcode_scanning.dataset_metadata import read_episode_metadata, write_hdf5_metadata


class Clock:
    def __init__(self):
        self.now = 10.0
    def __call__(self):
        return self.now


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.window = ScanWindow(clock=self.clock, wall_clock=lambda: 1000 + self.clock.now)
        self.window.arm('item-1', 5)

    def feed(self, text, **kwargs):
        for character in text:
            self.window.feed(character, **kwargs)

    def test_known_token_publishes_once(self):
        self.feed('DEST-A-S138683\n')
        event = self.window.events.get_nowait()
        self.assertEqual((event.bin_index, event.cycle_id), (0, 'item-1'))
        self.feed('DEST-B-S828608\n')
        self.assertEqual(self.window.result, event)
        self.assertTrue(self.window.events.empty())

    def test_unknown_token_allows_retry(self):
        self.feed('UNKNOWN\n')
        self.assertTrue(self.window.status()['active'])
        self.feed('DEST-B-S828608\n')
        self.assertEqual(self.window.result.bin_index, 1)

    def test_case_normalized_and_raw_text_retained(self):
        self.feed('dest-a-s138683\n')
        self.assertEqual(self.window.result.barcode, 'DEST-A-S138683')
        self.assertEqual(self.window.result.raw_barcode, 'dest-a-s138683')

    def test_case_normalization_can_be_disabled(self):
        with patch.dict('barcode_scanning.scanner_reader.SCANNER_READER', {'normalize_case': False}):
            self.feed('dest-a-s138683\n')
        self.assertIsNone(self.window.result)

    def test_unknown_text_visible_in_diagnostics(self):
        self.feed('NOT-A-DESTINATION\n')
        rejection = self.window.diagnostics.get_nowait()
        self.assertEqual(rejection['raw_barcode'], 'NOT-A-DESTINATION')
        self.assertEqual(rejection['reason'], 'unmapped barcode')

    def test_continuous_capture_has_no_deadline_or_rearm_gaps(self):
        window = ScanWindow(clock=self.clock, continuous=True)
        window.arm('continuous', None)
        self.clock.now += 1000000
        for token in ['DEST-A-S138683', 'DEST-A-S138683', 'DEST-B-S828608']:
            for char in token + '\n':
                window.feed(char)
        self.assertTrue(window.status()['active'])
        self.assertEqual([window.events.get_nowait().bin_index for _ in range(3)], [0, 0, 1])

    def test_keypad_digits(self):
        decoder = KeyboardDecoder()
        self.assertEqual(decoder.decode('KEY_KP1', 1), '1')
        self.assertEqual(decoder.decode('KEY_KPMINUS', 1), '-')

    def test_completion_after_deadline_rejected(self):
        self.feed('DEST-A-S138683')
        self.clock.now = 15
        self.feed('\n')
        self.assertIsNone(self.window.result)
        self.assertEqual(self.window.status()['reason'], 'scan timeout')

    def test_stale_device_events_rejected(self):
        self.feed('DEST-A-S138683\n', event_timestamp=1009)
        self.assertIsNone(self.window.result)
        self.feed('DEST-A-S138683\n', event_timestamp=1010)
        self.assertEqual(self.window.result.bin_index, 0)

    def test_partial_timeout_discards_entire_frame(self):
        self.feed('D')
        self.clock.now += 1
        self.feed('DEST-A-S138683\n')
        self.assertIsNone(self.window.result)
        self.feed('DEST-A-S138683\n')
        self.assertIsNotNone(self.window.result)

    def test_invalid_prefix_cannot_alias_valid_token(self):
        self.feed('!DEST-A-S138683\n')
        self.assertIsNone(self.window.result)

    def test_rearm_clears_partial_text_and_queue(self):
        self.feed('DEST-A-S138683\n')
        self.window.arm('item-2', 5)
        self.assertTrue(self.window.events.empty())
        self.feed('DEST-A-S138683\n')
        self.assertEqual(self.window.result.cycle_id, 'item-2')

    def test_closed_window_ignores_scans(self):
        self.window.close()
        self.feed('DEST-A-S138683\n')
        self.assertIsNone(self.window.result)

    def test_bad_duration_rejected(self):
        for duration in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.window.arm('item', duration)

    def test_simulate_cli_needs_no_evdev(self):
        with patch('barcode_scanning.scanner_reader._evdev', side_effect=AssertionError('device opened')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--simulate', 'DEST-A-S138683']), 0)
            self.assertEqual(main(['--simulate', 'UNKNOWN']), 2)


class DecoderTests(unittest.TestCase):
    def test_shift_and_release(self):
        decoder = KeyboardDecoder()
        self.assertEqual(decoder.decode('KEY_LEFTSHIFT', 1), '')
        self.assertEqual(decoder.decode('KEY_D', 1), 'D')
        self.assertEqual(decoder.decode('KEY_D', 0), '')
        self.assertEqual(decoder.decode('KEY_D', 2), '')
        decoder.decode('KEY_LEFTSHIFT', 0)
        self.assertEqual(decoder.decode('KEY_D', 1), 'd')

    def test_tokens_and_terminator(self):
        decoder = KeyboardDecoder()
        self.assertEqual(decoder.decode('KEY_1', 1), '1')
        self.assertEqual(decoder.decode('KEY_MINUS', 1), '-')
        self.assertEqual(decoder.decode('KEY_ENTER', 1), '\n')
        self.assertIsNone(decoder.decode('KEY_F1', 1))

    def test_caps_and_shift(self):
        decoder = KeyboardDecoder()
        decoder.decode('KEY_CAPSLOCK', 1)
        self.assertEqual(decoder.decode('KEY_A', 1), 'A')
        decoder.decode('KEY_RIGHTSHIFT', 1)
        self.assertEqual(decoder.decode('KEY_A', 1), 'a')


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def source(self):
        session = RecordingSession('A', 'carton', capture_barcode=True)
        session.start(self.root / 'A')
        for char in 'DEST-B-S828608\n':
            session.window.feed(char)
        session.poll()
        session.record_frame()
        session.stop()
        return self.root / 'A'

    def test_paired_a_b_records_keep_destination(self):
        source = self.source()
        b = RecordingSession('B', 'carton', source_episode=source, demonstrated_bin=1)
        b.start(self.root / 'B')
        b.stop()
        a_data = read_episode_metadata(source)
        b_data = read_episode_metadata(self.root / 'B')
        self.assertEqual(a_data['cycle_id'], b_data['cycle_id'])
        self.assertEqual(b_data['scan']['bin_index'], 1)
        self.assertEqual(b_data['source_episode_id'], 'A')
        self.assertEqual(b_data['review_status'], 'unreviewed')

    def test_a_without_scanner_is_convertible(self):
        a = RecordingSession('A', 'carton')
        a.start(self.root / 'manual-A')
        a.record_frame()
        a.stop()
        metadata = read_episode_metadata(self.root / 'manual-A')
        self.assertFalse(metadata['capture_barcode'])
        self.assertIsNone(metadata['scan'])
        with h5py.File(str(self.root / 'manual-A.hdf5'), 'w') as file:
            file.create_group('observations')
            write_hdf5_metadata(file, metadata, 1)
            self.assertNotIn('observations/destination', file)

    def test_manual_b_destination_is_saved_and_converted(self):
        b = RecordingSession('B', 'carton', demonstrated_bin=0)
        b.start(self.root / 'manual-B')
        b.record_frame()
        b.stop()
        metadata = read_episode_metadata(self.root / 'manual-B')
        self.assertIsNone(metadata['scan'])
        self.assertEqual(metadata['destination']['source'], 'manual')
        with h5py.File(str(self.root / 'manual-B.hdf5'), 'w') as file:
            file.create_group('observations')
            write_hdf5_metadata(file, metadata, 1)
            np.testing.assert_array_equal(file['observations/destination'][:], [[1, 0]])

    def test_manual_b_can_pair_with_unscanned_a(self):
        a = RecordingSession('A', 'carton')
        a.start(self.root / 'manual-A')
        a.record_frame()
        a.stop()
        b = RecordingSession('B', 'carton', source_episode=self.root / 'manual-A', demonstrated_bin=1)
        b.start(self.root / 'manual-B')
        b.record_frame()
        b.stop()
        self.assertEqual(a.metadata['cycle_id'], b.metadata['cycle_id'])
        self.assertEqual(b.metadata['destination']['bin_index'], 1)

    def test_manual_b_needs_a_configured_bin(self):
        for index in (None, -1, 2):
            with self.assertRaises(ValueError):
                RecordingSession('B', 'carton', demonstrated_bin=index)

    def test_wrong_bin_rejected_before_b(self):
        with self.assertRaisesRegex(ValueError, 'match scanned bin'):
            RecordingSession('B', 'carton', source_episode=self.source(), demonstrated_bin=0)

    def test_wrong_medium_rejected(self):
        with self.assertRaisesRegex(ValueError, 'medium'):
            RecordingSession('B', 'envelope', source_episode=self.source(), demonstrated_bin=1)

    def test_missing_scan_rejected(self):
        a = RecordingSession('A', 'carton', capture_barcode=True)
        a.start(self.root / 'A')
        a.record_frame()
        a.stop()
        with self.assertRaisesRegex(ValueError, 'usable accepted scan'):
            load_source_episode(self.root / 'A', 'carton', 1)

    def test_aborted_recording_rejected(self):
        a = RecordingSession('A', 'carton', capture_barcode=True)
        a.start(self.root / 'A')
        a.stop(complete=False)
        with self.assertRaisesRegex(ValueError, 'completed'):
            load_source_episode(self.root / 'A', 'carton', 1)

    def test_episode_overwrite_refused(self):
        a = RecordingSession('A', 'carton', capture_barcode=True)
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            a.start(self.source())

    def test_accepted_destination_cannot_be_rearmed(self):
        a = RecordingSession('A', 'carton', capture_barcode=True)
        a.start(self.root / 'A')
        for char in 'DEST-A-S138683\n':
            a.window.feed(char)
        a.poll()
        a.rearm()
        self.assertFalse(a.window.active)
        self.assertEqual(a.metadata['scan']['bin_index'], 0)

    def test_reader_failure_invalidates_source(self):
        a = RecordingSession('A', 'carton', capture_barcode=True)
        a.reader = types.SimpleNamespace(error='device disconnected')
        a.start(self.root / 'A')
        a.record_frame()
        for char in 'DEST-A-S138683\n':
            a.window.feed(char)
        a.stop()
        with self.assertRaisesRegex(ValueError, 'usable accepted scan'):
            load_source_episode(self.root / 'A', 'carton', 0)

    def test_hdf5_b_condition_is_constant(self):
        source = self.source()
        b = RecordingSession('B', 'carton', source_episode=source, demonstrated_bin=1)
        b.start(self.root / 'B')
        b.stop()
        metadata = read_episode_metadata(self.root / 'B')
        with h5py.File(str(self.root / 'episode.hdf5'), 'w') as file:
            file.create_group('observations')
            write_hdf5_metadata(file, metadata, 3)
            np.testing.assert_array_equal(file['observations/destination'][:], [[0, 1]] * 3)
            self.assertEqual(file.attrs['policy_stage'], 'B')

    def test_legacy_metadata_optional(self):
        self.assertIsNone(read_episode_metadata(self.root))


class ReaderCleanupTests(unittest.TestCase):
    def fake_device(self, name='Megahunt HID Keyboard'):
        class Device:
            info = types.SimpleNamespace(vendor=0x0461, product=0x4D82)
            fd = 1
            path = '/fake/scanner'
            grabbed = False
            closed = False
            def capabilities(self):
                return {1: [28]}
            def grab(self):
                self.grabbed = True
            def ungrab(self):
                self.grabbed = False
            def close(self):
                self.closed = True
        device = Device()
        device.name = name
        return device

    def evdev(self, device):
        return types.SimpleNamespace(list_devices=lambda: ['/fake/scanner'],
                                     InputDevice=lambda path: device,
                                     ecodes=types.SimpleNamespace(KEY_ENTER=28, EV_KEY=1))

    def test_inaccessible_nodes_are_reported(self):
        evdev = types.SimpleNamespace(list_devices=lambda: [],
                                     InputDevice=lambda path: (_ for _ in ()).throw(PermissionError('Permission denied')))
        with patch('barcode_scanning.scanner_reader._evdev', return_value=evdev), patch('barcode_scanning.scanner_reader.Path.glob', return_value=[Path('/dev/input/event3')]):
            devices = list_devices()
        self.assertEqual(devices[0]['path'], '/dev/input/event3')
        self.assertIn('Permission denied', devices[0]['error'])

    def test_wrong_device_never_grabbed(self):
        device = self.fake_device('ordinary keyboard')
        with patch('barcode_scanning.scanner_reader._evdev', return_value=self.evdev(device)):
            with self.assertRaisesRegex(RuntimeError, 'confirmed scanner'):
                ScannerReader().start()
        self.assertFalse(device.grabbed)
        self.assertTrue(device.closed)

    def test_read_failure_releases_device(self):
        device = self.fake_device()
        evdev = self.evdev(device)
        with patch('barcode_scanning.scanner_reader._evdev', return_value=evdev), patch('barcode_scanning.scanner_reader.select.select', side_effect=OSError('unplugged')):
            reader = ScannerReader().start()
            reader.thread.join(timeout=1)
            reader.close()
        self.assertIn('unplugged', reader.error)
        self.assertFalse(device.grabbed)
        self.assertTrue(device.closed)


class RecorderManualModeTests(unittest.TestCase):
    def test_manual_a_and_b_do_not_open_scanner(self):
        tree = ast.parse(Path('experiments/run_control.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        calls = []
        def scanner(*args, **kwargs):
            raise AssertionError('manual mode opened a scanner')
        namespace = {'RecordingSession': RecordingSession, 'ScannerReader': scanner,
                     '_run_control': lambda args, session: calls.append(session)}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'recorder-main', 'exec'), namespace)
        for stage, bin_index in [('A', None), ('B', 1)]:
            args = types.SimpleNamespace(policy_stage=stage, capture_barcode=False, medium='carton',
                                         scan_window_s=30, source_episode=None,
                                         demonstrated_bin=bin_index, scanner_device=None)
            namespace['main'](args)
        self.assertEqual([session.stage for session in calls], ['A', 'B'])


class RecorderButtonTests(unittest.TestCase):
    def test_first_b_release_starts_and_second_stops(self):
        # Execute just the button function; do not import hardware modules.
        source = Path('experiments/run_control.py').read_text()
        tree = ast.parse(source)
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'button_monitor_realtime')
        falling = np.array([0])
        actions = np.zeros((2, 3), dtype=int)
        namespace = {'np': np, 'time': __import__('time'), 'datetime': __import__('datetime'),
                     'what_to_do': actions, 'is_falling': falling,
                     'dt_time': np.array([0], dtype=object), 'using_sensor_protection': False,
                     'recording_lock': threading.Lock(), 'RUN_CONTROL': {'short_press_s': .5, 'long_press_s': 1}}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'button', 'exec'), namespace)
        # Force left synchronization on through its A long press.
        frames = [([[0, 0, 0], [0, 0, 0]], 0),
                  ([[-1, 0, 0], [0, 0, 0]], 0),
                  ([[0, 0, 0], [0, 0, 0]], 2),
                  ([[0, -1, 0], [0, 0, 0]], 2),
                  ([[0, 0, 0], [0, 0, 0]], 2),
                  ([[0, -1, 0], [0, 0, 0]], 2),
                  ([[0, 0, 0], [0, 0, 0]], 2)]
        observed = []
        class Agent:
            def get_keys(self):
                observed.append(bool(actions[0, 2]))
                frame, stamp = frames.pop(0)
                namespace['time'] = types.SimpleNamespace(time=lambda: stamp)
                if not frames:
                    falling[0] = 1
                return np.array(frame)
        with contextlib.redirect_stdout(io.StringIO()):
            namespace['button_monitor_realtime'](Agent())
        self.assertTrue(observed[-1])
        self.assertFalse(actions[0, 2])
        self.assertGreater(len(str(namespace['dt_time'][0])), 14)


if __name__ == '__main__':
    unittest.main()
