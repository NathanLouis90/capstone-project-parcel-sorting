from config.settings import GET_OFFSETS

import numpy as np
from parcel_sorting.hardware.dynamixel.driver import DynamixelDriver
from parcel_sorting.hardware.manipulate_utils import load_ini_data_hands
from parcel_sorting.utils import scan_port


def get_config(which_hand, which_hand_config):
    gripper_ids = GET_OFFSETS["gripper_ids"]
    driver =DynamixelDriver(ids=which_hand_config.joint_ids+gripper_ids[which_hand],
                            append_id=which_hand_config.append_id,
                            port=which_hand_config.port, baudrate=hands_dict[which_hand].baud_rate)
    # driver.set_torque_mode(False)
    print("--------------------", which_hand, "-------------------")
    pos_joint = driver.get_joints()
    curr_joints = pos_joint[:6]
    print("curr_joints: ", curr_joints)
    print("robot_joints: ", which_hand_config.start_joints)

    dev_pos = [float("%.2f" % (curr_joints[i]-which_hand_config.start_joints[i]*which_hand_config.joint_signs[i]))
               for i in range(6)]
    print("dev(write): ", dev_pos)
    print("dev(*pi/2): ", [(i / np.pi) * 2 for i in curr_joints])
    print("dev(angle): ", [np.rad2deg(i) for i in curr_joints])
    print("----------------------------------------------")
    gripper_on = int(np.rad2deg(pos_joint[-1]) - GET_OFFSETS["gripper_open_offset_deg"])
    gripper_close = int(np.rad2deg(pos_joint[-1]) + GET_OFFSETS["gripper_close_offset_deg"])
    print(
        "gripper open (degrees)       ",
        gripper_on,
    )
    print(
        "gripper close (degrees)      ",
        gripper_close,
    )
    return dev_pos, [gripper_ids[which_hand][0], gripper_close, gripper_on]


if __name__ == "__main__":
    # left hand nova2
    scan_port()
    ini_file_path = GET_OFFSETS["hardware_settings_path"]
    ini_file, hands_dict = load_ini_data_hands()
    for _hand in hands_dict.keys():
        offsets, pos_gripper = get_config(_hand, hands_dict[_hand])
        ini_file.set(section=_hand, option="joint_offsets",
                     value=str(offsets).replace("[", '').replace("]", ''))
        ini_file.set(section=_hand, option="gripper_config",
                     value=str(pos_gripper).replace("[", '').replace("]", ''))
        with open(ini_file_path, "w+") as _file:
            ini_file.write(_file)
        _file.close()

