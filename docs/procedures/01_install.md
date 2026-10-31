# Install the software on a new PC

At the end you have the `Xtrainer` conda environment with the full recording, training and test stack, and a passing test suite.

## Before you start

- Ubuntu 20.04, as in sections 3–4 of the [Dobot X-Trainer (Lightweight Base) User Guide V1.1](../provided_dobot/Dobot%20X-Trainer%20%28Lightweight%20Base%29%20User%20Guide%20V1.1_20240731_en.pdf).
- [Anaconda](https://www.anaconda.com/download) installed.
- For training: an NVIDIA driver for your GPU, CUDA 11.8 and matching cuDNN, installed as the User Guide describes.
- Internet access and an administrator (sudo) account.
- No robot, camera or leader is needed for this procedure.

## Steps

1. Install the system packages.

   ```bash
   sudo apt update
   sudo apt install git build-essential linux-libc-dev libxcb-cursor0
   ```

   Expect: apt finishes without errors.

2. Clone the repository into your home folder and enter it.

   ```bash
   cd ~
   git clone https://github.com/NathanLouis90/capstone-project-parcel-sorting.git dobot_xtrainer
   cd ~/dobot_xtrainer
   ```

   Expect: the folder contains `README.md`, `config/`, `setup/` and `robot/`.
   The guides assume `~/dobot_xtrainer`. Replace the path if your checkout is elsewhere.

3. Create and activate the Python 3.8.10 environment.

   ```bash
   conda create -n Xtrainer python=3.8.10
   conda activate Xtrainer
   ```

   Expect: the prompt starts with `(Xtrainer)`.

4. Install PyTorch for CUDA 11.8.

   ```bash
   python3 -m pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
   ```

   Expect: `Successfully installed torch-2.0.1 ...`.

5. Install the dependencies and bundled packages, in this order.

   ```bash
   python3 -m pip install -r requirements.txt
   python3 -m pip install -e third_party/DynamixelSDK/python
   python3 -m pip install -e third_party/act/act/detr
   python3 -m pip install -r requirements-robomimic.txt
   python3 -m pip install --no-deps -e robomimic-r2d2
   python3 -m pip install --no-deps -e .
   ```

   Expect: each command ends with `Successfully installed ...` or `Requirement already satisfied`.

6. Check that PyTorch can use the GPU.

   ```bash
   python3 -c "import torch; print('CUDA available:', torch.cuda.is_available())"
   ```

   Expect: `CUDA available: True`. Training needs this; recording and robot checks do not.

7. Run the hardware-free test suite.

   ```bash
   python3 -m pytest
   ```

   Expect: every test passes (`N passed`). Warnings are fine.

## Every new terminal

Prepare each terminal you open later with:

```bash
conda activate Xtrainer
cd ~/dobot_xtrainer
```

Continue with [hardware setup](02_hardware_setup.md).

## If something goes wrong

- `CUDA available: False` -> check `nvidia-smi`, then reinstall the driver/CUDA 11.8 as in the User Guide and repeat step 4.
- `ModuleNotFoundError` for `parcel_sorting`, `config`, `robomimic` or `detr` -> repeat step 5 in the activated `Xtrainer` environment.
- `requirements.txt` installed but training imports fail -> both requirement files and all editable installs in step 5 are needed.
- Tests fail -> run `python3 -m pytest -x` to stop at the first failure and read its message; see [tests reference](../reference/tests.md).
- Unsure what a command part means -> see the [command reference](../reference/commands.md).
