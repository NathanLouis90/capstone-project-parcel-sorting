"""Start the follower and gripper server used by recording, checks and cycles."""
from config.settings import LAUNCH_NODES

from dataclasses import dataclass
import tyro
from parcel_sorting.hardware.robots.dobot import DobotRobot
from parcel_sorting.hardware.robots.robot import BimanualRobot, PrintRobot
from parcel_sorting.hardware.robots.robot_node import ZMQServerRobot


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
