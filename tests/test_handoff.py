import numpy as np
from experiments.handoff import home_action, HandoffCheck
from scripts.dataset_checks import episode_warnings


def recording():
    home = home_action()
    target = home.copy()
    target[0] += 0.3
    frames = np.vstack([home, np.tile(target, (30, 1))])
    metadata = dict(medium='poly_mailer', label_face='bottom', frame_count=len(frames),
                    started_at=0, ended_at=len(frames)*.04, control_period_ms=40)
    return target, frames, metadata


def test_scan_pose_end_passes():
    target, frames, metadata = recording()
    assert episode_warnings(frames, metadata, waypoints={'scan_left': target[:6]})[1] == []


def test_home_end_fails_scan_check():
    target, frames, metadata = recording()
    frames[-20:] = home_action()
    assert any('End must hold' in w for w in episode_warnings(frames, metadata, waypoints={'scan_left': target[:6]})[1])


def test_motion_and_idle_arm_reset_settling():
    target, _, _ = recording()
    check = HandoffCheck('poly_mailer', target[:6])
    assert not check.update(target, 0)
    for i in range(1,15):
        ready=check.update(target, i*.04)
    assert ready
    moving=target.copy(); moving[7]+=.3
    assert not check.update(moving,.6)
    assert not check.update(target,.64)


def test_wrist_orientation_and_gripper_are_checked():
    target, _, _ = recording()
    for index, delta in [(5,.4),(6,-1)]:
        check=HandoffCheck('poly_mailer',target[:6]); bad=target.copy(); bad[index]+=delta
        assert not any(check.update(bad,i*.04) for i in range(30))
