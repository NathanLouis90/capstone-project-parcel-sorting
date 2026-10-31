"""Extension seams: policy registry and the cycle's reusable pick/scan/place skills."""

import pytest

from config.settings import MEDIA, RUNTIME
from parcel_sorting.data import dataset_metadata
from parcel_sorting.policies import interface
from parcel_sorting.policies.policy_step import SimulatedPolicy
from parcel_sorting.runtime import cycle as run_cycle
from parcel_sorting.runtime.cycle import Cycle, FakeScanner
from parcel_sorting.runtime.scripted_motion import MotionLoop, SimulatedEnv, VirtualClock, simulation_waypoints
from parcel_sorting.safety import inference_safety


def simulated_cycle(tmp_path, monkeypatch, token='DEST-A-S138683', medium='poly_mailer'):
    monkeypatch.setattr(inference_safety, 'commanded_workspace_ok', lambda action, config: True)
    clock = VirtualClock()
    points = simulation_waypoints()
    motion = MotionLoop(SimulatedEnv(), points, clock=clock, sleep=clock.sleep)
    arm = MEDIA[medium]['holding_arm']
    policy = SimulatedPolicy(medium, points['poses']['scan_' + arm])
    return Cycle(motion, policy, FakeScanner(token), medium, tmp_path / 'cycles.csv',
                 dry_run=True, outcome=lambda: 'success')


def test_unknown_policy_type_is_rejected():
    with pytest.raises(ValueError, match='Unknown policy type'):
        interface.load_policy('not_registered', 'poly_mailer', 'model.pth')


def test_registered_policy_is_selectable_from_the_cycle(monkeypatch, tmp_path):
    built = []

    def loader(medium, checkpoint, **options):
        built.append((medium, str(checkpoint), options))
        return SimulatedPolicy(medium, simulation_waypoints()['poses']['scan_right'])

    monkeypatch.setitem(interface.POLICY_LOADERS, 'example', loader)
    monkeypatch.setattr(inference_safety, 'commanded_workspace_ok', lambda action, config: True)
    status = run_cycle.main(['--medium', 'poly_mailer', '--dry-run', '--policy', 'example',
                             '--checkpoint', 'model.bin', '--fake-token', 'DEST-A-S138683',
                             '--waypoints', str(tmp_path / 'missing.yaml'), '--csv', str(tmp_path / 'c.csv')])
    assert status == 0
    assert built == [('poly_mailer', 'model.bin', {})]


def test_act_options_require_the_robomimic_policy(monkeypatch):
    monkeypatch.setitem(interface.POLICY_LOADERS, 'example', lambda *args, **kwargs: None)
    with pytest.raises(SystemExit):
        run_cycle.main(['--medium', 'poly_mailer', '--dry-run', '--policy', 'example',
                        '--checkpoint', 'model.bin', '--act-temporal-ensemble'])


def test_skills_run_individually(monkeypatch, tmp_path):
    cycle = simulated_cycle(tmp_path, monkeypatch)
    cycle.require_home()
    cycle.pick(cycle.motion.clock())
    event = cycle.scan('standalone')
    assert event['barcode'] == 'DEST-A-S138683' and event['bin_index'] == 0
    cycle.place(event['bin_index'])
    assert cycle.motion.env.commands[-1][[6, 13]].tolist() == [RUNTIME['open_gripper_command']] * 2


def test_media_lists_follow_settings():
    assert dataset_metadata.MEDIA == tuple(MEDIA)
