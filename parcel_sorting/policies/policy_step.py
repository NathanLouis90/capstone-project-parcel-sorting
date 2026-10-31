"""Policy-step helpers shared by the cycle supervisor: idle-arm parking and a simulated policy."""
import numpy as np
from config.settings import MEDIA, RUNTIME
from parcel_sorting.safety.handoff import home_action


def park_idle_arm(action, medium):
    action=np.asarray(action,dtype=float).copy()
    if action.shape != (14,) or not np.isfinite(action).all():
        raise ValueError('Policy must produce 14 finite actions')
    for offset,enabled in zip((0,7),MEDIA[medium]['active_arms']):
        if not enabled: action[offset:offset+7]=home_action()[offset:offset+7]
    action[[6,13]]=np.clip(action[[6,13]],0,1)
    return action


class SimulatedPolicy:
    policy_type='ACT'

    def __init__(self, medium, scan_joints):
        self.medium,self.scan_joints=medium,np.asarray(scan_joints)
        self.reset()

    def reset(self): self.steps=0

    def step(self, observation):
        action=observation['qpos'].copy()
        offset=0 if MEDIA[self.medium]['holding_arm']=='left' else 7
        action[offset:offset+6]+=np.clip(self.scan_joints-action[offset:offset+6],-.01,.01)
        action[offset+6]=RUNTIME['closed_gripper_command']  # simulated grasp
        self.steps+=1
        return action
