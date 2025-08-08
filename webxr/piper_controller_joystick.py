# code by LinCC111 Boxjod 2025.1.13 Box2AI-Robotics copyright 盒桥智能 版权所有
# Modified for Piper SDK control with WebXR controller support

import time
import socket
import json
from piper_sdk import C_PiperInterface_V2

# ================================
# 常量配置
# ================================
MOVEMENT_SCALE = 600
ROTATION_SCALE = 40
AXIS_MAPPING = {'X': -1, 'Y': -1, 'Z': 1}
UDP_PORT = 12345
FACTOR = 1000

# 校准和限制参数
CALIBRATION_FRAMES = 10
MAX_SINGLE_MOVE = 5000      # 最大单次移动量 (mm/1000)
MAX_SINGLE_ROTATE = 2000    # 最大单次旋转量 (度/1000)

# 初始位置
INITIAL_POSITION = [150.0, 0.0, 200.0, 0.0, 90.0, 0.0, 500.0]

# ================================
# 全局状态管理
# ================================
button_states = {
    'button1_pressed': False,  # 回初始位置按钮状态
    'button3_pressed': False,  # 急停按钮状态
    'emergency_stop': False    # 急停状态
}

# ================================
# 机械臂控制函数
# ================================

def init_piper():
    """初始化Piper机械臂
    
    Returns:
        C_PiperInterface_V2: 机械臂接口对象
    """
    print("正在连接Piper机械臂...")
    piper = C_PiperInterface_V2("can1")
    piper.ConnectPort()
    
    # 先尝试恢复（防止机械臂处于急停状态）
    print("尝试恢复机械臂状态...")
    try:
        piper.MotionCtrl_1(0x02, 0, 0)      # 恢复
        time.sleep(0.1)                     # 短暂等待
        piper.MotionCtrl_2(0x01, 0x01, 0, 0, 0, 0x01)  # 设置水平正装
        time.sleep(0.1)                     # 短暂等待
        piper.MotionCtrl_2(0x01, 0x00, 0, 0x00)   # 位置速度模式
        time.sleep(0.1)                     # 短暂等待
    except Exception as e:
        print(f"恢复尝试: {e}")
    
    # 使能机械臂
    enable_count = 0
    while not piper.EnablePiper():
        enable_count += 1
        print(f"等待机械臂使能... (第{enable_count}次)")
        time.sleep(0.01)
        if enable_count > 300:
            raise Exception("机械臂使能超时")
    
    # 配置机械臂负载参数
    load = 2  # 根据实际情况选择
    print(f"配置机械臂负载参数: {load}")
    piper.ArmParamEnquiryAndConfig(0, 0, 0, 0xAE, load)
    piper.CrashProtectionConfig(0, 0, 0, 0, 0, 0)
    
    print("Piper机械臂连接成功！")
    return piper


def recover_piper(piper):
    """恢复Piper机械臂从急停状态
    
    Args:
        piper: 机械臂接口对象
        
    Returns:
        bool: 恢复是否成功
    """
    print("正在恢复机械臂...")
    try:
        # 执行恢复命令
        piper.MotionCtrl_1(0x02, 0, 0)      # 恢复
        
        # 重新使能机械臂
        enable_count = 0
        while not piper.EnablePiper():
            enable_count += 1
            print(f"等待机械臂使能... (第{enable_count}次)")
            time.sleep(0.01)
            if enable_count > 200:
                raise Exception("机械臂使能超时")
        
        print("机械臂恢复成功！")
        return True
    except Exception as e:
        print(f"机械臂恢复失败: {e}")
        return False


def stop_piper(piper):
    """停止Piper机械臂
    
    Args:
        piper: 机械臂接口对象
        
    Returns:
        bool: 停止是否成功
    """
    print("正在停止机械臂...")
    try:
        piper.MotionCtrl_1(0x01, 0, 0)  # 急停
        print("机械臂已停止")
        return True
    except Exception as e:
        print(f"机械臂停止失败: {e}")
        return False


def go_to_initial_position(piper, target_pos):
    """回到初始位置
    
    Args:
        piper: 机械臂接口对象
        target_pos: 目标位置数组
        
    Returns:
        bool: 操作是否成功
    """
    print("正在回到初始位置...")
    try:
        piper.MotionCtrl_2(0x01, 0x00, 100, 0x00)
        piper.EndPoseCtrl(*[int(x * FACTOR) for x in INITIAL_POSITION[:6]])
        piper.GripperCtrl(500, 1000, 0x01, 0)
        
        # 更新目标位置
        target_pos[:] = INITIAL_POSITION[:]
        print("已回到初始位置")
        return True
    except Exception as e:
        print(f"回初始位置失败: {e}")
        return False

# ================================
# 网络和通信函数
# ================================

def setup_udp():
    """设置UDP套接字
    
    Returns:
        socket.socket: UDP套接字对象
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', UDP_PORT))
    sock.settimeout(0.001)
    print(f"UDP服务器启动，监听端口{UDP_PORT}...")
    return sock


# ================================
# 运动控制函数
# ================================

def update_position(target_pos, current_pos, last_pos, calibration_mode=False):
    """更新目标位置
    
    Args:
        target_pos: 目标位置数组
        current_pos: 当前控制器位置
        last_pos: 上次控制器位置
        calibration_mode: 是否为校准模式
        
    Returns:
        list: 当前位置（用于下次比较）
    """
    if last_pos is None:
        return current_pos
    
    # 校准模式下不应用位置变化，只记录
    if calibration_mode:
        return current_pos
    
    # 计算位置增量（映射控制器坐标到机械臂坐标）
    deltas = [
        (current_pos[2] - last_pos[2]) * MOVEMENT_SCALE * AXIS_MAPPING['X'],  # Z -> X
        (current_pos[0] - last_pos[0]) * MOVEMENT_SCALE * AXIS_MAPPING['Y'],  # X -> Y
        (current_pos[1] - last_pos[1]) * MOVEMENT_SCALE * AXIS_MAPPING['Z']   # Y -> Z
    ]
    
    # 更新目标位置
    for i, delta in enumerate(deltas):
        target_pos[i] += delta
    
    return current_pos


def update_rotation(target_pos, rotation, last_rotation=None, calibration_mode=False):
    """更新姿态
    
    Args:
        target_pos: 目标位置数组
        rotation: 当前控制器旋转
        last_rotation: 上次控制器旋转
        calibration_mode: 是否为校准模式
        
    Returns:
        list: 当前旋转（用于下次比较）
    """
    if last_rotation is None:
        return rotation  # 第一次数据，只记录不应用
    
    # 校准模式下不应用旋转变化，只记录
    if calibration_mode:
        return rotation
    
    # 计算姿态增量（映射控制器旋转到机械臂旋转）
    delta_rx = (rotation[1] - last_rotation[1]) * ROTATION_SCALE * AXIS_MAPPING['X']
    delta_ry = (rotation[0] - last_rotation[0]) * ROTATION_SCALE * AXIS_MAPPING['Y']
    delta_rz = (rotation[2] - last_rotation[2]) * ROTATION_SCALE * AXIS_MAPPING['Z']
    
    # 应用增量
    target_pos[3] += delta_rx
    target_pos[4] += delta_ry
    target_pos[5] += delta_rz
    
    return rotation


def send_commands(piper, target_pos, last_sent_pos=None):
    """发送控制命令到机械臂
    
    Args:
        piper: 机械臂接口对象
        target_pos: 目标位置数组
        last_sent_pos: 上次发送的位置
        
    Returns:
        list: 实际发送的位置
    """
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
    
    # 转换为整数值并发送命令
    coords = [round(pos * FACTOR) for pos in target_pos]
    
    piper.MotionCtrl_2(0x01, 0x00, 100, 0x00)
    piper.EndPoseCtrl(*coords[:6])
    piper.GripperCtrl(abs(coords[6]), 1000, 0x01, 0)
    
    # 返回实际发送的位置用于下次比较
    return [pos for pos in target_pos]

# ================================
# 控制器输入处理函数
# ================================

def control_gripper(target_pos, controller_data):
    """控制夹爪
    
    Args:
        target_pos: 目标位置数组
        controller_data: 控制器数据
    """
    if 'buttons' in controller_data and len(controller_data['buttons']) > 0:
        # 按钮0: 夹爪控制 (按下=关闭, 释放=打开)
        target_pos[6] = 0 if controller_data['buttons'][0] else 50


def control_buttons(piper, target_pos, controller_data):
    """控制其他按钮功能
    
    Args:
        piper: 机械臂接口对象
        target_pos: 目标位置数组
        controller_data: 控制器数据
    """
    global button_states
    
    if 'buttons' not in controller_data or len(controller_data['buttons']) < 4:
        return
    
    buttons = controller_data['buttons']
    
    # 按钮1：回初始位置
    if buttons[1] and not button_states['button1_pressed']:
        button_states['button1_pressed'] = True
        print("执行回初始位置...")
        try:
            # 如果当前处于急停状态，需要先恢复
            if button_states['emergency_stop']:
                if recover_piper(piper):
                    button_states['emergency_stop'] = False
                    print("已从急停状态恢复")
                else:
                    print("恢复失败，无法执行回初始位置")
                    return
            
            # 使用封装的回初始位置函数
            go_to_initial_position(piper, target_pos)
        except Exception as e:
            print(f"回初始位置操作失败: {e}")
    elif not buttons[1]:
        button_states['button1_pressed'] = False
    
    # 按钮3：急停/恢复切换
    if buttons[3] and not button_states['button3_pressed']:
        button_states['button3_pressed'] = True
        try:
            if not button_states['emergency_stop']:
                # 执行急停
                print("执行急停...")
                if stop_piper(piper):
                    button_states['emergency_stop'] = True
                    print("机械臂已急停")
            else:
                # 从急停恢复
                print("从急停恢复...")
                if recover_piper(piper):
                    button_states['emergency_stop'] = False
                    print("机械臂已恢复，正在回到初始位置...")
                    # 恢复后自动回到初始位置
                    go_to_initial_position(piper, target_pos)
                else:
                    print("恢复失败")
        except Exception as e:
            print(f"急停/恢复操作失败: {e}")
    elif not buttons[3]:
        button_states['button3_pressed'] = False

# ================================
# 主程序
# ================================

def main():
    """主程序入口"""
    # 初始化组件
    print("=" * 50)
    print("WebXR Piper机械臂控制系统启动")
    print("=" * 50)
    
    piper = init_piper()
    udp_socket = setup_udp()
    
    # 初始化状态变量
    target_position = INITIAL_POSITION[:]
    last_controller_position = None
    last_controller_rotation = None
    calibration_counter = 0
    last_sent_position = None
    
    # 设置初始位置
    print("设置机械臂初始位置...")
    go_to_initial_position(piper, target_position)
    
    print("开始WebXR控制循环...")
    print("按钮功能:")
    print("- 按钮0: 夹爪开合")
    print("- 按钮1: 回初始位置") 
    print("- 按钮3: 急停/恢复切换")
    print("-" * 50)
    
    # 主控制循环
    try:
        start_time = time.time()
        last_print_time = 0
        
        while time.time() - start_time < 1000:  # 运行1000秒
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
                last_controller_position = update_position(
                    target_position, current_position, last_controller_position, is_calibrating
                )
                last_controller_rotation = update_rotation(
                    target_position, rotation, last_controller_rotation, is_calibrating
                )
                
                # 只在非校准模式下控制夹爪和按钮
                if not is_calibrating:
                    control_gripper(target_position, controller_data)
                    control_buttons(piper, target_position, controller_data)
                
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
                emergency_status = " [急停]" if button_states['emergency_stop'] else ""
                print(f"[{status}{emergency_status}] Target: X={coords[0]}, Y={coords[1]}, Z={coords[2]}, "
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
            stop_piper(piper)
            print("Piper机械臂已安全断开")
        except Exception as e:
            print(f"断开Piper连接时出错: {e}")
        print("程序结束")


if __name__ == "__main__":
    main()
