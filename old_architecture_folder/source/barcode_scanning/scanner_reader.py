#!/usr/bin/env python3
"""Read a dedicated Linux HID barcode scanner without depending on window focus.

Use --list-devices to inspect devices, --simulate TOKEN for a hardware-free test,
or run without flags to capture continuously until Ctrl+C. Use --once for a
bounded, single-scan test.
"""
import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import queue
import select
import sys
import threading
import time

if __package__:
    from .barcode_scanning_config import MAKE_LABELS, SCANNER_READER
else:
    from barcode_scanning_config import MAKE_LABELS, SCANNER_READER


@dataclass(frozen=True)
class ScanEvent:
    barcode: str
    bin_index: int
    timestamp: float
    cycle_id: str
    received_monotonic: float
    raw_barcode: str = ''

    def to_dict(self):
        return asdict(self)


def destination_mapping():
    mapping = {}
    for destination in MAKE_LABELS['destinations']:
        token, index = destination['token'], destination['bin']
        if isinstance(token, str) and SCANNER_READER['normalize_case']:
            token = token.upper()
        if not isinstance(token, str) or not token or token in mapping:
            raise ValueError('Destination tokens must be unique, nonempty strings')
        if type(index) is not int or index < 0:
            raise ValueError('Destination bins must be nonnegative integers')
        mapping[token] = index
    return mapping


class ScanWindow:
    """Thread-safe, bounded scan window. No robot or evdev dependency."""
    def __init__(self, mapping=None, partial_timeout_s=None, max_length=None,
                 clock=time.monotonic, wall_clock=time.time, continuous=False):
        self.mapping = destination_mapping() if mapping is None else dict(mapping)
        self.partial_timeout_s = (SCANNER_READER['partial_timeout_s']
                                  if partial_timeout_s is None else partial_timeout_s)
        self.max_length = SCANNER_READER['max_length'] if max_length is None else max_length
        self.clock, self.wall_clock = clock, wall_clock
        self.continuous = continuous
        self.events = queue.Queue(maxsize=256 if continuous else 1)
        self.diagnostics = queue.Queue(maxsize=256)
        self.last_rejected = None
        self.discard_reason = None
        self.lock = threading.RLock()
        self.active = False
        self.result = None
        self.reason = 'not armed'
        self.buffer = ''
        self.discard_frame = False
        self.last_character = None
        self.cycle_id = None

    def arm(self, cycle_id, window_s):
        if window_s is None and not self.continuous:
            raise ValueError('Only continuous capture may omit the scan deadline')
        if window_s is not None and (window_s <= 0 or not float('-inf') < window_s < float('inf')):
            raise ValueError('Scan window must be positive and finite')
        with self.lock:
            self.cycle_id = str(cycle_id)
            self.opened_monotonic = self.clock()
            self.opened_timestamp = self.wall_clock()
            self.deadline = None if window_s is None else self.opened_monotonic + window_s
            self.active, self.result, self.reason = True, None, 'waiting'
            self.buffer, self.last_character = '', None
            self.discard_frame = False
            self.discard_reason = None
            self.last_rejected = None
            while True:
                try:
                    self.events.get_nowait()
                except queue.Empty:
                    break

    def close(self, reason='closed'):
        with self.lock:
            self.active = False
            self.buffer, self.last_character = '', None
            if self.result is None:
                self.reason = reason

    def status(self):
        with self.lock:
            self._expire()
            return {'active': self.active, 'reason': self.reason,
                    'scan': None if self.result is None else self.result.to_dict(),
                    'last_rejected': self.last_rejected}

    def _expire(self):
        now = self.clock()
        if self.active and self.deadline is not None and now >= self.deadline:
            self.close('scan timeout')
        if self.last_character is not None and now - self.last_character > self.partial_timeout_s:
            self.buffer, self.last_character = '', None
            self.discard_frame = True
            self.discard_reason = 'partial scan timeout'
            self.reason = 'partial scan timeout; waiting'
        return now

    def feed(self, character, event_timestamp=None):
        """Receive one decoded character; newline terminates a complete scan.

        Device timestamps are used only to reject events queued before arming.
        Window deadlines and partial-text timeouts use a monotonic clock.
        """
        with self.lock:
            now = self._expire()
            if not self.active:
                return None
            if event_timestamp is not None and event_timestamp < self.opened_timestamp:
                self.buffer, self.last_character = '', None
                return None
            if character == '\n':
                raw_token = self.buffer
                invalid = self.discard_frame
                rejection = self.discard_reason
                token = raw_token.upper() if SCANNER_READER['normalize_case'] else raw_token
                self.discard_frame = False
                self.discard_reason = None
                self.buffer, self.last_character = '', None
                if invalid or token not in self.mapping:
                    self.reason = 'unknown or empty barcode; waiting'
                    self.last_rejected = {'raw_barcode': raw_token,
                                          'reason': rejection or ('empty barcode' if not raw_token else 'unmapped barcode')}
                    diagnostic = dict(self.last_rejected, type='rejected', timestamp=self.wall_clock())
                    try:
                        self.diagnostics.put_nowait(diagnostic)
                    except queue.Full:
                        self.diagnostics.get_nowait()
                        self.diagnostics.put_nowait(diagnostic)
                    return None
                result = ScanEvent(token, self.mapping[token], self.wall_clock(),
                                   self.cycle_id, now, raw_token)
                self.result, self.active, self.reason = result, self.continuous, 'accepted'
                try:
                    self.events.put_nowait(result)
                except queue.Full as error:
                    raise RuntimeError('Scanner event queue is full; consumer must drain scans') from error
                return result
            if self.discard_frame:
                self.last_character = now
                return None
            if character == '\b':
                self.buffer = self.buffer[:-1]
                self.last_character = now if self.buffer else None
                return None
            if character is None or len(character) != 1 or character not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-':
                self.buffer, self.last_character = '', None
                self.discard_frame = True
                self.discard_reason = 'unsupported key/character'
                self.last_character = now
                self.reason = 'unsupported character; waiting'
                return None
            if len(self.buffer) >= self.max_length:
                self.buffer, self.last_character = '', None
                self.discard_frame = True
                self.discard_reason = 'barcode too long'
                self.last_character = now
                self.reason = 'barcode too long; waiting'
                return None
            self.buffer += character
            self.last_character = now
            return None


class KeyboardDecoder:
    """Decode an explicitly configured US keyboard layout and scanner suffix."""
    def __init__(self, terminators=None):
        self.terminators = SCANNER_READER['terminator_keys'] if terminators is None else terminators
        self.shifts = set()
        self.caps_lock = False

    def decode(self, key, value):
        if key in ('KEY_LEFTSHIFT', 'KEY_RIGHTSHIFT'):
            if value == 1:
                self.shifts.add(key)
            elif value == 0:
                self.shifts.discard(key)
            return ''
        if value != 1:  # Ignore key release and autorepeat events.
            return ''
        if key == 'KEY_NUMLOCK':
            return ''
        if key == 'KEY_CAPSLOCK':
            self.caps_lock = not self.caps_lock
            return ''
        if key in self.terminators:
            return '\n'
        if key == 'KEY_BACKSPACE':
            return '\b'
        name = key[4:] if key.startswith('KEY_') else ''
        if len(name) == 1 and name.isalpha():
            return name if bool(self.shifts) != self.caps_lock else name.lower()
        if len(name) == 1 and name.isdigit():
            return name if not self.shifts else None
        if key.startswith('KEY_KP') and len(key) == 7 and key[-1].isdigit():
            return key[-1]
        if key == 'KEY_KPMINUS':
            return '-'
        if key == 'KEY_MINUS':
            return '-' if not self.shifts else None
        return None


def _evdev():
    try:
        import evdev
    except ImportError as error:
        raise RuntimeError('Missing python-evdev. Install it in Xtrainer: python3 -m pip install "evdev==1.6.1"') from error
    return evdev


def list_devices():
    evdev = _evdev()
    devices = []
    # evdev.list_devices() silently omits nodes without access. Include those
    # nodes so --list-devices can explain permission failures.
    paths = sorted(set(evdev.list_devices()) | {str(path) for path in Path('/dev/input').glob('event*')})
    for path in paths:
        try:
            device = evdev.InputDevice(path)
            try:
                devices.append({'path': path, 'name': device.name, 'vendor': device.info.vendor,
                                'product': device.info.product, 'phys': device.phys,
                                'uniq': device.uniq})
            finally:
                device.close()
        except OSError as error:
            devices.append({'path': path, 'error': str(error)})
    return devices


class ScannerReader:
    """Own one scanner device and publish accepted scans through ScanWindow."""
    def __init__(self, window=None, device_path=None, debug=False):
        self.window = ScanWindow() if window is None else window
        self.device_path = device_path or SCANNER_READER['device_path']
        self.stop_event = threading.Event()
        self.error = None
        self.device = None
        self.thread = None
        self.decoder = KeyboardDecoder()
        self.debug = debug

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Scanner reader already started')
        if SCANNER_READER['keyboard_layout'] != 'us':
            raise ValueError('Only the US scanner keyboard layout is supported')
        if not SCANNER_READER['exclusive_capture']:
            raise ValueError('Exclusive capture is required to prevent typing into other windows')
        evdev = _evdev()
        candidates = []
        try:
            paths = [self.device_path] if self.device_path else evdev.list_devices()
            for path in paths:
                device = evdev.InputDevice(path)
                expected = SCANNER_READER
                matches = (device.name == expected['device_name']
                           and device.info.vendor == expected['vendor_id']
                           and device.info.product == expected['product_id'])
                if matches and evdev.ecodes.KEY_ENTER in device.capabilities().get(evdev.ecodes.EV_KEY, []):
                    candidates.append(device)
                else:
                    device.close()
            if len(candidates) != 1:
                raise RuntimeError('Expected exactly one confirmed scanner; found {}. Run --list-devices and configure its identity.'.format(len(candidates)))
            self.device = candidates[0]
            self.device.grab()
        except BaseException:
            for device in candidates:
                device.close()
            self.device = None
            raise
        self.thread = threading.Thread(target=self._run, name='barcode-reader', daemon=True)
        try:
            self.thread.start()
        except BaseException:
            self.device.ungrab()
            self.device.close()
            raise
        return self

    def _run(self):
        evdev = _evdev()
        try:
            while not self.stop_event.is_set():
                readable, _, _ = select.select([self.device.fd], [], [], SCANNER_READER['poll_interval_s'])
                if not readable:
                    self.window.status()
                    continue
                for event in self.device.read():
                    if event.type == evdev.ecodes.EV_SYN and event.code == evdev.ecodes.SYN_DROPPED:
                        raise RuntimeError('Scanner input events were dropped; restart capture')
                    if event.type != evdev.ecodes.EV_KEY:
                        continue
                    key = evdev.ecodes.KEY.get(event.code, '')
                    if isinstance(key, list):
                        key = key[0]
                    character = self.decoder.decode(key, event.value)
                    if self.debug and event.value == 1:
                        print(json.dumps({'type': 'key', 'key': key, 'decoded': character}), flush=True)
                    if character != '':
                        self.window.feed(character, event.timestamp())
        except Exception as error:
            self.error = str(error)
            self.window.close('scanner disconnected or failed')
        finally:
            try:
                self.device.ungrab()
            except OSError:
                pass
            self.device.close()

    def check_health(self):
        if self.error is not None:
            raise RuntimeError('Barcode scanner failed: ' + self.error)

    def close(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2)

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list-devices', action='store_true')
    parser.add_argument('--device', help='Device path; configured name/vendor/product must still match')
    parser.add_argument('--window', type=float, default=SCANNER_READER['scan_window_s'])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--continuous', action='store_true', help='Capture indefinitely (also the default)')
    mode.add_argument('--once', action='store_true', help='Capture one valid barcode within --window seconds')
    parser.add_argument('--debug', action='store_true', help='Print scanner key events and decoded characters')
    parser.add_argument('--simulate', metavar='TOKEN', help='Feed text without opening any input device')
    args = parser.parse_args(argv)
    try:
        if args.list_devices:
            devices = list_devices()
            for device in devices:
                print(json.dumps(device), flush=True)
            if not any('name' in device for device in devices):
                if devices:
                    print('Input devices exist but cannot be opened. Check the reported permission errors.', file=sys.stderr)
                else:
                    print('No input device nodes found. Check /dev/input visibility on the host.', file=sys.stderr)
                return 2
            return 0
        window = ScanWindow()
        if args.simulate is not None:
            window.arm('standalone-1', args.window)
            for character in args.simulate + '\n':
                window.feed(character)
            print(json.dumps(window.status()), flush=True)
            return 0 if window.result is not None else 2
        if not args.once:
            window = ScanWindow(continuous=True)
            window.arm('continuous', None)
        with ScannerReader(window, args.device, debug=args.debug) as reader:
            print('Capturing scanner exclusively: {}'.format(reader.device.path), flush=True)
            if args.once:
                window.arm('standalone-1', args.window)
                print('Scan window open for {} seconds'.format(args.window), flush=True)
            else:
                print('Continuous capture active; no overall timeout. Ctrl+C stops capture.', flush=True)
            while True:
                reader.check_health()
                status = window.status()
                while True:
                    try:
                        print(json.dumps(window.events.get_nowait().to_dict()), flush=True)
                    except queue.Empty:
                        break
                while True:
                    try:
                        print(json.dumps(window.diagnostics.get_nowait()), flush=True)
                    except queue.Empty:
                        break
                if args.once and not status['active']:
                    print(json.dumps(status), flush=True)
                    return 0 if window.result is not None else 2
                time.sleep(SCANNER_READER['poll_interval_s'])
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print('Scanner error: {}'.format(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
