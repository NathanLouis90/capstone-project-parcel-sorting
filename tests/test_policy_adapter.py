from collections import deque
import numpy as np
import pytest
from experiments.robomimic_runner import RobomimicPolicy


def adapter(horizon):
    result=RobomimicPolicy.__new__(RobomimicPolicy)
    result.medium='poly_mailer'; result.horizon=horizon
    result.shapes={name:(3,8,8) for name in ('top','left_wrist','right_wrist')}
    class Policy:
        def start_episode(self): self.inputs=[]
        def __call__(self,inputs):
            self.inputs.append(inputs)
            return np.zeros(14)
    result.policy=Policy(); result.reset()
    return result


def observation(value):
    return dict(qpos=np.full(14,value,dtype=float),
                images={name:np.full((12,12,3),[200,40,10],dtype=np.uint8)
                        for name in ('top','left_wrist','right_wrist')})


def test_diffusion_frame_history_pads_then_advances_and_resets():
    policy=adapter(2)
    policy.step(observation(1)); policy.step(observation(2))
    first,second=policy.policy.inputs
    np.testing.assert_array_equal(first['qpos'],np.ones((2,14)))
    assert second['qpos'][0,0]==1 and second['qpos'][1,0]==2
    assert second['top'][0,0,0].tolist()==[200,40,10]
    policy.reset(); policy.step(observation(3))
    np.testing.assert_array_equal(policy.policy.inputs[0]['qpos'],np.full((2,14),3))


def test_act_uses_single_frame_and_parks_idle_arm():
    policy=adapter(1); action=policy.step(observation(1))
    assert policy.policy.inputs[0]['qpos'].shape==(14,)
    from experiments.handoff import home_action
    np.testing.assert_allclose(action[7:],home_action()[7:])


def test_nonfinite_policy_output_is_rejected():
    from experiments.run_inference import park_idle_arm
    with pytest.raises(ValueError): park_idle_arm(np.full(14,np.nan),'carton')
