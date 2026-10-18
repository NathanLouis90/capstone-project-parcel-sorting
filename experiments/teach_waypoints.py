"""Capture follower joints after manual positioning; never issue a motion command."""
import argparse
from pathlib import Path
import sys
import time
import yaml
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from experiments.experiments_config import SUPERVISOR, LAUNCH_NODES
from experiments.scripted_motion import simulation_waypoints


def save_pose(path, name, joints):
    path = Path(path)
    if not name.endswith(('_left', '_right')):
        raise ValueError('Name must end in _left or _right')
    joints=np.asarray(joints, dtype=float)
    if joints.shape != (6,) or not np.isfinite(joints).all():
        raise ValueError('Expected six finite joint angles')
    value=yaml.safe_load(path.read_text()) if path.exists() else dict(
        units='radians', commissioned=False, poses={}, routes={}, joint_limits_rad=None)
    value['poses'][name]=joints.tolist()
    value['commissioned']=False
    path.parent.mkdir(parents=True,exist_ok=True)
    from barcode_scanning.recording import write_metadata
    # JSON is valid YAML; atomic replacement avoids partial taught files.
    write_metadata(path,value)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', help='scan_left, scan_right, drop_bin0_left, etc.')
    parser.add_argument('--output', type=Path, default=Path(SUPERVISOR['waypoint_file']))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    args=parser.parse_args(argv)
    if args.dry_run:
        if args.output.exists() and not args.overwrite: parser.error('Output exists; choose another file')
        args.output.write_text(yaml.safe_dump(simulation_waypoints(),sort_keys=False))
        print('Wrote simulation-only waypoints; these are not calibrated robot poses')
        return
    if not args.name: parser.error('--name is required')
    if args.output.exists():
        saved=yaml.safe_load(args.output.read_text())
        if args.name in saved.get('poses',{}) and not args.overwrite:
            parser.error('Pose exists; use --overwrite to replace it')
    from dobot_control.robots.robot_node import ZMQClientRobot
    # Use the controller's manual drag mode and disable drag before capture.
    robot=ZMQClientRobot(port=LAUNCH_NODES['robot_port'],host=LAUNCH_NODES['hostname'])
    offset=0 if args.name.endswith('_left') else 7
    import zmq
    robot._socket.setsockopt(zmq.RCVTIMEO,1000)
    robot._socket.setsockopt(zmq.SNDTIMEO,1000)
    try:
        samples=[]
        for _ in range(3):
            samples.append(np.asarray(robot.get_observations()['joint_positions'])[offset:offset+6])
            time.sleep(.04)
    finally:
        robot._socket.close(linger=0)
        robot._context.term()
    if np.max(np.ptp(samples,axis=0)) > .01: raise ValueError('Stop moving the follower before capture')
    save_pose(args.output,args.name,samples[-1])
    print('Saved '+args.name+'; review limits and routes before commissioning')


if __name__ == '__main__': main()
