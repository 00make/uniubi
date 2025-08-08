import sys
import os
import json
import logging
import socket
import subprocess
import re
import time
import threading
from typing import Dict, Any

# 添加 mc_sdk 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "mc_sdk")))
from py_whl import mc_sdk_py

# --- 配置 ---
SPEED_RANGE = (-0.4, 0.4)  # 速度映射范围
UDP_PORT = 12346           # 监听UDP数据的端口
COMMAND_TIMEOUT = 2.0      # 超过2秒没有收到手柄信号，则停止移动

# --- 日志设置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DogController:
    def __init__(self, dog_ip: str, local_ip: str, local_port: int):
        self.dog_ip = dog_ip
        self.local_ip = local_ip
        self.local_port = local_port

        self.app = mc_sdk_py.HighLevel()
        self.running = False
        self.initialized = False

        # --- 线程安全的共享状态 ---
        self.state_lock = threading.Lock()
        self.latest_command = {'vx': 0.0, 'wz': 0.0}
        self.last_command_time = 0

    def _udp_listener(self):
        """
        运行在独立线程中的UDP监听器。
        """
        logger.info(f"UDP监听线程启动，监听端口 {UDP_PORT}")
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_socket.bind(('0.0.0.0', UDP_PORT))
        except OSError as e:
            logger.error(f"绑定UDP端口 {UDP_PORT} 失败: {e}")
            logger.error("程序将退出，请检查端口是否被占用。")
            self.running = False # 停止主循环
            return
            
        udp_socket.settimeout(1.0) # 设置超时以便能检查 self.running

        while self.running:
            try:
                data, _ = udp_socket.recvfrom(1024)
                message = json.loads(data.decode())

                if message.get('controller_id') == 'controller1':
                    controller_data = message.get('data', {})
                    axes = controller_data.get('axes', [0, 0, 0, 0])
                    
                    # 安全地访问axes数组
                    vx_axis = axes[3] if len(axes) > 3 else 0
                    wz_axis = axes[2] if len(axes) > 2 else 0

                    # 更新共享状态
                    with self.state_lock:
                        self.latest_command['vx'] = -vx_axis * SPEED_RANGE[1]
                        self.latest_command['wz'] = -wz_axis * SPEED_RANGE[1]
                        self.last_command_time = time.time()

            except socket.timeout:
                continue # 只是为了有机会检查 self.running
            except Exception as e:
                logger.error(f"处理UDP数据时出错: {e}")
        
        udp_socket.close()
        logger.info("UDP监听线程已停止。")

    def run(self):
        """
        主控制循环。
        """
        try:
            # 1. 初始化机器人
            logger.info("正在初始化机器人...")
            self.app.initRobot(self.local_ip, self.local_port, self.dog_ip)
            self.initialized = True
            logger.info("机器人初始化完成。")

            # 2. 启动UDP监听线程
            self.running = True
            udp_thread = threading.Thread(target=self._udp_listener, daemon=True)
            udp_thread.start()
            
            # 3. 让机器狗站起来
            logger.info("命令机器狗站立...")
            self.app.standUp()
            time.sleep(3) # 等待站立完成
            logger.info("机器狗已站立。等待手柄信号...")
            self.last_command_time = time.time() # 初始化时间戳

            # 4. 进入主控制循环
            last_sent_command = {'vx': 0.0, 'wz': 0.0}
            while self.running:
                with self.state_lock:
                    current_vx = self.latest_command['vx']
                    current_wz = self.latest_command['wz']
                    last_time = self.last_command_time
                
                # 检查手柄信号是否超时
                if time.time() - last_time > COMMAND_TIMEOUT:
                    current_vx = 0.0
                    current_wz = 0.0
                    if last_sent_command['vx'] != 0.0 or last_sent_command['wz'] != 0.0:
                        logger.warning("手柄信号超时，停止移动。")

                # 只有当命令变化时才发送
                if current_vx != last_sent_command['vx'] or current_wz != last_sent_command['wz']:
                    self.app.move(current_vx, 0.0, current_wz)
                    last_sent_command['vx'] = current_vx
                    last_sent_command['wz'] = current_wz
                    logger.info(f"发送移动命令: vx={current_vx:.2f} m/s, wz={current_wz:.2f} rad/s")

                time.sleep(0.1) # 控制命令发送频率

        except Exception as e:
            logger.error(f"主循环遇到严重错误: {e}")
        finally:
            self.shutdown()
            
    def shutdown(self):
        """
        安全关闭程序。
        """
        logger.info("正在关闭程序...")
        self.running = False
        
        if self.initialized:
            try:
                logger.info("停止移动并进入休息模式...")
                self.app.move(0.0, 0.0, 0.0)
                time.sleep(0.5)
                self.app.passive() # 进入休息模式
                time.sleep(1.0)
                logger.info("机器狗已安全进入休息模式。")
            except Exception as e:
                logger.error(f"关闭机器狗时出错: {e}")
        
        logger.info("程序已关闭。")

def get_local_234_ip() -> str:
    """动态获取本机192.168.234.x网段的IP地址"""
    # 方法1: 通过socket连接获取 (更可靠)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.234.1", 80))
            local_ip = s.getsockname()[0]
            if local_ip.startswith("192.168.234."):
                logger.info(f"通过socket连接找到IP: {local_ip}")
                return local_ip
    except Exception:
        pass
    
    # 方法2: 通过命令行获取 (作为备用)
    try:
        cmd = 'ifconfig' if os.name != 'nt' else 'ipconfig'
        output = subprocess.check_output(cmd, shell=True, text=True)
        matches = re.findall(r'192\.168\.234\.(\d{1,3})', output)
        if matches:
            ip = f"192.168.234.{matches[0]}"
            logger.info(f"通过命令行找到IP: {ip}")
            return ip
    except Exception:
        pass
    
    # 默认回退值
    default_ip = "192.168.234.12"
    logger.warning(f"无法动态获取IP，使用默认值: {default_ip}")
    return default_ip

if __name__ == '__main__':
    dog_ip = '192.168.234.1'
    local_ip = get_local_234_ip()
    local_port = 43988
    
    print("-" * 50)
    print(f"机器狗IP: {dog_ip}")
    print(f"本机IP:   {local_ip}:{local_port}")
    print(f"摇杆端口: {UDP_PORT}")
    print("如需修改，请编辑脚本顶部的配置变量。")
    print("-" * 50)

    controller = DogController(dog_ip=dog_ip, local_ip=local_ip, local_port=local_port)
    
    try:
        controller.run()
    except KeyboardInterrupt:
        print("\n检测到用户中断 (Ctrl+C)。")
    finally:
        controller.shutdown()


        