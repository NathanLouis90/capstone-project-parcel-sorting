"""The policy-step contract and the registry of policy types the supervisor can run.

Any strategy that produces joint/gripper targets from camera images and joint
positions plugs in here (robomimic ACT/DP today; a VLA or another learner later).

To add a policy type:
1. Write a class with ``policy_type``, ``reset()`` and ``step(observation)``
   (optionally ``warmup(observation)``) in a new module under this package.
2. Add a loader to ``POLICY_LOADERS``. Import heavy dependencies inside the
   loader so the supervisor starts without them.
3. ``evaluation/run_cycle.py --policy NAME`` then runs it through the same
   validated motion loop, handoff check, scan and placement.
"""
from typing import Dict, Protocol

import numpy as np


class Policy(Protocol):
    """One control step at 25 Hz.

    ``observation`` is ``{"qpos": 14 floats, "images": {"top", "left_wrist",
    "right_wrist": HxWx3 uint8 RGB}}``. ``step`` returns 14 floats: left J1–J6,
    left gripper, right J1–J6, right gripper (gripper 1.0 open, 0.0 closed).
    Every returned action is validated before it reaches the robot.
    """

    policy_type: str

    def reset(self) -> None:
        ...

    def step(self, observation: Dict) -> np.ndarray:
        ...


def _load_robomimic(medium, checkpoint, **options):
    from parcel_sorting.policies.robomimic_policy import RobomimicPolicy
    return RobomimicPolicy(medium, checkpoint, **options)


POLICY_LOADERS = {
    'robomimic': _load_robomimic,
}


def load_policy(kind, medium, checkpoint, **options):
    """Build a registered policy for one medium from its checkpoint."""
    if kind not in POLICY_LOADERS:
        raise ValueError('Unknown policy type {!r}; choose from {}'.format(kind, ', '.join(sorted(POLICY_LOADERS))))
    return POLICY_LOADERS[kind](medium, checkpoint, **options)
