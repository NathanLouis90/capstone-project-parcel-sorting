"""Hardware resources for the supervisor; importing this module opens no devices."""
import threading
import time
import numpy as np
from config.settings import CONTROLLED_STOP, LAUNCH_NODES, RUNTIME
from parcel_sorting.safety.inference_safety import JOINT_INDICES


class LiveRuntime:
    def __init__(self, with_cameras=True):
        self.cameras=[]; self.threads=[]; self.frames={}
        self.running=threading.Event(); self.running.set()
        self.lock=threading.Lock(); self.error=None; self.robot=None; self.stop_robot=None
        try:
            from parcel_sorting.hardware.env import RobotEnv
            from parcel_sorting.hardware.robots.robot_node import ZMQClientRobot
            import zmq
            self.robot=ZMQClientRobot(port=LAUNCH_NODES['robot_port'],host=LAUNCH_NODES['hostname'])
            self.robot._socket.setsockopt(zmq.RCVTIMEO,1000)
            self.robot._socket.setsockopt(zmq.SNDTIMEO,1000)
            capabilities=self.robot.get_observations().get('server_capabilities', [])
            if not {'get_controller_status', 'controlled_stop', 'emergency_stop'}.issubset(capabilities):
                raise RuntimeError('Restart robot/launch_nodes.py to load controller status/stop support')
            # Dashboard port 29999 accepts one client. The launcher owns it.
            # Keep a separate ZMQ request socket for stops after a main-socket timeout.
            self.stop_robot=ZMQClientRobot(port=LAUNCH_NODES['robot_port'],host=LAUNCH_NODES['hostname'])
            self.stop_robot._socket.setsockopt(zmq.RCVTIMEO,1000)
            self.stop_robot._socket.setsockopt(zmq.SNDTIMEO,1000)
            # After a timed-out stop request, still allow the emergency-stop request.
            self.stop_robot._socket.setsockopt(zmq.REQ_RELAXED,1)
            self.stop_robot._socket.setsockopt(zmq.REQ_CORRELATE,1)
            self.env=RobotEnv(self.robot)
            self.health()
            if not with_cameras:
                return
            from parcel_sorting.hardware.cameras.realsense_camera import RealSenseCamera
            from parcel_sorting.hardware.manipulate_utils import load_ini_data_camera
            ids=load_ini_data_camera()
            for name,identity,flip in (('top',ids['top'],RUNTIME['flip_top_right']),
                                       ('left_wrist',ids['left'],RUNTIME['flip_left']),
                                       ('right_wrist',ids['right'],RUNTIME['flip_top_right'])):
                camera=RealSenseCamera(device_id=identity,flip=flip); self.cameras.append(camera)
                thread=threading.Thread(target=self._read,args=(camera,name),daemon=True)
                thread.start(); self.threads.append(thread)
            deadline=time.monotonic()+10
            while len(self.frames)!=3:
                self.health()
                if time.monotonic()>=deadline: raise TimeoutError('All cameras must supply images')
                time.sleep(.02)
        except BaseException:
            self.close()
            raise

    def _read(self,camera,name):
        try:
            while self.running.is_set():
                image,_=camera.read()
                with self.lock: self.frames[name]=(image,time.monotonic())
        except Exception as error:
            if self.running.is_set(): self.error=str(error)

    def health(self):
        if self.error: raise RuntimeError('Camera failure: '+self.error)
        from parcel_sorting.hardware.robot_home import require_no_alarms
        states=self.robot.get_controller_status()
        for arm in ('left', 'right'):
            mode,alarms=states[arm]['mode'],states[arm]['alarms']
            require_no_alarms(alarms)
            if mode not in (5,7,8):
                raise RuntimeError('{} controller not enabled for servo commands: {}'.format(arm,mode))

    def images(self):
        self.health()
        with self.lock:
            if len(self.frames)!=3 or any(time.monotonic()-stamp>.5 for _,stamp in self.frames.values()):
                raise RuntimeError('Camera frames are stale or missing')
            return {name:image.copy() for name,(image,_) in self.frames.items()}

    def stop(self):
        """Prefer a verified controlled stop; request an emergency stop otherwise.

        A software EmergencyStop() powers both arms off, and on this installation
        clearing its alarm 116 has required power-cycling the controllers.
        """
        try:
            self.stop_robot.controlled_stop()
            self.confirm_stopped()
        except Exception as error:
            reason=str(error) or type(error).__name__
            print('Controlled stop not confirmed ({}); requesting emergency stop.'.format(reason),flush=True)
            self.stop_robot.emergency_stop()
            return 'controlled stop not confirmed ({}); emergency stop requested'.format(reason)
        print('Controlled stop confirmed: both arms idle, powered, and holding position.',flush=True)
        return 'controlled stop confirmed'

    def confirm_stopped(self):
        from parcel_sorting.hardware.robot_home import require_no_alarms
        settings=CONTROLLED_STOP
        deadline=time.monotonic()+settings['timeout_s']
        previous=None; still=0
        while True:
            states=self.stop_robot.get_controller_status()
            for arm in ('left','right'):
                require_no_alarms(states[arm]['alarms'])
            idle=all(states[arm]['mode'] in (4,5) for arm in ('left','right'))
            joints=np.asarray(self.stop_robot.get_joint_state(),dtype=float)
            if joints.shape!=(14,) or not np.isfinite(joints).all():
                raise RuntimeError('Invalid joint feedback while confirming the stop')
            steady=previous is not None and np.max(np.abs(
                joints[list(JOINT_INDICES)]-previous[list(JOINT_INDICES)]))<=settings['still_tolerance_rad']
            still=still+1 if idle and steady else 0
            if still>=settings['still_samples']:
                return
            if time.monotonic()>=deadline:
                raise TimeoutError('Arms were not idle and still within {} s; last modes {}'.format(
                    settings['timeout_s'],{arm:states[arm]['mode'] for arm in ('left','right')}))
            previous=joints
            time.sleep(settings['poll_interval_s'])

    def close(self):
        self.running.clear()
        for camera in self.cameras:
            try: camera._pipeline.stop()
            except Exception: pass
        for thread in self.threads: thread.join(timeout=1)
        for robot in (self.robot, self.stop_robot):
            if robot is not None:
                robot._socket.close(linger=0); robot._context.term()
