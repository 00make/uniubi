import asyncio
from robodog import Dog
import json
import logging
from typing import Dict, Any

DEFAULT_HEIGHT = 0.25
MIN_HEIGHT = 0.09
MAX_HEIGHT = 0.35
SPEED_RANGE = (-0.4, 0.4)
UDP_PORT = 12346

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DogController:
    def __init__(self):
        self.dog = None
        self.initialized = False
        self.running = True
        self.udp_transport = None
        self._params_lock = asyncio.Lock()
        self.last_position = None  # 添加位置跟踪
        self.current_height = DEFAULT_HEIGHT  # 跟踪当前高度
        self.HEIGHT_SCALE = 0.5  # 高度调整的缩放因子

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
                self.dog = Dog().__enter__()
                self.dog.body_height = DEFAULT_HEIGHT
                self.dog.set_gait_params(
                    friction=0.6, scale_x=1.2, scale_y=1.0)
                self.initialized = True
                logger.info("机器狗已成功连接")
            except Exception as e:
                self.initialized = False
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

        axes = data.get('axes', [0, 0])
        buttons = data.get('buttons', [])
        position = data.get('position', {})
        
        params = {
            'vx': 0.0, 
            'wz': 0.0, 
            'body_height': self.current_height
        }

        # 计算高度调整
        if buttons and buttons[0] and 'z' in position:
            current_position = [
                position.get('x', 0),
                position.get('y', 0),
                position.get('z', 0)
            ]
            
            if self.last_position is not None:
                # 计算z轴移动增量
                delta_z = (current_position[1] - self.last_position[1]) * self.HEIGHT_SCALE
                # 更新高度
                self.current_height = max(MIN_HEIGHT, min(MAX_HEIGHT, self.current_height + delta_z))
                params['body_height'] = self.current_height
            
            self.last_position = current_position
        else:
            self.last_position = None  # 重置位置跟踪

        if buttons:
            params['vx'] = -axes[3] * SPEED_RANGE[1]
            params['wz'] = -axes[2] * SPEED_RANGE[1]
            logger.info(
                f"移动: {params['vx']:.2f}m/s, 转向: {params['wz']:.2f}rad/s, 高度: {params['body_height']:.2f}m")
        
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
    controller = DogController()
    try:
        asyncio.run(controller.run())
    except KeyboardInterrupt:
        asyncio.run(controller.shutdown())
