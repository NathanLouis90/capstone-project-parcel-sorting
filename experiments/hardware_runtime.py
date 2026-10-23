"""Hardware resources for the supervisor; importing this module opens no devices."""
import threading
import time
from experiments.experiments_config import LAUNCH_NODES, RUN_INFERENCE


class LiveRuntime:
    def __init__(self, with_cameras=True):
        self.controllers=[]; self.cameras=[]; self.threads=[]; self.frames={}
        self.running=threading.Event(); self.running.set()
        self.lock=threading.Lock(); self.error=None; self.robot=None
        try:
            from experiments.robot_home import Channel
            # Emergency stops use dashboard sockets independent of the ZMQ stream.
            for ip in (LAUNCH_NODES['left_robot_ip'],LAUNCH_NODES['right_robot_ip']):
                self.controllers.append(Channel(ip,29999))
            from dobot_control.env import RobotEnv
            from dobot_control.robots.robot_node import ZMQClientRobot
            import zmq
            self.robot=ZMQClientRobot(port=LAUNCH_NODES['robot_port'],host=LAUNCH_NODES['hostname'])
            self.robot._socket.setsockopt(zmq.RCVTIMEO,1000)
            self.robot._socket.setsockopt(zmq.SNDTIMEO,1000)
            self.env=RobotEnv(self.robot)
            self.health()
            if not with_cameras:
                return
            from dobot_control.cameras.realsense_camera import RealSenseCamera
            from scripts.manipulate_utils import load_ini_data_camera
            ids=load_ini_data_camera()
            for name,identity,flip in (('top',ids['top'],RUN_INFERENCE['flip_top_right']),
                                       ('left_wrist',ids['left'],RUN_INFERENCE['flip_left']),
                                       ('right_wrist',ids['right'],RUN_INFERENCE['flip_top_right'])):
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
        from experiments.robot_home import status, require_no_alarms
        for dashboard in self.controllers:
            mode,alarms=status(dashboard); require_no_alarms(alarms)
            if mode not in (5,7,8): raise RuntimeError('Controller not enabled for servo commands: {}'.format(mode))

    def images(self):
        self.health()
        with self.lock:
            if len(self.frames)!=3 or any(time.monotonic()-stamp>.5 for _,stamp in self.frames.values()):
                raise RuntimeError('Camera frames are stale or missing')
            return {name:image.copy() for name,(image,_) in self.frames.items()}

    def stop(self):
        errors=[]
        for dashboard in self.controllers:
            try: dashboard.command('EmergencyStop()')
            except Exception as error: errors.append(str(error))
        if errors: raise RuntimeError('Stop acknowledgement failed: '+'; '.join(errors))

    def close(self):
        self.running.clear()
        for camera in self.cameras:
            try: camera._pipeline.stop()
            except Exception: pass
        for thread in self.threads: thread.join(timeout=1)
        for dashboard in self.controllers: dashboard.close()
        if self.robot is not None:
            self.robot._socket.close(linger=0); self.robot._context.term()
