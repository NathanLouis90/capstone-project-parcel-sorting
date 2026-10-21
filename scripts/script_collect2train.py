if __package__:
    from .scripts_config import SCRIPT_COLLECT2TRAIN
else:
    from scripts_config import SCRIPT_COLLECT2TRAIN

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from barcode_scanning.dataset_metadata import read_episode_metadata, write_hdf5_metadata
from scripts.dataset_integrity import require_fresh, require_rollout_opt_in
from scripts.scripts_config import PREPARE_ACT_DATASETS

import time
import h5py
import os
import glob
import cv2
import pickle
import numpy as np

if __package__:
    from .function_util import save_videos, mk_dir
else:
    from function_util import save_videos, mk_dir
import click
#
# """
# For each timestep:
# observations
# - images
#     - each_cam_name     (480, 640, 3) 'uint8'
# - qpos                  (14,)         'float64'
# - qvel                  (14,)         'float64'
#
# action                  (14,)         'float64'
# """
#



def deal_data(pos_list, top_list, left_list, right_list):
    identifiers = [{Path(path).stem for path in paths}
                   for paths in (pos_list, top_list, left_list, right_list)]
    if not identifiers[0] or any(ids != identifiers[0] for ids in identifiers[1:]):
        raise ValueError('Missing or mismatched observation/camera frames; raw files were preserved')
    return pos_list, top_list, left_list, right_list


def load_data(one_dataset_dir):
    camera_names = ['top', 'left_wrist', 'right_wrist']
    print(camera_names)

    data_pose_list = glob.glob(one_dataset_dir + 'observation/*.pkl')
    images_top_list = glob.glob(one_dataset_dir + 'topImg/*.jpg')
    images_left_list = glob.glob(one_dataset_dir + 'leftImg/*.jpg')
    images_right_list = glob.glob(one_dataset_dir + 'rightImg/*.jpg')
    data_pose_list.sort(key=lambda x: int(x.split("/")[-1].split(".")[0]))
    images_top_list.sort(key=lambda x: int(x.split("/")[-1].split(".")[0]))
    images_left_list.sort(key=lambda x: int(x.split("/")[-1].split(".")[0]))
    images_right_list.sort(key=lambda x: int(x.split("/")[-1].split(".")[0]))
    # print(images_right_list)

    data_pose_list, images_top_list, images_left_list, images_right_list = (
        deal_data(data_pose_list, images_top_list, images_left_list, images_right_list))

    is_sim = False
    qpos = []
    qvel = []
    action = []
    image_dict = dict()
    image_li = [[], [], []]
    for cam_name in camera_names:
        image_dict[f'{cam_name}'] = []
    for i in range(len(data_pose_list)):
        with open(data_pose_list[i], "rb") as f:
            data_single = pickle.load(f)
            qpos.append(data_single['joint_positions'])
            qvel.append(data_single['joint_velocities'])
            action.append(data_single['control'])
            image_top = cv2.imread(images_top_list[i])
            image_left = cv2.imread(images_left_list[i])
            image_right = cv2.imread(images_right_list[i])
            if any(image is None for image in (image_top, image_left, image_right)):
                raise ValueError('Unreadable camera image at frame ' + str(i))
            # cv2.imshow("0", image_right)
            # cv2.waitKey(1)
            image_li[0].append(image_top)
            image_li[1].append(image_left)
            image_li[2].append(image_right)
    image_dict['top'] = image_li[0]
    image_dict['left_wrist'] = image_li[1]
    image_dict['right_wrist'] = image_li[2]
    return np.array(qpos), np.array(qvel), np.array(action), image_dict, is_sim


@click.command()
@click.option('-r', '--root_dir', required=True, default=SCRIPT_COLLECT2TRAIN["root_dir"], help='')
@click.option('-d', '--dataset_name', required=True, help='Registered recording project')
@click.option('-t', '--date_collect', required=True, help='Episode folder name')
@click.option('-n', '--idx', required=True, default=SCRIPT_COLLECT2TRAIN["episode_index"],  help='')
@click.option('--allow-rollouts', is_flag=True, help='Include rollouts only in explicitly named rollout projects')
def main(root_dir, dataset_name, date_collect, idx, allow_rollouts=False):
    project = Path(root_dir) / dataset_name
    require_fresh(project, allow_building=True)
    if Path(date_collect).name != date_collect or date_collect in ('.', '..'):
        raise ValueError('Use an episode folder name, not a path')
    episode_metadata = read_episode_metadata(project / 'collect_data' / date_collect)
    settings = PREPARE_ACT_DATASETS['projects'].get(dataset_name, {})
    for key in ('medium', 'label_face'):
        if settings.get(key) is not None and episode_metadata[key] != settings[key]:
            raise ValueError('{} mismatch for {}: recorded {!r}, expected {!r}'.format(
                key, project, episode_metadata[key], settings[key]))
    require_rollout_opt_in(episode_metadata, project, allow_rollouts)
    if episode_metadata.get('review_status') != 'accepted':
        raise ValueError('Conversion requires accepted review status')
    dataset_dir = root_dir + "/" + dataset_name + "/collect_data/"
    mk_dir(dataset_dir)
    output_video_dir = root_dir + "/" + dataset_name + "/output_videos/"
    mk_dir(output_video_dir)
    output_train_data = root_dir + "/" + dataset_name + "/train_data/"
    mk_dir(output_train_data)
    dataset_path = os.path.join(output_train_data, f'episode_init_{idx}')
    if os.path.exists(dataset_path + '.hdf5'):
        raise FileExistsError('Refuse to overwrite: ' + dataset_path + '.hdf5')
    MIRROR_STATE_MULTIPLY = np.array(SCRIPT_COLLECT2TRAIN["MIRROR_STATE_MULTIPLY"])


    one_data_dir = dataset_dir+date_collect+"/"
    print(one_data_dir)
    qpos, qvel, action, image_dict, is_sim = load_data(one_data_dir)
    qpos = np.concatenate([qpos[:, :7] * MIRROR_STATE_MULTIPLY, qpos[:, 7:] * MIRROR_STATE_MULTIPLY], axis=1)
    qvel = np.concatenate([qvel[:, :7] * MIRROR_STATE_MULTIPLY, qvel[:, 7:] * MIRROR_STATE_MULTIPLY], axis=1)
    action = np.concatenate([action[:, :7] * MIRROR_STATE_MULTIPLY, action[:, 7:] * MIRROR_STATE_MULTIPLY], axis=1)

    # saving
    data_dict = {
        '/observations/qpos': qpos,
        '/observations/qvel': qvel,
        '/action': action,
    }
    for cam_name in image_dict.keys():
        data_dict[f'/observations/images/{cam_name}'] = image_dict[cam_name]
    max_timesteps = len(qpos)

    COMPRESS = SCRIPT_COLLECT2TRAIN["COMPRESS"]

    if COMPRESS:
        # JPEG compression
        t0 = time.time()
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), SCRIPT_COLLECT2TRAIN["jpeg_quality"]]  # tried as low as 20, seems fine
        compressed_len = []
        for cam_name in image_dict.keys():
            image_list = data_dict[f'/observations/images/{cam_name}']
            compressed_list = []
            compressed_len.append([])
            for image in image_list:
                result, encoded_image = cv2.imencode('.jpg', image,
                                                     encode_param)  # 0.02 sec # cv2.imdecode(encoded_image, 1)
                compressed_list.append(encoded_image)
                compressed_len[-1].append(len(encoded_image))
            data_dict[f'/observations/images/{cam_name}'] = compressed_list
        print(f'compression: {time.time() - t0:.2f}s')

        # pad so it has same length
        t0 = time.time()
        compressed_len = np.array(compressed_len)
        padded_size = compressed_len.max()
        for cam_name in image_dict.keys():
            compressed_image_list = data_dict[f'/observations/images/{cam_name}']
            padded_compressed_image_list = []
            for compressed_image in compressed_image_list:
                padded_compressed_image = np.zeros(padded_size, dtype='uint8')
                image_len = len(compressed_image)
                padded_compressed_image[:image_len] = compressed_image
                padded_compressed_image_list.append(padded_compressed_image)
            data_dict[f'/observations/images/{cam_name}'] = padded_compressed_image_list
        print(f'padding: {time.time() - t0:.2f}s')

    # HDF5
    t0 = time.time()
    with h5py.File(dataset_path + '.hdf5', 'x', rdcc_nbytes=SCRIPT_COLLECT2TRAIN["hdf5_cache_bytes"]) as root:
        root.attrs['sim'] = is_sim
        root.attrs['compress'] = COMPRESS
        root.attrs['jpeg_quality'] = SCRIPT_COLLECT2TRAIN['jpeg_quality']
        root.attrs['mirror_state_multiply'] = MIRROR_STATE_MULTIPLY
        obs = root.create_group('observations')
        write_hdf5_metadata(root, episode_metadata)
        image = obs.create_group('images')
        for cam_name in image_dict.keys():
            if COMPRESS:
                _ = image.create_dataset(cam_name, (max_timesteps, padded_size), dtype='uint8',
                                         chunks=(1, padded_size), )
            else:
                _ = image.create_dataset(cam_name, (max_timesteps, 480, 640, 3), dtype='uint8',
                                         chunks=(1, 480, 640, 3), )
        qpos = obs.create_dataset('qpos', (max_timesteps, 14))
        qvel = obs.create_dataset('qvel', (max_timesteps, 14))
        action = root.create_dataset('action', (max_timesteps, 14))

        for name, array in data_dict.items():
            root[name][...] = array

        if COMPRESS:
            _ = root.create_dataset('compress_len', (len(image_dict.keys()), max_timesteps))
            root['/compress_len'][...] = compressed_len

    print(f'Saving {dataset_path}: {time.time() - t0:.1f} secs\n')

    # if idx in [0, 4, 8, 23, 33]:
    save_videos(image_dict, SCRIPT_COLLECT2TRAIN["video_frame_period_s"], video_path=os.path.join(output_video_dir + date_collect + f'_video.mp4'))


if __name__ == "__main__":
    main()
