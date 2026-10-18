"""Hardware-free Nova jaw-tip forward kinematics, in meters."""
import numpy as np

def dh_transformation_matrix(theta, d, a, alpha):
    """
    Create the DH transformation matrix
    """
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)
    cos_alpha = np.cos(alpha)
    sin_alpha = np.sin(alpha)
    return np.array([
        [cos_theta, -sin_theta * cos_alpha, sin_theta * sin_alpha, a * cos_theta],
        [sin_theta, cos_theta * cos_alpha, -cos_theta * sin_alpha, a * sin_theta],
        [0, sin_alpha, cos_alpha, d],
        [0, 0, 0, 1]
    ])

def claw_width(coef):
    """
    Calculate the claw width
    """
    claw_servo = 2.3818 - coef * 1.5401
    cos_claw_servo = np.cos(claw_servo)
    claw_wid = 0.03 * cos_claw_servo + 0.5 * np.sqrt(0.0036 * cos_claw_servo ** 2 + 0.0028)
    return claw_wid

def forward_kinematics(q0, q1, q2, q3, q4, q5, y, r_type, return_transform=False):
    """
    Compute the forward kinematics
    """
    if r_type == "Nova 2":
        dh_params = [
            (q0, 0.2234, 0, np.pi / 2),
            (q1 - np.pi / 2, 0, -0.280, 0),
            (q2, 0, -0.225, 0),
            (q3 - np.pi / 2, 0.1175, 0, np.pi / 2),
            (q4, 0.120, 0, -np.pi / 2),
            (q5, 0.088, 0, 0)
        ]
    elif r_type == "Nova 5":
        dh_params = [
            (q0, 0.240, 0, np.pi / 2),
            (q1 - np.pi / 2, 0, -0.400, 0),
            (q2, 0, -0.330, 0),
            (q3 - np.pi / 2, 0.135, 0, np.pi / 2),
            (q4, 0.120, 0, -np.pi / 2),
            (q5, 0.088, 0, 0)
        ]

    else:
        raise ValueError("Unsupported robot type: {}".format(r_type))

    t = np.eye(4)
    for params in dh_params:
        t = np.dot(t, dh_transformation_matrix(*params))
    t_tool = np.eye(4)
    t_tool[:3, 3] = np.array([0, y, 0.2])
    t_final = np.dot(t, t_tool)
    if return_transform:
        return t_final
    pos = t_final[:3, 3]
    return pos
