"""Run saved robomimic ACT/DP policies through the common policy-step interface."""
import argparse
from collections import deque
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'robomimic-r2d2'))
from experiments.run_inference import park_idle_arm


def checkpoint_medium_matches(saved, config, medium):
    """Prefer recorded dataset identity; retain support for older named runs."""
    metadata = saved.get('env_metadata') or {}
    recorded = (metadata.get('env_kwargs') or {}).get('medium')
    if recorded is not None:
        return recorded == medium
    return config['experiment']['name'].startswith(medium + '_')


class RobomimicPolicy:
    def __init__(self,medium,checkpoint,device=None):
        import torch
        import robomimic.utils.file_utils as files
        checkpoint=Path(checkpoint).expanduser().resolve()
        if not checkpoint.is_file(): raise ValueError('Missing checkpoint: '+str(checkpoint))
        # Trusted locally trained checkpoints only, as with the vendor loader.
        saved=torch.load(str(checkpoint),map_location='cpu')
        self.config=json.loads(saved['config'])
        self.smoke_checkpoint=self.config['experiment']['name'].endswith('_smoke')
        algorithm=saved['algo_name']
        if algorithm not in ('act','diffusion_policy'): raise ValueError('Expected ACT or DP checkpoint')
        if not checkpoint_medium_matches(saved,self.config,medium):
            raise ValueError('Checkpoint medium differs from requested medium')
        expected={'qpos','top','left_wrist','right_wrist'}
        if set(saved['shape_metadata']['all_shapes'])!=expected:
            raise ValueError('Checkpoint must use only joints and the three cameras')
        if saved['shape_metadata']['ac_dim']!=14:
            raise ValueError('Checkpoint must produce 14 actions')
        if not saved.get('action_normalization_stats') or not saved.get('obs_normalization_stats'):
            raise ValueError('Checkpoint must include training observation/action normalization')
        self.medium,self.policy_type=medium,'ACT' if algorithm=='act' else 'DP'
        self.policy,self.saved=files.policy_from_checkpoint(ckpt_dict=saved,device=device)
        self.horizon=int(self.config['train']['frame_stack'])
        self.shapes=saved['shape_metadata']['all_shapes']
        self.reset()

    def reset(self):
        self.policy.start_episode()
        self.history=deque(maxlen=self.horizon)
        self.steps=0

    def warmup(self,observation):
        self.reset()
        self.step(observation)
        self.reset()

    def step(self,observation):
        import cv2
        qpos=np.asarray(observation['qpos'],dtype=np.float32)
        if qpos.shape!=(14,) or not np.isfinite(qpos).all(): raise ValueError('Invalid joint observation')
        current={'qpos':qpos}
        for camera in ('top','left_wrist','right_wrist'):
            image=observation['images'][camera]
            if image.ndim!=3 or image.shape[2]!=3: raise ValueError('Expected RGB camera frame')
            channels,height,width=self.shapes[camera]
            if channels!=3: raise ValueError('Expected three image channels')
            current[camera]=cv2.resize(image,(width,height),interpolation=cv2.INTER_AREA).astype(np.uint8)
        if not self.history:
            self.history.extend([current]*self.horizon)
        else:
            self.history.append(current)
        inputs=current if self.horizon==1 else {
            key:np.stack([frame[key] for frame in self.history]) for key in current}
        import torch
        with torch.no_grad(): action=self.policy(inputs)
        self.steps+=1
        return park_idle_arm(action,self.medium)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--medium',choices=('envelope','poly_mailer','carton'),required=True)
    parser.add_argument('--dry-run',action='store_true',required=True)
    parser.add_argument('--steps',type=int,default=3)
    args=parser.parse_args(argv)
    import torch
    torch.set_num_threads(1)
    policy=RobomimicPolicy(args.medium,args.checkpoint,device=torch.device('cpu'))
    from experiments.handoff import home_action
    obs={'qpos':home_action(),'images':{key:np.zeros((128,128,3),dtype=np.uint8)
                                      for key in ('top','left_wrist','right_wrist')}}
    for i in range(args.steps):
        action=policy.step(obs)
        print(json.dumps(dict(step=i,policy_type=policy.policy_type,action=action.tolist())))
    print('Checkpoint stepped without hardware; predictions were not sent to a robot')


if __name__ == '__main__': main()
