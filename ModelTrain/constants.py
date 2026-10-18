"""Dobot training tasks share the per-medium dataset registry."""
from pathlib import Path
from scripts.scripts_config import PREPARE_ACT_DATASETS

DATASETS_ROOT = Path(PREPARE_ACT_DATASETS['root_dir']).expanduser().resolve()
TASK_CONFIGS = {
    name: dict(dataset_dir=str(DATASETS_ROOT / name / 'train_data'),
               episode_len=project['episode_len'], train_ratio=project['train_ratio'],
               camera_names=list(project['camera_names']), medium=project['medium'])
    for name, project in PREPARE_ACT_DATASETS['projects'].items()
}
DT = 0.04
FPS = 25
