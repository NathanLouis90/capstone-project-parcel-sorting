"""Pick, scan, place and log one parcel; barcode input never reaches a policy."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import sys
import time
import uuid
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from experiments.experiments_config import MEDIA, SUPERVISOR, CONTROL
from experiments.handoff import HandoffCheck, home_action
from experiments.scripted_motion import (MotionLoop, SimulatedEnv, VirtualClock,
                                          simulation_waypoints, load_waypoints)
from experiments.run_inference import SimulatedPolicy, VendorPolicy
from barcode_scanning.scanner_reader import ScanWindow, ScannerReader, destination_mapping

COLUMNS=('cycle_id','retry_of','medium','policy_type','label_face','rotations_to_read','token',
         'bin','outcome','no_read_cause','fault_detail','t_pick_s','t_scan_s','t_place_s','t_total_s',
         'dry_run','control_overruns')
OUTCOMES={'s':'success','g':'grasp_fail','d':'drop','w':'wrong_bin'}
CAUSES={'t':'tilted_in_grip','l':'label_occluded','':'unknown','u':'unknown'}


def read_key(prompt):
    print(prompt,flush=True)
    if not sys.stdin.isatty(): return input().strip().lower()
    import termios
    import tty
    descriptor=sys.stdin.fileno(); previous=termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor); key=sys.stdin.read(1).lower()
        if key=='\x03': raise KeyboardInterrupt
        return '' if key in ('\r','\n') else key
    finally:
        termios.tcsetattr(descriptor,termios.TCSADRAIN,previous)
        print()


def operator_outcome():
    while True:
        key=read_key('Record outcome: [s] success, [g] grasp_fail, [d] drop, [w] wrong_bin')
        if key in OUTCOMES: return OUTCOMES[key]


def operator_cause():
    while True:
        key=read_key('No-read cause (optional): [t] tilted_in_grip, [l] label_occluded, [Enter] unknown')
        if key in CAUSES: return CAUSES[key]


def check_cycle_log(path):
    path=Path(path)
    if path.exists() and path.stat().st_size:
        with path.open(newline='') as stream:
            if next(csv.reader(stream),None)!=list(COLUMNS):
                raise ValueError('Cycle CSV columns differ; select a new log file')


def append_cycle(path,row):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+',newline='') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        stream.seek(0)
        existing=next(csv.reader(stream),None)
        if existing is not None and existing!=list(COLUMNS):
            raise ValueError('Cycle CSV columns differ; select a new log file')
        stream.seek(0,os.SEEK_END); writer=csv.DictWriter(stream,fieldnames=COLUMNS)
        if existing is None: writer.writeheader()
        writer.writerow(row); stream.flush(); os.fsync(stream.fileno())


class Scanner:
    def __init__(self,device=None):
        self.window=ScanWindow(); self.reader=ScannerReader(self.window,device)
        self.reader.start()

    def arm(self,cycle_id): self.window.arm(cycle_id,120)

    def poll(self,rotations=0):
        if self.reader.error: raise RuntimeError('Scanner failure: '+str(self.reader.error))
        return self.window.status()['scan']

    def close(self): self.reader.close()


class FakeScanner:
    def __init__(self,token=None,rotations_to_read=0):
        self.token,self.rotations_to_read=token,rotations_to_read

    def arm(self,cycle_id): self.cycle_id=cycle_id

    def poll(self,rotations=0):
        if self.token in destination_mapping() and rotations>=self.rotations_to_read:
            return dict(barcode=self.token,bin_index=destination_mapping()[self.token],cycle_id=self.cycle_id)
        return None

    def close(self): pass


class Cycle:
    def __init__(self,motion,policy,scanner,medium,csv_path,images=None,dry_run=False,
                 outcome=operator_outcome,cause=operator_cause,label_face='',config=SUPERVISOR):
        self.motion,self.policy,self.scanner=motion,policy,scanner
        self.medium,self.csv_path,self.images=medium,csv_path,images or (lambda:{})
        self.dry_run,self.outcome,self.cause=dry_run,outcome,cause
        self.label_face,self.config=label_face,config

    def run(self,retry_of=''):
        check_cycle_log(self.csv_path)
        motion=self.motion; clock=motion.clock; start=clock()
        before_overruns=motion.overruns
        row={key:'' for key in COLUMNS}
        row.update(cycle_id=uuid.uuid4().hex,retry_of=retry_of,medium=self.medium,
                   policy_type=self.policy.policy_type,label_face=self.label_face,
                   rotations_to_read=0,dry_run=self.dry_run,t_pick_s=0,t_scan_s=0,t_place_s=0)
        arm=MEDIA[self.medium]['holding_arm']; offset=0 if arm=='left' else 7
        phase_start=start; phase='t_pick_s'
        try:
            current=motion.observe()['joint_positions']
            indices=[0,1,2,3,4,5,7,8,9,10,11,12]
            if np.max(np.abs(current[indices]-home_action()[indices]))>.12:
                raise ValueError('Both arms must start at home; home explicitly before a cycle')
            if hasattr(self.policy,'warmup'):
                self.policy.warmup({'qpos':current,'images':self.images()})
                # Warmup requests predictions only; no robot command is issued.
                start=clock(); phase_start=start
            self.policy.reset()
            check=HandoffCheck(self.medium,motion.waypoints['poses']['scan_'+arm],self.config)
            limit=int(np.ceil(self.config['policy_timeout_s']*1000/CONTROL['control_period_ms']))
            for _ in range(limit):
                tick_start=clock()
                qpos=motion.observe()['joint_positions']
                if check.update(qpos,clock()): break
                if clock()-start>=self.config['policy_timeout_s']:
                    raise TimeoutError('Pick-to-scan handoff timeout')
                observation={'qpos':qpos,'images':self.images()}
                inference_start=time.monotonic()
                action=self.policy.step(observation)
                if time.monotonic()-inference_start>self.config.get('policy_step_timeout_s',1.0):
                    raise TimeoutError('Policy step exceeded inference timeout')
                motion.command(action,start=tick_start)
            else: raise TimeoutError('Pick-to-scan handoff timeout')
            row['t_pick_s']=clock()-phase_start
            phase='t_scan_s'; phase_start=clock()
            self.scanner.arm(row['cycle_id'])
            rotations=0
            def poll():
                event=self.scanner.poll(rotations)
                if event is None: return None
                if event.get('cycle_id')!=row['cycle_id']: return None
                if destination_mapping().get(event.get('barcode'))!=event.get('bin_index'): return None
                return event
            event=motion.hold(self.config['scan_dwell_s'],poll)
            while event is None and rotations<MEDIA[self.medium]['max_rotations']:
                attempted_rotation=rotations+1
                row['rotations_to_read']=attempted_rotation
                target=motion.last_action.copy()
                direction=motion.waypoints.get('rotation_direction',{}).get(arm,1)
                if direction not in (-1,1): raise ValueError('Rotation direction must be -1 or 1')
                target[offset+5]+=direction*np.deg2rad(MEDIA[self.medium]['rotation_deg'])
                event=motion.move(target,poll)
                rotations=attempted_rotation
                if event is None: event=motion.hold(self.config['scan_dwell_s'],poll)
            row['rotations_to_read']=rotations
            row['t_scan_s']=clock()-phase_start
            phase='t_place_s'; phase_start=clock()
            if event is None:
                # Never choose a destination after exhausting the scanner sweep.
                motion.route('drop_receiving_'+arm,arm)
                target=motion.last_action.copy(); target[offset+6]=0
                motion.command(target); motion.hold(.5)
                motion.home(arm)
                target=motion.last_action.copy(); target[[6,13]]=1; motion.command(target)
                row['outcome']='no_read'
                row['t_place_s']=clock()-phase_start
                row['t_total_s']=clock()-start
                row['no_read_cause']=self.cause()
            else:
                row['token'],row['bin']=event['barcode'],event['bin_index']
                motion.route('drop_bin{}_{}'.format(event['bin_index'],arm),arm)
                target=motion.last_action.copy(); target[offset+6]=0
                motion.command(target); motion.hold(.5)
                motion.home(arm)
                target=motion.last_action.copy(); target[[6,13]]=1; motion.command(target)
                row['t_place_s']=clock()-phase_start
                row['t_total_s']=clock()-start
                row['outcome']=self.outcome()
                if row['outcome'] not in OUTCOMES.values(): raise ValueError('Invalid physical outcome')
        except (Exception,KeyboardInterrupt) as error:
            # No release, recovery trajectory or homing follows a fault.
            row['outcome']='fault'; row['fault_detail']=str(error) or 'Operator interrupted'
            try: motion.halt()
            except Exception as stop_error: row['fault_detail']+='; '+str(stop_error)
            row[phase]=clock()-phase_start; row['t_total_s']=clock()-start
        row['control_overruns']=motion.overruns-before_overruns
        append_cycle(self.csv_path,row)
        return row


def run_attempts(cycle,retry=lambda row:False):
    rows=[]; original=''
    for attempt in range(2):
        row=cycle.run(retry_of=original); rows.append(row)
        if row['outcome'] in ('success','fault'): break
        if attempt==1:
            print('Retry failed. Stop and wait for the operator.',flush=True)
            break
        if not retry(row): break
        original=row['cycle_id']
    return rows


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--medium',required=True,choices=sorted(MEDIA))
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run',action='store_true'); mode.add_argument('--live',action='store_true')
    parser.add_argument('--backend',choices=('vendor','robomimic'),default='vendor')
    parser.add_argument('--checkpoint',type=Path)
    parser.add_argument('--model-name',default='policy_best.ckpt')
    parser.add_argument('--waypoints',type=Path,default=Path(SUPERVISOR['waypoint_file']))
    parser.add_argument('--csv',type=Path,default=Path(SUPERVISOR['cycle_csv']))
    parser.add_argument('--label-face',default='')
    parser.add_argument('--fake-token',default=None)
    parser.add_argument('--fake-read-after',type=int,default=0)
    parser.add_argument('--fake-outcome',choices=tuple(OUTCOMES.values()),default='success')
    parser.add_argument('--retry-once',action='store_true',help='Simulate one retry; live retries always require operator input')
    args=parser.parse_args(argv)
    if args.fake_read_after < 0:
        parser.error('--fake-read-after must be nonnegative')
    if args.label_face:
        from barcode_scanning.dataset_metadata import validate_medium_face
        validate_medium_face(args.medium,args.label_face)
    if args.live and (args.fake_token is not None or args.retry_once):
        parser.error('Fake scanner and automatic retry options are restricted to --dry-run')
    if args.live and args.checkpoint is None:
        parser.error('--checkpoint is required for live execution')
    runtime=None; scanner=None
    try:
        points=(load_waypoints(args.waypoints,live=args.live) if args.waypoints.exists()
                else simulation_waypoints() if args.dry_run else load_waypoints(args.waypoints,live=True))
        arm=MEDIA[args.medium]['holding_arm']
        if args.dry_run and args.checkpoint is None:
            policy=SimulatedPolicy(args.medium,points['poses']['scan_'+arm])
        elif args.backend=='vendor':
            if args.checkpoint is None: parser.error('--checkpoint is required for live execution')
            policy=VendorPolicy(args.medium,args.checkpoint,args.model_name)
        else:
            from experiments.robomimic_runner import RobomimicPolicy
            policy=RobomimicPolicy(args.medium,args.checkpoint)
        if args.live and getattr(policy, 'smoke_checkpoint', False):
            parser.error('Smoke checkpoints are restricted to software-only checks')
        if args.dry_run:
            clock=VirtualClock(); env=SimulatedEnv()
            motion=MotionLoop(env,points,clock=clock,sleep=clock.sleep)
            scanner=FakeScanner(args.fake_token,args.fake_read_after)
            images=lambda:{key:np.zeros((480,640,3),dtype=np.uint8) for key in ('top','left_wrist','right_wrist')}
        else:
            from experiments.hardware_runtime import LiveRuntime
            runtime=LiveRuntime(); scanner=Scanner()
            motion=MotionLoop(runtime.env,points,stop=runtime.stop,health=runtime.health)
            images=runtime.images
        cycle=Cycle(motion,policy,scanner,args.medium,args.csv,images,args.dry_run,
                    outcome=(lambda:args.fake_outcome) if args.dry_run else operator_outcome,
                    cause=(lambda:'unknown') if args.dry_run else operator_cause,label_face=args.label_face)
        def retry(row):
            if args.dry_run: return args.retry_once
            return read_key('Place the same parcel at receiving. [r] retry once, any other key stops')=='r'
        rows=run_attempts(cycle,retry)
        for row in rows: print(json.dumps(row,sort_keys=True))
        if not args.dry_run and rows[-1]['outcome']!='success':
            read_key('Cycle stopped. Inspect the parcel and robot before recovery. Press any key to exit; homing is manual.')
        return 0 if rows[-1]['outcome']=='success' else 2
    finally:
        if scanner is not None: scanner.close()
        if runtime is not None: runtime.close()


if __name__ == '__main__': sys.exit(main())
