import csv
import numpy as np
import pytest
from experiments.run_cycle import Cycle, FakeScanner, run_attempts
from experiments.run_inference import SimulatedPolicy
from experiments.scripted_motion import MotionLoop, SimulatedEnv, VirtualClock, simulation_waypoints
from experiments.experiments_config import MEDIA


def build(tmp_path, medium='poly_mailer', token='DEST-A-S138683', outcome='success'):
    clock=VirtualClock(); points=simulation_waypoints(); env=SimulatedEnv()
    motion=MotionLoop(env,points,clock=clock,sleep=clock.sleep)
    arm=MEDIA[medium]['holding_arm']
    policy=SimulatedPolicy(medium,points['poses']['scan_'+arm])
    cycle=Cycle(motion,policy,FakeScanner(token),medium,tmp_path/'cycles.csv',dry_run=True,
                outcome=lambda:outcome,cause=lambda:'tilted_in_grip')
    return cycle


@pytest.mark.parametrize('medium', ['envelope','poly_mailer','carton'])
def test_success_returns_home_and_operator_confirms(tmp_path,medium):
    cycle=build(tmp_path,medium,outcome='wrong_bin')
    row=cycle.run()
    assert row['outcome']=='wrong_bin'
    assert row['bin']==0
    assert row['rotations_to_read']==0
    from experiments.handoff import home_action
    np.testing.assert_allclose(cycle.motion.last_action,home_action())
    assert len(list(csv.DictReader((tmp_path/'cycles.csv').open())))==1


@pytest.mark.parametrize('medium,rotations', [('envelope',1),('poly_mailer',1),('carton',3)])
def test_no_read_returns_to_receiving_without_bin_choice(tmp_path,medium,rotations):
    cycle=build(tmp_path,medium,token=None)
    routes=[]; original=cycle.motion.route
    def route(name,*args,**kwargs):
        routes.append(name); return original(name,*args,**kwargs)
    cycle.motion.route=route
    row=cycle.run()
    assert row['outcome']=='no_read',row
    assert row['rotations_to_read']==rotations
    assert row['bin']==row['token']==''
    assert row['no_read_cause']=='tilted_in_grip'
    assert routes==['drop_receiving_'+MEDIA[medium]['holding_arm']]


def test_retry_has_new_id_and_stops_after_second_failure(tmp_path):
    cycle=build(tmp_path,token=None)
    rows=run_attempts(cycle,retry=lambda row:True)
    assert len(rows)==2
    assert rows[0]['cycle_id']!=rows[1]['cycle_id']
    assert rows[0]['retry_of']==''
    assert rows[1]['retry_of']==rows[0]['cycle_id']


def test_fault_stops_without_releasing_or_homing(tmp_path):
    cycle=build(tmp_path)
    cycle.policy.step=lambda obs:np.full(14,np.nan)
    cycle.motion.home=lambda arm:pytest.fail('No homing after a fault')
    row=cycle.run()
    assert row['outcome']=='fault'
    assert cycle.motion.halted and cycle.motion.env.stopped
    assert len(cycle.motion.env.commands)==0


def test_policy_never_receives_scanner_or_label_input(tmp_path):
    cycle=build(tmp_path)
    original=cycle.policy.step
    def step(obs):
        assert set(obs)=={'qpos','images'}
        return original(obs)
    cycle.policy.step=step
    assert cycle.run()['outcome']=='success'


def test_unknown_token_never_selects_a_bin(tmp_path):
    cycle=build(tmp_path,token='NOT-A-DESTINATION')
    assert cycle.run()['outcome']=='no_read'


def test_read_after_second_carton_face_stops_further_rotations(tmp_path):
    cycle=build(tmp_path,'carton')
    cycle.scanner=FakeScanner('DEST-A-S138683',rotations_to_read=2)
    initial=cycle.motion.last_action[5]
    row=cycle.run()
    assert row['outcome']=='success'
    assert row['rotations_to_read']==2
    assert max(command[5] for command in cycle.motion.env.commands)==pytest.approx(initial+np.pi)


def test_policy_timeout_is_fault_without_automatic_homing(tmp_path):
    cycle=build(tmp_path)
    cycle.policy.step=lambda obs:obs['qpos']
    cycle.motion.home=lambda arm:pytest.fail('Do not home after a timeout')
    row=cycle.run()
    assert row['outcome']=='fault'
    assert 'timeout' in row['fault_detail']
    assert cycle.motion.halted


def test_incompatible_log_is_rejected_before_motion(tmp_path):
    cycle=build(tmp_path)
    (tmp_path/'cycles.csv').write_text('unrelated,columns\n')
    with pytest.raises(ValueError,match='CSV columns'): cycle.run()
    assert not cycle.motion.env.commands


def test_live_smoke_checkpoint_rejected_before_hardware(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import yaml
    import experiments.robomimic_runner as runner
    import experiments.hardware_runtime as hardware
    from experiments.run_cycle import main
    points=simulation_waypoints(); points['commissioned']=True
    path=tmp_path/'points.yaml'; path.write_text(yaml.safe_dump(points))
    monkeypatch.setattr(runner,'RobomimicPolicy',lambda *args:SimpleNamespace(smoke_checkpoint=True))
    monkeypatch.setattr(hardware,'LiveRuntime',lambda:pytest.fail('Smoke checkpoint must not open hardware'))
    with pytest.raises(SystemExit) as error:
        main(['--medium','poly_mailer','--live','--backend','robomimic',
              '--checkpoint',str(tmp_path/'smoke.pth'),'--waypoints',str(path)])
    assert error.value.code==2
