# code by LinCC111 Boxjod 2025.1.13 Box2AI-Robotics copyright 盒桥智能 版权所有
# Modified for Piper SDK control
import time
from piper_sdk import C_PiperInterface_V2
import socket
import json

# Constants
MOVEMENT_SCALE = 360
ROTATION_SCALE = 36
AXIS_MAPPING = {'X': -1, 'Y': -1, 'Z': 1}
UDP_PORT = 12345
FACTOR = 1000

CALIBRATION_FRAMES = 10  # 校准帧数
MAX_SINGLE_MOVE = 5000    # 最大单次移动量 (mm/1000)
MAX_SINGLE_ROTATE = 2000  # 最大单次旋转量 (度/1000)

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
    piper.MotionCtrl_1(0x02,0,0)#恢复
    piper.MotionCtrl_2(0, 0, 0, 0x00)#位置速度模式
    piper.MotionCtrl_2(0x01, 0x00, 50, 0x00)
    piper.EndPoseCtrl(*[int(x) for x in target_pos[:6]])
    piper.GripperCtrl(0, 1000, 0x01, 0)
    time.sleep(2)

def update_position(target_pos, current_pos, last_pos, calibration_mode=False):
    """更新目标位置"""
    if last_pos is None:
        return current_pos
    
    # 校准模式下不应用位置变化，只记录
    if calibration_mode:
        return current_pos
    
    # 计算位置增量
    deltas = [
        (current_pos[0] - last_pos[0]) * MOVEMENT_SCALE * AXIS_MAPPING['Y'],
        (current_pos[1] - last_pos[1]) * MOVEMENT_SCALE * AXIS_MAPPING['Z'],
        (current_pos[2] - last_pos[2]) * MOVEMENT_SCALE * AXIS_MAPPING['X']
    ]
    
    # 更新目标位置
    for i, delta in enumerate(deltas):
        target_pos[i] += delta
    
    return current_pos

def update_rotation(target_pos, rotation, last_rotation=None, calibration_mode=False):
    """更新姿态"""
    if last_rotation is None:
        return rotation  # 第一次数据，只记录不应用
    
    # 校准模式下不应用旋转变化，只记录
    if calibration_mode:
        return rotation
    
    # 计算姿态增量（包括Z轴旋转）
    delta_rx = (rotation[0] - last_rotation[0]) * ROTATION_SCALE * AXIS_MAPPING['Y']
    delta_ry = (rotation[1] - last_rotation[1]) * ROTATION_SCALE * AXIS_MAPPING['X']
    delta_rz = (rotation[2] - last_rotation[2]) * ROTATION_SCALE * AXIS_MAPPING['Z']
    
    # 应用增量
    target_pos[3] += delta_rx
    target_pos[4] += delta_ry
    target_pos[5] += delta_rz
    
    return rotation

def control_gripper(target_pos, controller_data):
    """控制夹爪"""
    if 'buttons' in controller_data and len(controller_data['buttons']) > 0:
        target_pos[6] = 0 if controller_data['buttons'][0] else 50

def send_commands(piper, target_pos, last_sent_pos=None):
    """发送控制命令到机械臂"""
    # 如果有上次发送的位置，检查移动量限制
    if last_sent_pos is not None:
        limited_pos = target_pos[:]
        
        # 限制位置移动量 (X, Y, Z)
        for i in range(3):
            delta = target_pos[i] - last_sent_pos[i]
            if abs(delta) > MAX_SINGLE_MOVE:
                limited_pos[i] = last_sent_pos[i] + (MAX_SINGLE_MOVE if delta > 0 else -MAX_SINGLE_MOVE)
        
        # 限制旋转移动量 (RX, RY, RZ)
        for i in range(3, 6):
            delta = target_pos[i] - last_sent_pos[i]
            if abs(delta) > MAX_SINGLE_ROTATE:
                limited_pos[i] = last_sent_pos[i] + (MAX_SINGLE_ROTATE if delta > 0 else -MAX_SINGLE_ROTATE)
        
        # 使用限制后的位置
        target_pos = limited_pos
    
    # 转换为整数值
    coords = [round(pos * FACTOR) for pos in target_pos]
    
    piper.MotionCtrl_2(0x01, 0x00, 100, 0x00)
    piper.EndPoseCtrl(*coords[:6])
    piper.GripperCtrl(abs(coords[6]), 1000, 0x01, 0)
    
    # 返回实际发送的位置用于下次比较
    return [pos for pos in target_pos]

# Initialize components
piper = init_piper()
udp_socket = setup_udp()
target_position = [150.0, 0.0, 200.0, 0.0, 90.0, 0.0, 0.0]
last_controller_position = None
last_controller_rotation = None
calibration_counter = 0  # 校准计数器
last_sent_position = None  # 上次发送给机械臂的位置

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
            
            # 检查是否在校准模式
            is_calibrating = calibration_counter < CALIBRATION_FRAMES
            
            if is_calibrating:
                calibration_counter += 1
                print(f"校准中... ({calibration_counter}/{CALIBRATION_FRAMES})")
            
            # 更新位置和姿态
            last_controller_position = update_position(target_position, current_position, last_controller_position, is_calibrating)
            last_controller_rotation = update_rotation(target_position, rotation, last_controller_rotation, is_calibrating)
            
            # 只在非校准模式下控制夹爪
            if not is_calibrating:
                control_gripper(target_position, controller_data)
            
        except (socket.timeout, json.JSONDecodeError, KeyError):
            pass  # 忽略超时和解析错误，继续循环
        except Exception as e:
            print(f"数据处理错误: {e}")
            continue

        # 发送控制命令
        try:
            last_sent_position = send_commands(piper, target_position, last_sent_position)
        except Exception as e:
            print(f"控制机械臂时出错: {e}")
        
        # 定期打印状态
        current_time = time.time()
        if current_time - last_print_time >= 1.0:  # 每秒打印一次
            coords = [round(pos * FACTOR) for pos in target_position]
            status = "校准中" if calibration_counter < CALIBRATION_FRAMES else "正常运行"
            print(f"[{status}] Target: X={coords[0]}, Y={coords[1]}, Z={coords[2]}, "
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
        piper.MotionCtrl_1(0x01,0,0)
        print("Piper机械臂已安全断开")
    except Exception as e:
        print(f"断开Piper连接时出错: {e}")
