if __package__:
    from .scripts_config import SCRIPT_4_COLLECT2TRAIN_DATA
else:
    from scripts_config import SCRIPT_4_COLLECT2TRAIN_DATA

import os
import sys
import subprocess
from pathlib import Path


root_dir = SCRIPT_4_COLLECT2TRAIN_DATA["root_dir"]
dataset_name = SCRIPT_4_COLLECT2TRAIN_DATA["dataset_name"]

dataset_dir = root_dir + "/" + dataset_name + "/collect_data/"
all_data_dir = os.listdir(dataset_dir)
all_data_dir.sort(key=lambda x: int(x))
print(all_data_dir)

idx = 0
for i in all_data_dir:
    print("dealing with: ", i)
    CMD = [
        sys.executable, str(Path(__file__).resolve().parent / "script_collect2train.py"),
        '--root_dir', str(root_dir),
        '--dataset_name', str(dataset_name),
        '--date_collect', i,
        '--idx', str(idx)
    ]
    rt_code = subprocess.call(CMD)
    if rt_code:
        break
    idx+=1