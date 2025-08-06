# code by LinCC111 Boxjod 2025.1.13 Box2AI-Robotics copyright 盒桥智能 版权所有
# Modified for Piper SDK control
import time
from piper_sdk import C_PiperInterface_V2
import socket
import json

# Constants
MOVEMENT_SCALE = 1.0
ROTATION_SCALE = 1.0
AXIS_MAPPING = {'X': -1, 'Y': -1, 'Z': 1}
UDP_PORT = 12345
FACTOR = 1000

def init_piper():
    """初始化Piper机械臂"""
    print("正在连接Piper机械臂...")
    piper = C_PiperInterface_V2("can0")
    piper.ConnectPort()
    while not piper.EnablePiper():
        print("等待机械臂使能...")
        time.sleep(0.01)
    print("Piper机械臂连接成功！")
    return piper

def setup_udp():
    """设置UDP套接字"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', UDP_PORT))
    sock.settimeout(0.001)
    print(f"UDP服务器启动，监听端口{UDP_PORT}...")
    return sock

def set_initial_position(piper, target_pos):
    """设置初始位置"""
    print("设置机械臂初始位置...")
    piper.MotionCtrl_2(0x01, 0x00, 50, 0x00)
    piper.EndPoseCtrl(*[int(x) for x in target_pos[:6]])
    piper.GripperCtrl(0, 1000, 0x01, 0)
    time.sleep(2)

def update_position(target_pos, current_pos, last_pos):
    """更新目标位置"""
    if last_pos is None:
        return current_pos
    
    # 计算位置增量
    deltas = [
        (current_pos[0] - last_pos[0]) * MOVEMENT_SCALE * AXIS_MAPPING['X'],
        (current_pos[2] - last_pos[2]) * MOVEMENT_SCALE * AXIS_MAPPING['Y'],
        (current_pos[1] - last_pos[1]) * MOVEMENT_SCALE * AXIS_MAPPING['Z']
    ]
    
    # 更新目标位置
    for i, delta in enumerate(deltas):
        target_pos[i] += delta
    
    return current_pos

def update_rotation(target_pos, rotation):
    """更新姿态"""
    target_pos[3] = rotation[1] * ROTATION_SCALE * AXIS_MAPPING['Y']
    target_pos[4] = rotation[0] * ROTATION_SCALE * AXIS_MAPPING['X']

def control_z_rotation(target_pos, controller_data):
    """控制Z轴旋转"""
    if 'axes' in controller_data and len(controller_data['axes']) > 2:
        rz_speed = -controller_data['axes'][2] * ROTATION_SCALE * 0.1
        target_pos[5] += rz_speed

def control_gripper(target_pos, controller_data):
    """控制夹爪"""
    if 'buttons' in controller_data and len(controller_data['buttons']) > 0:
        target_pos[6] = 50 if controller_data['buttons'][0] else 0

def send_commands(piper, target_pos):
    """发送控制命令到机械臂"""
    # 转换为整数值
    coords = [round(pos * FACTOR) for pos in target_pos]
    
    piper.MotionCtrl_2(0x01, 0x00, 100, 0x00)
    piper.EndPoseCtrl(*coords[:6])
    piper.GripperCtrl(abs(coords[6]), 1000, 0x01, 0)

# Initialize components
piper = init_piper()
udp_socket = setup_udp()
target_position = [150.0, 0.0, 200.0, 0.0, 90.0, 0.0, 0.0]
last_controller_position = None

set_initial_position(piper, target_position)

print("开始WebXR控制循环...")

# 主控制循环
try:
    start_time = time.time()
    last_print_time = 0
    
    while time.time() - start_time < 1000:
        try:
            # 接收并解析UDP数据
            data, _ = udp_socket.recvfrom(1024)
            message = json.loads(data.decode())
            
            # 只处理controller2的数据
            if message.get('controller_id') != 'controller2':
                continue
                
            controller_data = message['data']
            
            # 提取当前位置和姿态
            pos_data = controller_data['position']
            current_position = [pos_data['x'], pos_data['y'], pos_data['z']]
            
            rot_data = controller_data['rotation']
            rotation = [rot_data['x'], rot_data['y'], rot_data['z']]
            
            # 更新位置和姿态
            last_controller_position = update_position(target_position, current_position, last_controller_position)
            update_rotation(target_position, rotation)
            control_z_rotation(target_position, controller_data)
            control_gripper(target_position, controller_data)
            
        except (socket.timeout, json.JSONDecodeError, KeyError):
            pass  # 忽略超时和解析错误，继续循环
        except Exception as e:
            print(f"数据处理错误: {e}")
            continue

        # 发送控制命令
        try:
            send_commands(piper, target_position)
        except Exception as e:
            print(f"控制机械臂时出错: {e}")
        
        # 定期打印状态
        current_time = time.time()
        if current_time - last_print_time >= 1.0:  # 每秒打印一次
            coords = [round(pos * FACTOR) for pos in target_position]
            print(f"Target: X={coords[0]}, Y={coords[1]}, Z={coords[2]}, "
                  f"RX={coords[3]}, RY={coords[4]}, RZ={coords[5]}, Gripper={coords[6]}")
            last_print_time = current_time
        
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n用户中断程序...")
except Exception as e:
    print(f"程序运行出错: {e}")
finally:
    print("正在关闭连接...")
    udp_socket.close()
    try:
        piper.DisablePiper()
        print("Piper机械臂已安全断开")
    except Exception as e:
        print(f"断开Piper连接时出错: {e}")
