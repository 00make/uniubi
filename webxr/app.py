from flask import Flask, render_template, send_from_directory
from flask_sock import Sock
from typing import Dict, Any
import json
import socket
import logging
import ssl
# $ pip install pyopenssl
# 机器狗高度控制
# web 摄像头esp32

# 常量配置
ARM_ADDRESS = ('127.0.0.1', 12345)  # 机械臂地址
DOG_ADDRESS = ('127.0.0.1', 12346)  # 机器狗地址
# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化Flask应用
app = Flask(__name__,
            static_url_path='',
            static_folder='static',
            template_folder='templates')
sock = Sock(app)

# 初始化两个UDP socket
arm_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dog_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def handle_controller_data(controller_id: str, data: Dict[str, Any]):
    """处理控制器数据并转发到对应设备"""
    message = {
        'controller_id': controller_id,
        'data': data
    }

    # 右手控制器(controller2)控制机械臂，左手控制器(controller1)控制机器狗
    if controller_id == 'controller2':
        arm_socket.sendto(json.dumps(message).encode(), ARM_ADDRESS)
        logger.info(f"发送机械臂控制数据: {message}")
    elif controller_id == 'controller1':
        dog_socket.sendto(json.dumps(message).encode(), DOG_ADDRESS)
        logger.info(f"发送机器狗控制数据: {message}")

# 路由配置


@app.route('/')
def index():
    return render_template('web_paint.html')


@app.route('/static/<path:folder>/<path:path>')
def send_static(folder, path):
    return send_from_directory(f'static/{folder}', path)


@sock.route('/ws')
def ws(ws):
    try:
        while True:
            data = ws.receive()
            if not data:
                logger.warning("WebSocket 接收到空数据")
                continue

            msg = json.loads(data)
            if msg['type'] == 'controllers_state':
                controller_data = msg['data']
                if 'controller1' in controller_data:
                    handle_controller_data(
                        'controller1', controller_data['controller1'])
                if 'controller2' in controller_data:
                    handle_controller_data(
                        'controller2', controller_data['controller2'])
    except json.JSONDecodeError as je:
        logger.error(f"JSON解析错误: {je}")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}", exc_info=True)


if __name__ == '__main__':
    try:
        app.run(ssl_context='adhoc', host='0.0.0.0', debug=True)
    finally:
        arm_socket.close()
        dog_socket.close()
