# code by LinCC111 Boxjod 2025.1.13 Box2AI-Robotics copyright 盒桥智能 版权所有
import os
import numpy as np
import time
from lerobot_kinematics import lerobot_IK, lerobot_FK, get_robot, feetech_arm
import socket
import json
import threading
np.set_printoptions(linewidth=200)
# Define joint names
JOINT_NAMES = ["Rotation", "Pitch", "Elbow",
               "Wrist_Pitch", "Wrist_Roll", "Jaw"]
robot = get_robot('so100')
# Define joint control increment (in radians)
JOINT_INCREMENT = 0.005
POSITION_INSERMENT = 0.0008
# Define joint limits
control_qlimit = [[-2.1, -3.1, -0.0, -1.375,  -1.57, -0.1],
                  [2.1,  0.0,  3.1,  1.475,   3.1,  1.5]]
control_glimit = [[0.125, -0.4,  0.046, -3.1, -0.75, -1.5],
                  [0.340,  0.4,  0.23, 2.0,  1.57,  1.5]]
# Initialize target joint positions
init_qpos = np.array([0.0, -3.14, 3.14, 0.0, -1.57, 0.157])
target_qpos = init_qpos.copy()
init_gpos = lerobot_FK(init_qpos[1:5], robot=robot)
target_gpos = init_gpos.copy()
# UDP socket setup
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.bind(('127.0.0.1', 12345))
udp_socket.settimeout(0.001)
# Controller tracking variables
last_controller_position = None
MOVEMENT_SCALE = 0.2
BASEROTAION_SCALE = 2
# Axis mapping coefficients
AXIS_MAPPING = {
    'X': -1,  # 控制器左右对应机械臂前后（取反）
    'Y': -1,  # 控制器上下对应机械臂左右（取反）
    'Z': 1    # 控制器前后对应机械臂上下（保持）
}
# Initialize tracking variables
target_gpos_last = init_gpos.copy()
target_qpos_last = init_qpos.copy()
base_rotation = init_qpos[0]
# Connect to robotic arm
follower_arm = feetech_arm(driver_port="/dev/tty.usbmodem5A460846011",
                           calibration_file="webxr/so100/main_follower.json")
# 修改 UDP 数据处理部分
try:
    start = time.time()
    while time.time() - start < 1000:
        step_start = time.time()
        try:
            # 接收UDP数据
            data, addr = udp_socket.recvfrom(1024)
            message = json.loads(data.decode())

            # 只处理controller2的数据用于机械臂控制
            if message['controller_id'] == 'controller2':
                controller_data = message['data']
                current_position = [
                    controller_data['position']['x'],
                    controller_data['position']['y'],
                    controller_data['position']['z']
                ]

                if last_controller_position is not None:
                    # 坐标映射
                    delta_x = (
                        current_position[0] - last_controller_position[0]) * MOVEMENT_SCALE * AXIS_MAPPING['X']
                    delta_y = (
                        current_position[2] - last_controller_position[2]) * MOVEMENT_SCALE * AXIS_MAPPING['Y']
                    delta_z = (
                        current_position[1] - last_controller_position[1]) * MOVEMENT_SCALE * AXIS_MAPPING['Z']

                    # 更新基座旋转 - 使用位置变化
                    delta_r = (
                        current_position[0] - last_controller_position[0]) * BASEROTAION_SCALE * AXIS_MAPPING['X']
                    base_rotation = np.clip(base_rotation + delta_r,
                                            control_qlimit[0][0],
                                            control_qlimit[1][0])

                    # 更新目标位置
                    target_gpos[1] = np.clip(target_gpos[1] + delta_x,
                                             control_glimit[0][1],
                                             control_glimit[1][1])
                    target_gpos[0] = np.clip(target_gpos[0] + delta_y,
                                             control_glimit[0][0],
                                             control_glimit[1][0])
                    target_gpos[2] = np.clip(target_gpos[2] + delta_z,
                                             control_glimit[0][2],
                                             control_glimit[1][2])
                last_controller_position = current_position

                # 更新姿态
                rotation = [
                    controller_data['rotation']['x'],
                    controller_data['rotation']['y'],
                    controller_data['rotation']['z']
                ]
                target_gpos[3] = np.clip(rotation[1] * AXIS_MAPPING['Y'],
                                         control_glimit[0][3],
                                         control_glimit[1][3])
                target_gpos[4] = np.clip(rotation[0] * AXIS_MAPPING['X'],
                                         control_glimit[0][4],
                                         control_glimit[1][4])

                # 使用axes数据控制基座旋转（叠加效果）和buttons控制夹爪
                if 'axes' in controller_data and 'buttons' in controller_data:
                    axes = controller_data['axes']
                    buttons = controller_data['buttons']

                    if len(axes) > 2:
                        # 基座旋转控制 - 使用axes（叠加到位置控制上）
                        base_rotation_speed = -axes[2] * 0.1
                        base_rotation = np.clip(base_rotation + base_rotation_speed,
                                                control_qlimit[0][0],
                                                control_qlimit[1][0])

                    # 夹爪控制
                    if len(buttons) > 0:
                        if buttons[0]:
                            target_qpos[5] = -0.1  # 完全闭合
                        else:
                            target_qpos[5] = 0.7  # 打开
        except socket.timeout:
            pass
        # Inverse Kinematics calculation
        qpos_inv, IK_success = lerobot_IK(
            target_qpos_last[1:5], target_gpos, robot=robot)
        if IK_success:
            target_qpos = np.concatenate(
                ([base_rotation], qpos_inv[:4], [target_qpos[5]]))
            print("target_qpos:", [f"{x:.3f}" for x in target_qpos])

            # Control real robot
            follower_arm.action(target_qpos)
            target_gpos_last = target_gpos.copy()
            target_qpos_last = target_qpos.copy()
        else:
            target_gpos = target_gpos_last.copy()
        time.sleep(0.01)  # 控制循环频率
except KeyboardInterrupt:
    print("User interrupted the program.")
finally:
    udp_socket.close()
    follower_arm.disconnect()
