import asyncio
from robodog import Dog
import json
import logging
from typing import Dict, Any

DEFAULT_HEIGHT = 0.25
MIN_HEIGHT = 0.09
MAX_HEIGHT = 0.30
SPEED_RANGE = (-0.4, 0.4)
UDP_PORT = 12346

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DogController:
    def __init__(self, host):
        self.host = host
        self.dog = None
        self.initialized = False
        self.running = True
        self.udp_transport = None
        self._params_lock = asyncio.Lock()
        self.last_position = None  # 添加位置跟踪
        self.current_height = DEFAULT_HEIGHT  # 跟踪当前高度
        self.HEIGHT_SCALE = 0.2  # 高度调整的缩放因子
        self.movement_position = None  # 添加运动控制位置追踪
        self.MOVEMENT_SCALE = 5.0  # 位置变化到速度的映射系数

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
                self.dog = Dog(host=self.host).__enter__()
                self.dog.body_height = DEFAULT_HEIGHT
                self.dog.set_gait_params(
                    friction=0.6, scale_x=1.2, scale_y=1.0)
                self.initialized = True
                logger.info(f"机器狗已成功连接到 {self.host}")
            except Exception as e:
                self.initialized = False
                logger.error(f"连接失败: {e}")
                raise

    async def _set_parameters_safe(self, params: Dict[str, Any]):
        async with self._params_lock:
            self.dog.set_parameters(params)
            await asyncio.sleep(0.02)

    async def handle_controller(self, data: Dict[str, Any]):
        if not self.initialized:
            await self.init_robot()
        if self._params_lock.locked():
            return
        buttons = data.get('buttons', [])
        position = data.get('position', {})

        params = {
            'vx': 0.0,
            'wz': 0.0,
            'body_height': self.current_height
        }
        current_position = [
            position.get('x', 0),
            position.get('y', 0),
            position.get('z', 0)
        ]
        # 所有控制都在按钮0按下时生效
        if buttons and buttons[0]:
            # 运动控制
            if self.movement_position is not None:
                # 计算位置变化
                delta_x = current_position[0] - self.movement_position[0]
                delta_z = current_position[2] - self.movement_position[2]
                delta_y = current_position[1] - self.movement_position[1]
                # 映射到速度命令
                params['vx'] = -delta_z * self.MOVEMENT_SCALE  # 前后移动（z轴变化）
                params['wz'] = -delta_x * self.MOVEMENT_SCALE  # 转向（x轴变化）
                # 更新高度
                self.current_height = max(MIN_HEIGHT,
                                          min(MAX_HEIGHT,
                                              self.current_height + delta_y * self.HEIGHT_SCALE))
                params['body_height'] = self.current_height
                # 限制速度范围
                params['vx'] = max(SPEED_RANGE[0], min(
                    SPEED_RANGE[1], params['vx']))
                params['wz'] = max(SPEED_RANGE[0], min(
                    SPEED_RANGE[1], params['wz']))
                logger.info(
                    f"移动: {params['vx']:.2f}m/s, 转向: {params['wz']:.2f}rad/s, 高度: {params['body_height']:.2f}m")
            self.movement_position = current_position
        else:
            self.movement_position = None  # 重置位置追踪
            params['vx'] = 0.0
            params['wz'] = 0.0
        await self._set_parameters_safe(params)

    async def shutdown(self):
        self.running = False
        if self.udp_transport:
            self.udp_transport.close()
        if self.dog and self.initialized:
            await self._set_parameters_safe({'body_height': DEFAULT_HEIGHT})
            self.dog.__exit__(None, None, None)

    async def run(self):
        try:
            await self.init_udp()
            while self.running:
                await asyncio.sleep(0.1)
        finally:
            await self.shutdown()


if __name__ == '__main__':
    # 替换为您的机器狗IP地址
    host = '192.168.139.67'  # 默认值，根据实际情况修改
    
    controller = DogController(host=host)
    try:
        print(f"正在连接到机器狗 ({host})...")
        print("如需修改IP地址，请编辑脚本中的host变量")
        asyncio.run(controller.run())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        asyncio.run(controller.shutdown())
    except Exception as e:
        print(f"程序运行错误: {e}")
        print(f"请确保机器狗已开机并位于同一网络中，IP地址正确为: {host}")
        asyncio.run(controller.shutdown())
