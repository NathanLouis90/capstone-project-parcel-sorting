import json
import shutil
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


@pytest.mark.parametrize('faces', [('bottom',), ('top', 'bottom')])
def test_explicit_project_selection_excludes_other_datasets(tmp_path, faces):
    from scripts import convert_to_robomimic as converter

    legacy = project(tmp_path)
    for i in range(4):
        face = 'top' if i % 2 else 'bottom'
        target = tmp_path / ('poly_mailer_' + face) / 'train_data'
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(legacy / 'train_data' / 'episode_init_{}.hdf5'.format(i)), str(target))
    output, split = tmp_path / 'selected.hdf5', tmp_path / 'selected.split.json'
    selected = ['poly_mailer_' + face for face in faces]
    converter.main(['--recipe', 'poly_mailer',
        '--projects', *[str(tmp_path / name) for name in selected],
        '--output', str(output), '--split-file', str(split)])
    sources = json.loads(split.read_text())['sources']
    assert len(sources) == 2 * len(faces)
    assert {entry['id'].split('/')[0] for entry in sources} == set(selected)
    with h5py.File(str(output)) as source:
        assert len(source['data']) == 2 * len(faces)
        assert {demo.attrs['label_face'] for demo in source['data'].values()} == set(faces)


def test_default_projects_skip_missing_and_other_media(tmp_path, monkeypatch):
    from scripts import convert_to_robomimic as converter

    project(tmp_path)
    (tmp_path / 'carton' / 'train_data').mkdir(parents=True)
    (tmp_path / 'carton' / 'train_data' / 'episode_init_0.hdf5').write_bytes(b'not a mailer dataset')
    monkeypatch.setitem(converter.PREPARE_ACT_DATASETS, 'root_dir', str(tmp_path))
    output, split = tmp_path / 'default.hdf5', tmp_path / 'default.split.json'
    converter.main(['--recipe', 'poly_mailer',
        '--output', str(output), '--split-file', str(split)])
    sources = json.loads(split.read_text())['sources']
    assert len(sources) == 4
    assert {entry['id'].split('/')[0] for entry in sources} == {'poly_mailer'}


@pytest.mark.parametrize('schema', [None, 2, 4])
def test_unsupported_metadata_refused_before_creating_outputs(tmp_path, schema):
    p = project(tmp_path)
    with h5py.File(str(p / 'train_data/episode_init_0.hdf5'), 'r+') as source:
        metadata = json.loads(source.attrs['episode_metadata_json'])
        metadata['schema_version'] = schema
        source.attrs['episode_metadata_json'] = json.dumps(metadata)
    output, split = tmp_path / 'data.hdf5', tmp_path / 'split.json'
    with pytest.raises(ValueError, match='schema 3'):
        convert([p], 'poly_mailer', output, split)
    assert not output.exists() and not split.exists()
