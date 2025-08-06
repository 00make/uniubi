# code by LinCC111 Boxjod 2025.1.13 Box2AI-Robotics copyright 盒桥智能 版权所有
# Modified for Piper SDK control
import os
import numpy as np
import time
from piper_sdk import C_PiperInterface_V2
import socket
import json
import threading
np.set_printoptions(linewidth=200)

# Initialize Piper robot
print("正在连接Piper机械臂...")
piper = C_PiperInterface_V2("can0")
piper.ConnectPort()
while not piper.EnablePiper():
    print("等待机械臂使能...")
    time.sleep(0.01)
print("Piper机械臂连接成功！")

# Initialize target position [X, Y, Z, RX, RY, RZ, Gripper]
# 初始位置设置为安全位置
target_position = [150.0, 0.0, 200.0, 0.0, 90.0, 0.0, 0.0]

# UDP socket setup
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.bind(('127.0.0.1', 12345))
udp_socket.settimeout(0.001)
print("UDP服务器启动，监听端口12345...")

# Controller tracking variables
last_controller_position = None
MOVEMENT_SCALE = 1.0  # Scale factor for position movement (mm)
ROTATION_SCALE = 1.0  # Scale factor for rotation (degrees)

# Axis mapping coefficients
AXIS_MAPPING = {
    'X': -1,  # 控制器左右对应机械臂前后（取反）
    'Y': -1,  # 控制器上下对应机械臂左右（取反）
    'Z': 1    # 控制器前后对应机械臂上下（保持）
}

# 设置初始位置
print("设置机械臂初始位置...")
piper.MotionCtrl_2(0x01, 0x00, 50, 0x00)  # 设置较慢的速度进行初始化
piper.EndPoseCtrl(int(target_position[0]), int(target_position[1]), int(target_position[2]), 
                  int(target_position[3]), int(target_position[4]), int(target_position[5]))
piper.GripperCtrl(0, 1000, 0x01, 0)  # 夹爪打开
time.sleep(2)  # 等待到达初始位置

print("开始WebXR控制循环...")

# 主控制循环
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
                    # 坐标映射 - 更新位置增量
                    delta_x = (current_position[0] - last_controller_position[0]) * MOVEMENT_SCALE * AXIS_MAPPING['X']
                    delta_y = (current_position[2] - last_controller_position[2]) * MOVEMENT_SCALE * AXIS_MAPPING['Y']
                    delta_z = (current_position[1] - last_controller_position[1]) * MOVEMENT_SCALE * AXIS_MAPPING['Z']

                    # 更新目标位置 (mm)
                    target_position[0] = target_position[0] + delta_x
                    target_position[1] = target_position[1] + delta_y
                    target_position[2] = target_position[2] + delta_z

                last_controller_position = current_position

                # 更新姿态 (degrees)
                rotation = [
                    controller_data['rotation']['x'],
                    controller_data['rotation']['y'],
                    controller_data['rotation']['z']
                ]
                target_position[3] = rotation[1] * ROTATION_SCALE * AXIS_MAPPING['Y']
                target_position[4] = rotation[0] * ROTATION_SCALE * AXIS_MAPPING['X']

                # 使用axes数据控制Z轴旋转和buttons控制夹爪
                if 'axes' in controller_data and 'buttons' in controller_data:
                    axes = controller_data['axes']
                    buttons = controller_data['buttons']

                    if len(axes) > 2:
                        # Z轴旋转控制
                        rz_speed = -axes[2] * ROTATION_SCALE * 0.1
                        target_position[5] = target_position[5] + rz_speed

                    # 夹爪控制
                    if len(buttons) > 0:
                        if buttons[0]:
                            target_position[6] = 50  # 打开
                        else:
                            target_position[6] = 0     # 完全闭合

        except socket.timeout:
            pass  # 没有数据时继续循环
        except json.JSONDecodeError:
            print("JSON解析错误，跳过此数据包")
            continue
        except Exception as e:
            print(f"接收数据时出错: {e}")
            continue

        # 控制Piper机械臂
        factor = 1000
        X = round(target_position[0] * factor)
        Y = round(target_position[1] * factor)
        Z = round(target_position[2] * factor)
        RX = round(target_position[3] * factor)
        RY = round(target_position[4] * factor)
        RZ = round(target_position[5] * factor)
        gripper = round(target_position[6] * factor)

        # 每隔一定时间打印当前目标位置
        if int(time.time() * 10) % 10 == 0:  # 每秒打印一次
            print(f"Target: X={X}, Y={Y}, Z={Z}, RX={RX}, RY={RY}, RZ={RZ}, Gripper={gripper}")
        
        try:
            # 发送运动控制命令
            piper.MotionCtrl_2(0x01, 0x00, 100, 0x00)  # 设置运动模式和速度
            piper.EndPoseCtrl(X, Y, Z, RX, RY, RZ)     # 末端位置控制
            piper.GripperCtrl(abs(gripper), 1000, 0x01, 0)  # 夹爪控制
        except Exception as e:
            print(f"控制机械臂时出错: {e}")
        
        time.sleep(0.01)  # 控制循环频率

except KeyboardInterrupt:
    print("\n用户中断程序...")
except Exception as e:
    print(f"程序运行出错: {e}")
finally:
    print("正在关闭连接...")
    udp_socket.close()
    try:
        piper.DisablePiper()  # 断开Piper连接
        print("Piper机械臂已安全断开")
    except:
        print("断开Piper连接时出错，请手动检查")
