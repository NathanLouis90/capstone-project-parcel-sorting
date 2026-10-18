from pathlib import Path as _ConfigPath
import sys as _config_sys
_config_sys.path.insert(0, str(_ConfigPath(__file__).resolve().parent))
from experiments_config import LAUNCH_NODES

import sys
import os
# 获取根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
from dataclasses import dataclass
import tyro
from dobot_control.robots.dobot import DobotRobot
from dobot_control.robots.robot import BimanualRobot, PrintRobot
from dobot_control.robots.robot_node import ZMQServerRobot


@dataclass
class Args:
    robot_port: int = LAUNCH_NODES["robot_port"]
    hostname: str = LAUNCH_NODES["hostname"]


def launch_robot_server(args: Args):
    port = args.robot_port
    _robot_l = DobotRobot(robot_ip=LAUNCH_NODES["left_robot_ip"], robot_number=LAUNCH_NODES["robot_number"])  # IP of the left hand robotic arm
    _robot_r = DobotRobot(robot_ip=LAUNCH_NODES["right_robot_ip"], robot_number=LAUNCH_NODES["robot_number"])  # IP of the rigth hand robotic arm
    robot = BimanualRobot(_robot_l, _robot_r)
    server = ZMQServerRobot(robot, port=port, host=args.hostname)
    print(f"Starting robot server on port {port}")
    server.serve()


def main(args):
    launch_robot_server(args)


if __name__ == "__main__":
    main(tyro.cli(Args))
