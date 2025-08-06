import asyncio
import sys
import os
import json
import logging
import time
from typing import Dict, Any

# 添加 mc_sdk 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "mc_sdk")))
from py_whl import mc_sdk_py
import socket
import subprocess
import re

SPEED_RANGE = (-0.4, 0.4)
UDP_PORT = 12346

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DogController:
    def __init__(self, dog_ip, local_ip="192.168.234.1", local_port=43988):
        self.dog_ip = dog_ip
        self.local_ip = local_ip
        self.local_port = local_port
        self.app = None
        self.initialized = False
        self.running = True
        self.udp_transport = None
        self._params_lock = asyncio.Lock()
        self.last_position = None  # 添加位置跟踪

    async def init_udp(self):
        class UDPProtocol(asyncio.DatagramProtocol):
            def datagram_received(self_, data, _):
                try:
                    message = json.loads(data.decode())
                    if message['controller_id'] == 'controller1':
                        asyncio.create_task(
                            self.handle_controller(message['data']))
                except Exception as e:
                    logger.error(f"数据处理错误: {e}")
        loop = asyncio.get_running_loop()
        self.udp_transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(),
            local_addr=('0.0.0.0', UDP_PORT)
        )

    async def init_robot(self):
        if not self.initialized:
            try:
                self.app = mc_sdk_py.HighLevel()
                logger.info("Initializing robot...")
                self.app.initRobot(self.local_ip, self.local_port, self.dog_ip)
                logger.info("Initialization completed")
                # 让机器狗站起来
                self.app.standUp()
                time.sleep(2)  # 等待站立完成
                self.initialized = True
                logger.info(f"机器狗已成功连接到 {self.dog_ip}")
            except Exception as e:
                self.initialized = False
                logger.error(f"连接失败: {e}")
                raise

    async def _set_parameters_safe(self, vx: float, vy: float, wz: float):
        async with self._params_lock:
            if self.app and self.initialized:
                self.app.move(vx, vy, wz)
            await asyncio.sleep(0.02)

    async def handle_controller(self, data: Dict[str, Any]):
        if not self.initialized:
            await self.init_robot()
        if self._params_lock.locked():
            return
        axes = data.get('axes', [0, 0])
        buttons = data.get('buttons', [])
        position = data.get('position', {})

        vx, vy, wz = 0.0, 0.0, 0.0
        
        # 摇杆控制
        if buttons:
            # 安全地访问axes数组，避免索引越界
            vx_axis = axes[3] if len(axes) > 3 else 0
            wz_axis = axes[2] if len(axes) > 2 else 0
            
            # 映射到机器狗的移动参数
            vx = -vx_axis * SPEED_RANGE[1]  # 前后移动
            vy = 0.0  # 不使用左右移动
            wz = -wz_axis * SPEED_RANGE[1]  # 转向
            
            logger.info(f"移动: vx={vx:.2f}m/s, wz={wz:.2f}rad/s")

        await self._set_parameters_safe(vx, vy, wz)

    async def shutdown(self):
        self.running = False
        if self.udp_transport:
            self.udp_transport.close()
        if self.app and self.initialized:
            try:
                # 停止移动
                self.app.move(0.0, 0.0, 0.0)
                time.sleep(1)
                # 让机器狗进入被动模式
                self.app.passive()
                logger.info("机器狗已进入被动模式")
            except Exception as e:
                logger.error(f"关闭时出错: {e}")

    async def run(self):
        try:
            await self.init_udp()
            while self.running:
                await asyncio.sleep(0.1)
        finally:
            await self.shutdown()


if __name__ == '__main__':
    # 机器狗网络配置
    dog_ip = '192.168.234.1'  # 机器狗IP地址
    def get_local_234_ip():
        """动态获取本机234网段的IP地址"""
        try:
            # 方法1: 通过socket连接获取
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.168.234.1", 80))
                local_ip = s.getsockname()[0]
                if local_ip.startswith("192.168.234."):
                    return local_ip
        except:
            pass
        
        try:
            # 方法2: 通过ipconfig/ifconfig获取所有网卡信息
            if os.name == 'nt':  # Windows
                result = subprocess.run(['ipconfig'], capture_output=True, text=True)
                output = result.stdout
            else:  # Linux/Mac
                result = subprocess.run(['ifconfig'], capture_output=True, text=True)
                output = result.stdout
            
            # 查找234网段的IP
            ip_pattern = r'192\.168\.234\.(\d+)'
            matches = re.findall(ip_pattern, output)
            if matches:
                return f"192.168.234.{matches[0]}"
        except:
            pass
        
        # 默认回退值
        return "192.168.234.23"
    
    local_ip = get_local_234_ip()  # 动态获取本机234网段IP
    local_port = 43988  # 本地端口
    
    controller = DogController(dog_ip=dog_ip, local_ip=local_ip, local_port=local_port)
    try:
        print(f"正在连接到机器狗 ({dog_ip})...")
        print(f"本地地址: {local_ip}:{local_port}")
        print("如需修改IP地址，请编辑脚本中的配置变量")
        asyncio.run(controller.run())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        asyncio.run(controller.shutdown())
    except Exception as e:
        print(f"程序运行错误: {e}")
        print(f"请确保机器狗已开机并位于同一网络中，配置正确")
        print(f"机器狗IP: {dog_ip}, 本地IP: {local_ip}, 端口: {local_port}")
        asyncio.run(controller.shutdown())
