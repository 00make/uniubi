# %%
import json
import asyncio
import redis
import time


class CommandRedis(object):
    """
    用于控制指令的Redis数据库
    """

    def __init__(self, command_type, host='localhost', port=6379, db=4,
                 command_store_nums=2000):
        print(command_type)
        self.redis_client = redis.StrictRedis(host=host, port=port, db=db)
        self.command_store_nums = command_store_nums
        self.last_process_command_id = None
        self.start_process_command_id = None  # 最近一段指令集的初始id
        # for i in range(self.command_store_nums):
        #     self.clean_key(i)
        # self.clean_key("lastID")
        self.start_flag = True

    def get_last_command_id(self, wait=True):
        """
        获取最后一条指令的ID，如果wait为True则会等待直到获取到ID（阻塞模式），否则直接返回None
        """
        if not self.redis_client.exists("lastID"):
            if wait:
                while True:
                    time.sleep(0.03)
                    if self.redis_client.exists("lastID"):
                        return int(self.redis_client.get("lastID"))
            else:
                return None
        else:
            return int(self.redis_client.get("lastID"))

    def set_last_command_id(self, new_id: int):
        """
        设置最后一条指令的ID
        """
        # print('set_last_command_id', new_id)
        return self.redis_client.set("lastID", new_id)

    def request_command(self, command_content: dict):
        """
        向数据库中添加一条指令，等待指令执行完成后返回执行结果
        """
        # self.unset_task_stop()
        count = 0
        while self.is_locked():
            count += 1
            if count % 200 == 0:
                print('locking', count)
            time.sleep(0.03)
        # self.lock()
        last_id = self.get_last_command_id(wait=False)
        if last_id is None or last_id+1 >= self.command_store_nums:
            self.last_process_command_id = 0
        else:
            self.last_process_command_id = last_id + 1
        last_process_command_id = self.last_process_command_id
        if self.redis_client.exists("{}_r".format(last_process_command_id)):
            self.redis_client.delete("{}_r".format(last_process_command_id))
        # print('request', self.last_process_command_id, command_content['msg'])
        self.set_command(
            command_content, last_process_command_id, lock_flag=False)
        self.unlock()
        count = 0
        while not self.redis_client.exists("{}_r".format(last_process_command_id)):
            count += 1
            if count % 200 == 0:
                print("still doing ", command_content['msg'])
                if command_content['msg'] == "get_neck_transformer":
                    print('msg seems miss, resend', count)
                    return self.request_command(command_content)
                elif command_content['msg'] == "get_movebase_enable_status":
                    print('msg seems miss, resend', count)
                    return self.request_command(command_content)
                elif command_content['msg'] == "get_robot_busy_state":
                    print('msg seems miss, resend', count)
                    return self.request_command(command_content)
                elif command_content['msg'] == "check_neck_using_priority":
                    print('msg seems miss, resend', count)
                    return self.request_command(command_content)
            time.sleep(0.03)
        result = self.redis_client.hget(
            "{}_r".format(last_process_command_id), 'result')
        # print('recv', self.last_process_command_id, result)
        return result

    def set_command(self, command_content: dict, command_id=None, lock_flag=True):
        """
        向数据库中添加一条指令，不等待指令执行完成
        """
        # self.unset_task_stop()
        if lock_flag:
            while self.is_locked():
                time.sleep(0.03)
            # self.lock()
        if command_id is None:
            last_id = self.get_last_command_id(wait=False)
            if last_id is None or last_id+1 >= self.command_store_nums:
                self.last_process_command_id = 0
            else:
                self.last_process_command_id = last_id + 1
        else:
            self.last_process_command_id = command_id
        command_content.update({'timestamp': time.time()})
        self.redis_client.hset(
            self.last_process_command_id, mapping=command_content)
        self.set_last_command_id(self.last_process_command_id)
        if lock_flag:
            self.unlock()
        return True

    def set_result(self, result_content: dict, command_id: int):
        """
        向数据库中返回一条指令的执行结果
        """
        result_content.update({'timestamp': time.time()})
        self.redis_client.hset(str(command_id)+'_r', mapping=result_content)
        return

    def clean_key(self, key):
        return self.redis_client.delete(key)

    def get_last_command_with_id(self, wait=True, timeout=3.0):
        """
        获取最后一条指令的ID和内容，如果wait为True则会等待直到获取到ID（阻塞模式），否则直接返回None。
        Args:
            wait: 是否等待
            timeout: 获取消息的超时时间
        Returns:
            (dict, int): 指令内容和指令ID
        """
        last_id = self.get_last_command_id(wait=wait)
        if last_id is None:
            return None, None
        elif last_id == self.last_process_command_id:
            if wait:
                while True:
                    time.sleep(0.03)
                    new_id = self.get_last_command_id()
                    if new_id != last_id:
                        break
                self.last_process_command_id = new_id
                return self.redis_client.hgetall(str(new_id)), new_id
            else:
                return None, None
        else:
            results = self.redis_client.hgetall(str(last_id))
            if time.time()-float(results[b'timestamp']) >= timeout:
                if self.start_flag:
                    print('msg timeout', time.time() -
                          float(results[b'timestamp']))
                    self.start_flag = False
                    # 消息过时
                if wait:
                    while True:
                        time.sleep(0.03)
                        new_id = self.get_last_command_id()
                        if new_id != last_id:
                            break
                    self.last_process_command_id = new_id
                    return self.redis_client.hgetall(str(new_id)), new_id
                else:
                    return None, None
            else:
                self.last_process_command_id = last_id
                return results, last_id

    def get_last_command(self, wait=True, timeout=3.0):
        """
        获取最后一条指令的内容，如果wait为True则会等待直到获取到ID（阻塞模式），否则直接返回None。
        Args:
            wait: 是否等待
            timeout: 获取消息的超时时间
        Returns:
            dict: 指令内容
        """
        last_id = self.get_last_command_id(wait=wait)
        if last_id is None:
            return None
        elif last_id == self.last_process_command_id:
            if wait:
                while True:
                    time.sleep(0.03)
                    new_id = self.get_last_command_id()
                    if new_id != last_id:
                        break
                self.last_process_command_id = new_id
                return self.redis_client.hgetall(str(new_id))
            else:
                return None
        else:
            results = self.redis_client.hgetall(str(last_id))
            if time.time()-float(results[b'timestamp']) >= timeout:
                if self.start_flag:
                    print('msg timeout', time.time() -
                          float(results[b'timestamp']))
                    self.start_flag = False
                    # 消息过时
                if wait:
                    while True:
                        time.sleep(0.03)
                        new_id = self.get_last_command_id()
                        if new_id != last_id:
                            break
                    self.last_process_command_id = new_id
                    return self.redis_client.hgetall(str(new_id))
                else:
                    return None
            else:
                self.last_process_command_id = last_id
                return results

    def get_commands_by_id(self, command_id: int):
        """
        获取指定ID的指令
        Args:
            command_id: 指令ID
        Returns:
            dict: 指令内容
        """
        return self.redis_client.hgetall(str(command_id))

    def get_last_commands(self):
        """
        获取过去一段时间的指令集,暂不考虑指令集合中指令是否超时问题
        Args:
            command_id: 指令ID
        Returns:
            dict: 指令集内容
        """
        last_commands = []
        last_command_id = self.get_last_command_id(wait=False)
        if last_command_id is None:
            return [], None, None
        if self.start_process_command_id is None:
            self.start_process_command_id = last_command_id
        current_id = self.start_process_command_id
        for i in range(0, (last_command_id-self.start_process_command_id) % self.command_store_nums):
            current_id = self.start_process_command_id+i+1
            if current_id >= self.command_store_nums:
                current_id = current_id-self.command_store_nums
            last_command = self.get_commands_by_id(current_id)
            last_commands.append(last_command)
        start_id = self.start_process_command_id+1
        self.start_process_command_id = last_command_id
        return last_commands, start_id, current_id+1

    def set_task_stop(self):
        """
        设置任务停止
        """
        self.redis_client.set("task_stop", 1)
        return

    def unset_task_stop(self):
        """
        取消任务停止
        """
        self.redis_client.delete("task_stop")
        return

    def is_set_task_stop(self):
        """
        查询任务是否停止
        """
        if self.redis_client.exists("task_stop"):
            self.redis_client.delete("task_stop")
            return True
        else:
            return False

    def clean_stop_info(self):
        """
        清除任务停止信息
        """
        self.redis_client.delete("task_stop_info")
        return

    def get_stop_info(self):
        """
        获取任务停止信息
        """
        while True:
            time.sleep(0.03)
            if self.redis_client.exists("task_stop_info"):
                # TODO 若中止的任务在多层级调用下，目前的方案不能保证完整的信息输出
                return self.redis_client.get("task_stop_info").decode()

    def write_stop_info(self, info: str):
        """
        写入任务停止信息
        """
        return self.redis_client.append("task_stop_info", info)

    def unlock(self):
        """
        解锁数据库
        """
        self.redis_client.delete("lock")
        return

    def is_locked(self):
        """
        查询数据库是否被锁定
        """
        # return self.redis_client.exists("lock")
        set_success = self.redis_client.setnx("lock", 1)
        if set_success:
            self.redis_client.expire("lock", 5)
            return False
        else:
            return True


class MiniController(object):
    def __init__(self, host="10.168.135.114", port=6379, db=6, redis_client=None) -> None:
        if redis_client is None:
            self.redis_client = CommandRedis(
                "Robot Control", host=host, port=port, db=db)
        self.command_count = 0
        self.command_count_start_time = time.time()
        self.last_input = {'speed': 0, 'turn_speed': 0}

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
        self.last_input = {'speed': 0, 'turn_speed': 0}
        if speed == self.last_input['speed'] and turn_speed == self.last_input['turn_speed']:
            # print('same input')
            return
        else:
            self.last_input = {'speed': speed, 'turn_speed': turn_speed}
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


mini_controller = MiniController('192.168.1.15')
# mini_controller.set_movebase_speed(0.1, 10/57.29578)
# time.sleep(1)
# mini_controller.set_movebase_speed(0.1, -10/57.29578)
# time.sleep(1)
# mini_controller.set_movebase_speed(-0.1, 0)
# time.sleep(1)
# mini_controller.set_movebase_speed(0, 0)
# forward: 0.5 turn_left: 45 speed: 0.1 turn_speed: 10.0
# forward: 0.5 turn_left: -45 speed: 0.1 turn_speed: 10.0
# forward: -0.5 turn_left: 0 speed: 0.1 turn_speed: 10
# forward: 0 turn_left: 0 speed: 0.1 turn_speed: 10
UDP_PORT = 12346


class UDPHandler:
    def __init__(self, mini_controller):
        self.mini_controller = mini_controller
        self.redis_client = redis.StrictRedis(
            host='localhost', port=6379, db=5)  # 使用一个新的 Redis 数据库
        self.last_command_time = 0  # 记录上次发送命令的时间
        self.command_interval = 0.1  # 命令间隔时间，10Hz
        self.last_linear_speed = None  # 记录上次的线性速度
        self.last_angular_speed = None  # 记录上次的角速度
        self.is_stopped = False  # 记录是否已经发送停止命令

    def handle_controller_data(self, data):
        """处理从UDP接收到的控制器数据"""
        try:
            # 检查是否达到发送新命令的时间间隔
            current_time = time.time()
            if current_time - self.last_command_time < self.command_interval:
                return  # 如果间隔不够，直接返回，不发送命令
            # 解析数据
            axes = data.get('axes', [0, 0])
            buttons = data.get('buttons', [])
            # 从手柄数据映射到机器人控制
            linear_speed = -axes[3] * 0.4  # 线性速度
            angular_speed = -axes[2] * 50/57.29578  # 角速度
            # 检查是否是停止命令以及是否已经发送过停止命令
            is_stop_command = abs(linear_speed) < 0.001 and abs(
                angular_speed) < 0.001

            # 如果是停止命令且已经处于停止状态，则不重复发送
            if is_stop_command and self.is_stopped:
                return
            # 如果是新的移动命令或首次发送停止命令
            self.is_stopped = is_stop_command
            self.last_linear_speed = linear_speed
            self.last_angular_speed = angular_speed

            # 更新上次发送命令的时间
            self.last_command_time = current_time
            # 使用mini_controller控制机器人
            self.mini_controller.set_movebase_speed(
                linear_speed, angular_speed)
            # 打印控制信息
            print(
                f"Linear Speed: {linear_speed}, Angular Speed: {angular_speed}")
        except Exception as e:
            print(f"Error processing controller data: {e}")

    async def udp_listener(self):
        """创建一个UDP监听器"""
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: self.UDPProtocol(self),
            local_addr=('0.0.0.0', UDP_PORT)
        )
        print(f"Listening for UDP packets on port {UDP_PORT}")
        try:
            await asyncio.Future()  # 保持监听器运行
        finally:
            transport.close()

    class UDPProtocol(asyncio.DatagramProtocol):
        def __init__(self, handler):
            self.handler = handler

        def datagram_received(self, data, addr):
            try:
                message = json.loads(data.decode())
                if message['controller_id'] == 'controller1':
                    self.handler.handle_controller_data(message['data'])
            except Exception as e:
                print(f"Error decoding or handling UDP data: {e}")


async def main():
    udp_handler = UDPHandler(mini_controller)
    await udp_handler.udp_listener()
if __name__ == "__main__":
    asyncio.run(main())
