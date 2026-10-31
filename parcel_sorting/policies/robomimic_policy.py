"""Run saved robomimic ACT/DP policies through the common policy-step interface."""
import argparse
from collections import deque
import json
from pathlib import Path
import numpy as np
from parcel_sorting.policies.policy_step import park_idle_arm


def checkpoint_medium_matches(saved, config, medium):
    """Prefer recorded dataset identity; retain support for older named runs."""
    metadata = saved.get('env_metadata') or {}
    recorded = (metadata.get('env_kwargs') or {}).get('medium')
    if recorded is not None:
        return recorded == medium
    return config['experiment']['name'].startswith(medium + '_')


STATIONARY_STD_RAD = 0.01


def idle_arm_inputs(qpos_stats, active_arms):
    """Match each arm's runtime role to its training data; return fixed idle-arm inputs.

    Normalization uses the training std, so even a small move by an arm that
    never moved in training is far outside the data. A parked arm is fed its
    training mean, which also covers the gripper channel that tracks commands.
    """
    mean = np.asarray(qpos_stats['mean'], dtype=np.float32).reshape(-1)
    std = np.asarray(qpos_stats['std'], dtype=np.float32).reshape(-1)
    if mean.shape != (14,) or std.shape != (14,):
        raise ValueError('Checkpoint qpos normalization must have 14 values')
    inputs = {}
    for offset, enabled, arm in zip((0, 7), active_arms, ('left', 'right')):
        stationary = bool(np.all(std[offset:offset + 6] < STATIONARY_STD_RAD))
        if enabled and stationary:
            raise ValueError('The {} arm never moved in this checkpoint\'s training data; '
                             'set it inactive for this medium before commanding it'.format(arm))
        if not enabled:
            if not stationary:
                raise ValueError('The {} arm moved in this checkpoint\'s training data but is '
                                 'parked for this medium'.format(arm))
            inputs[offset] = mean[offset:offset + 7].copy()
    return inputs


def add_act_rollout_arguments(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--act-temporal-ensemble', dest='act_temporal_ensemble', action='store_true', default=None,
                       help='Override ACT checkpoint settings: blend overlapping chunks at every control step')
    group.add_argument('--no-act-temporal-ensemble', dest='act_temporal_ensemble', action='store_false')
    parser.add_argument('--act-ensemble-coefficient', type=float, default=None,
                        help='ACT weighting: positive favors older predictions, negative favors newer, zero averages')
    parser.add_argument('--act-query-frequency', type=int, default=None,
                        help='ACT replan interval with ensembling off; 0 executes a full chunk')


def act_rollout_overrides(args):
    return dict(act_temporal_ensemble=args.act_temporal_ensemble,
                act_ensemble_coefficient=args.act_ensemble_coefficient,
                act_query_frequency=args.act_query_frequency)


def apply_act_rollout_overrides(config, algorithm, temporal=None, coefficient=None, query_frequency=None):
    """Update the in-memory load configuration, preserving the checkpoint on disk."""
    if algorithm != 'act':
        if any(value is not None for value in (temporal, coefficient, query_frequency)):
            raise ValueError('ACT rollout options require an ACT checkpoint')
        return None
    from robomimic.algo.act_rollout import ACTActionSelector
    settings = config['algo']['act']
    effective = ACTActionSelector(
        int(config['train']['seq_length']),
        settings.get('temporal_agg', False) if temporal is None else temporal,
        settings.get('temporal_ensemble_coeff', 0.01) if coefficient is None else coefficient,
        settings.get('query_frequency', 0) if query_frequency is None else query_frequency,
    )
    settings.update(temporal_agg=effective.temporal_agg, temporal_ensemble_coeff=effective.coefficient)
    if query_frequency is not None:
        settings['query_frequency'] = query_frequency
    return dict(temporal_ensemble=effective.temporal_agg, coefficient=effective.coefficient,
                query_frequency=effective.query_frequency, chunk_length=effective.chunk_size)


class RobomimicPolicy:
    def __init__(self,medium,checkpoint,device=None,act_temporal_ensemble=None,
                 act_ensemble_coefficient=None,act_query_frequency=None):
        import torch
        import robomimic.utils.file_utils as files
        checkpoint=Path(checkpoint).expanduser().resolve()
        if not checkpoint.is_file(): raise ValueError('Missing checkpoint: '+str(checkpoint))
        # Load trusted, locally trained checkpoints only.
        saved=torch.load(str(checkpoint),map_location='cpu')
        self.config=json.loads(saved['config'])
        self.smoke_checkpoint=self.config['experiment']['name'].endswith('_smoke')
        algorithm=saved['algo_name']
        if algorithm not in ('act','diffusion_policy'): raise ValueError('Expected ACT or DP checkpoint')
        self.act_rollout_settings = apply_act_rollout_overrides(
            self.config, algorithm, act_temporal_ensemble, act_ensemble_coefficient, act_query_frequency)
        saved['config'] = json.dumps(self.config)
        if not checkpoint_medium_matches(saved,self.config,medium):
            raise ValueError('Checkpoint medium differs from requested medium')
        expected={'qpos','top','left_wrist','right_wrist'}
        if set(saved['shape_metadata']['all_shapes'])!=expected:
            raise ValueError('Checkpoint must use only joints and the three cameras')
        if saved['shape_metadata']['ac_dim']!=14:
            raise ValueError('Checkpoint must produce 14 actions')
        if not saved.get('action_normalization_stats') or not saved.get('obs_normalization_stats'):
            raise ValueError('Checkpoint must include training observation/action normalization')
        from config.settings import MEDIA
        self.idle_inputs=idle_arm_inputs(saved['obs_normalization_stats']['qpos'],MEDIA[medium]['active_arms'])
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
        qpos=qpos.copy()
        for offset,value in self.idle_inputs.items(): qpos[offset:offset+7]=value
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
    from config.settings import MEDIA
    parser.add_argument('--medium',choices=sorted(MEDIA),required=True)
    parser.add_argument('--steps',type=int,default=3)
    add_act_rollout_arguments(parser)
    args=parser.parse_args(argv)
    import torch
    torch.set_num_threads(1)
    policy=RobomimicPolicy(args.medium,args.checkpoint,device=torch.device('cpu'),**act_rollout_overrides(args))
    if policy.act_rollout_settings is not None:
        print('ACT rollout settings: ' + json.dumps(policy.act_rollout_settings, sort_keys=True))
    from parcel_sorting.safety.handoff import home_action
    obs={'qpos':home_action(),'images':{key:np.zeros((128,128,3),dtype=np.uint8)
                                      for key in ('top','left_wrist','right_wrist')}}
    for i in range(args.steps):
        action=policy.step(obs)
        print(json.dumps(dict(step=i,policy_type=policy.policy_type,action=action.tolist())))
    print('Checkpoint stepped without hardware; predictions were not sent to a robot')

