"""Policy-step interface used by the parcel cycle supervisor."""
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from experiments.experiments_config import MEDIA
from experiments.handoff import home_action
from experiments.inference_safety import prepare_vendor_action


class VendorPolicy:
    policy_type='ACT'

    def __init__(self, medium, checkpoint_dir, model_name='policy_best.ckpt'):
        from experiments.act_checkpoint import load_act_checkpoint
        self.medium=medium
        self.model=load_act_checkpoint(checkpoint_dir,model_name,medium)
        self.reset()

    def reset(self):
        self.steps=0
        if hasattr(self.model,'reset'): self.model.reset()
        # The vendor predictor indexes temporal state by rollout timestep.
        for name in ('all_time_actions', 'all_actions'):
            value=getattr(self.model,name,None)
            if hasattr(value,'zero_'): value.zero_()

    def step(self, observation):
        # The camera source is RGB. The vendor was trained on OpenCV BGR files.
        inputs=dict(qpos=observation['qpos'], images={
            key:image[:,:,::-1].copy() for key,image in observation['images'].items()})
        action=prepare_vendor_action(self.model.predict(inputs,self.steps))
        self.steps+=1
        return park_idle_arm(action,self.medium)


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
        self.steps+=1
        return action
