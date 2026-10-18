import json
import cv2
import h5py
import numpy as np
import pytest
from scripts.convert_to_robomimic import convert
from scripts.scripts_config import ROBOMIMIC


def project(tmp_path):
    project=tmp_path/'poly_mailer'; directory=project/'train_data'; directory.mkdir(parents=True)
    for i in range(4):
        with h5py.File(str(directory/('episode_init_{}.hdf5'.format(i))),'w') as f:
            m=dict(schema_version=3, medium='poly_mailer',label_face='top' if i%2 else 'bottom',
                   cycle_id=str(i),episode_id=str(i),review_status='accepted')
            f.attrs['episode_metadata_json']=json.dumps(m)
            for key in ('medium','label_face','cycle_id'): f.attrs[key]=m[key]
            f.attrs['compress']=True
            f['observations/qpos']=np.zeros((20,14)); f['action']=np.zeros((20,14))
            _, image=cv2.imencode('.jpg', np.full((32,32,3),[10,40,200],dtype=np.uint8))
            for camera in ROBOMIMIC['cameras']:
                f['observations/images/'+camera]=np.tile(image.ravel(),(20,1))
    return project


def test_per_medium_conversion_and_frozen_split(tmp_path):
    p=project(tmp_path); out=tmp_path/'data.hdf5'; split=tmp_path/'split.json'
    result=convert([p],'poly_mailer',out,split)
    assert set(result['train']).isdisjoint(result['valid'])
    with h5py.File(str(out)) as f:
        demo=f['data/demo_0']
        assert set(demo['obs'])=={'qpos','top','left_wrist','right_wrist'}
        assert demo['obs/top'][0,0,0,0]>demo['obs/top'][0,0,0,2]
    with pytest.raises(FileExistsError): convert([p],'poly_mailer',out,split)


def test_configs_have_only_joint_and_image_observations(tmp_path):
    from robomimic.scripts.config_gen.parcel_sorting_gen import generate_configs
    p=project(tmp_path); out=tmp_path/'data.hdf5'; split=tmp_path/'split.json'
    convert([p],'poly_mailer',out,split)
    paths=generate_configs(out,split,tmp_path/'configs',smoke=True,cpu=True)
    assert len(paths)==2
    for path in paths:
        c=json.loads(path.read_text())
        assert c['observation']['modalities']['obs']['low_dim']==['qpos']
        assert c['train']['hdf5_filter_key']=='train'
        assert c['train']['hdf5_validation_filter_key']=='valid'


def test_changed_source_refuses_frozen_split(tmp_path):
    p=project(tmp_path); split=tmp_path/'split.json'
    convert([p],'poly_mailer',tmp_path/'first.hdf5',split)
    with h5py.File(str(p/'train_data/episode_init_0.hdf5'),'r+') as f: f['action'][0,0]=.1
    with pytest.raises(ValueError,match='sources changed'):
        convert([p],'poly_mailer',tmp_path/'second.hdf5',split)
