import asyncio
from robodog import Dog
import json
import logging
from typing import Dict, Any

DEFAULT_HEIGHT = 0.25
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
        axes = data.get('axes', [0, 0])
        buttons = data.get('buttons', [])
        position = data.get('position', {})

        params = {
            'vx': 0.0,
            'wz': 0.0,
            'body_height': DEFAULT_HEIGHT
        }
        # 摇杆控制
        if buttons:
            # 安全地访问axes数组，避免索引越界
            vx_axis = axes[3] if len(axes) > 3 else 0
            wz_axis = axes[2] if len(axes) > 2 else 0
            
            params['vx'] = -vx_axis * SPEED_RANGE[1]
            params['wz'] = -wz_axis * SPEED_RANGE[1]
            logger.info(
                f"移动: {params['vx']:.2f}m/s, 转向: {params['wz']:.2f}rad/s")

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
    host = '192.168.123.77'  # 默认值，根据实际情况修改
    
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
