import asyncio
import json
import logging
import redis
import time
UDP_PORT = 12346
DEFAULT_SPEED = 0.1
DEFAULT_TURN_SPEED = 10/57.29578
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HandRobotController:
    def __init__(self, host="192.168.1.15", port=6379, db=6):
        self.redis_client = redis.StrictRedis(
            host='localhost', port=6379, db=5)  # 用于接收手柄数据
        self.mini_controller = self.MiniController(host=host, port=port, db=db)
        self.running = True
        self.movement_position = None  # 添加运动控制位置追踪
        self.MOVEMENT_SCALE = 1.0  # 位置变化到速度的映射系数

    class MiniController(object):
        def __init__(self, host="10.168.135.114", port=6379, db=6, redis_client=None) -> None:
            import webxr.test as test
            if redis_client is None:
                self.redis_client = test.CommandRedis(
                    "Robot Control", host=host, port=port, db=db)
            self.command_count = 0
            self.command_count_start_time = time.time()

        def set_movebase_loc_and_angle(self, forward, turn_left, speed=None, turn_speed=None):
            if speed is None:
                command_msg = "set_movebase_dist_mode,{:.4f},{:.4f}".format(
                    forward, turn_left)
            elif turn_speed is None:
                command_msg = "set_movebase_dist_mode,{:.4f},{:.4f},{:.4f}".format(
                    forward, turn_left, speed
                )
            else:
                command_msg = "set_movebase_dist_mode,{:.4f},{:.4f},{:.4f},{:.4f}".format(
                    forward, turn_left, speed, turn_speed
                )
            return self.send_msg(command_msg)

        def set_movebase_mode(self, state):
            if state in [
                "push_mode",
                "dist_mode",
                "loc_and_rot_mode",
                "stay_at_location_mode",
            ]:
                return self.send_msg("set_movebase_mode,{}".format(state))
            else:
                print("set_movebase_mode error")
                return None

        def send_msg(self, msg):
            return self.redis_client.set_command({"msg": msg})

        def request_msg(self, msg, timeout=30*60):  # 30min TODO
            return self.redis_client.request_command({"msg": msg})

        def set_movebase_speed(self, speed, turn_speed):
            # forward_speed: m/s
            # turn_speed: rad/s 这里输入弧度，后续处理当中会转换为角度
            turn_speed = turn_speed*57.29578  # rad/s to degree/s
            # 我们把速度模式转为位置摸索，
            # 如果控制中断，机器人也指挥在最后一个指令的速度移动0.5m，转向45度
            if speed >= 0.04:
                forward = 0.5
            elif speed <= -0.04:
                speed = -speed
                forward = -0.5
            else:
                # 最小速度值
                speed = 0.1
                forward = 0
            if turn_speed >= 10:
                turn_left = 45
            elif turn_speed <= -10:
                turn_speed = -turn_speed
                turn_left = -45
            else:
                # 最小角速度值
                turn_speed = 10
                turn_left = 0
            print('forward:', forward, 'turn_left:', turn_left,
                  'speed:', speed, 'turn_speed:', turn_speed)
            if speed > 0.4 or speed < -0.4:
                print('speed out of range')
                return
            if turn_speed > 45 or turn_speed < -45:
                print('turn_speed out of range')
                return
            if forward == 0 and turn_left == 0:
                self.set_movebase_mode("stay_at_location_mode")
            else:
                self.set_movebase_loc_and_angle(
                    forward, turn_left, speed, turn_speed)
            # 控制频率
            if self.command_count % 100 == 0:
                self.command_count_start_time = time.time()
            elif self.command_count % 100 == 99:
                print('last 100 commands hz:', 100 /
                      (time.time()-self.command_count_start_time))
            self.command_count += 1
            return

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

    async def handle_controller(self, data):
        """处理从UDP接收到的控制器数据"""
        try:
            buttons = data.get('buttons', [])
            position = data.get('position', {})
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
                    # 映射到速度命令
                    linear_speed = -delta_z * self.MOVEMENT_SCALE  # 前后移动（z轴变化）
                    angular_speed = -delta_x * self.MOVEMENT_SCALE  # 转向（x轴变化）
                    # 使用mini_controller控制机器人
                    self.mini_controller.set_movebase_speed(
                        linear_speed, angular_speed)
                    logger.info(
                        f"移动: {linear_speed:.2f}m/s, 转向: {angular_speed:.2f}rad/s")
                self.movement_position = current_position
            else:
                self.movement_position = None  # 重置位置追踪
                # 停止移动
                self.mini_controller.set_movebase_speed(0.0, 0.0)
        except Exception as e:
            print(f"Error processing controller data: {e}")

    async def udp_listener(self):
        """创建一个UDP监听器"""
        class UDPProtocol(asyncio.DatagramProtocol):
            def __init__(self, controller):
                self.controller = controller

            def datagram_received(self, data, addr):
                try:
                    message = json.loads(data.decode())
                    if message['controller_id'] == 'controller1':
                        asyncio.create_task(
                            self.controller.handle_controller(message['data']))
                except Exception as e:
                    logger.error(f"Error decoding or handling UDP data: {e}")
        loop = asyncio.get_running_loop()
        self.udp_transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self),
            local_addr=('0.0.0.0', UDP_PORT)
        )
        print(f"Listening for UDP packets on port {UDP_PORT}")
        try:
            await asyncio.Future()  # 保持监听器运行
        finally:
            self.udp_transport.close()

    async def shutdown(self):
        self.running = False
        if self.udp_transport:
            self.udp_transport.close()

    async def run(self):
        try:
            await self.init_udp()
            while self.running:
                await asyncio.sleep(0.1)
        finally:
            await self.shutdown()


if __name__ == "__main__":
    controller = HandRobotController()
    try:
        asyncio.run(controller.run())
    except KeyboardInterrupt:
        asyncio.run(controller.shutdown())
