#!/usr/bin/env python3
"""
简化版Piper机械臂自动连接服务
适用于无法安装完整piper_sdk的环境
"""

import os
import sys
import time
import subprocess
import threading
import logging
import signal
from pathlib import Path
from typing import Optional, List, Dict
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/piper_service.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SimplePiperService:
    def __init__(self, config_file: str = "/etc/piper_service.conf"):
        self.config_file = config_file
        self.config = self.load_config()
        self.running = False
        self.current_can_port = None
        self.monitoring_thread = None
        
    def load_config(self) -> Dict:
        """加载配置文件"""
        default_config = {
            "can_name": "can0",
            "bitrate": 1000000,
            "check_interval": 5,
            "usb_address": None,
            "log_level": "INFO"
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
                logger.info(f"已加载配置文件: {self.config_file}")
            except Exception as e:
                logger.warning(f"加载配置文件失败，使用默认配置: {e}")
        else:
            # 创建默认配置文件
            self.save_config(default_config)
            
        return default_config
    
    def save_config(self, config: Dict):
        """保存配置文件"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"配置文件已保存: {self.config_file}")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
    
    def check_dependencies(self) -> bool:
        """检查系统依赖"""
        dependencies = ['ethtool', 'can-utils']
        missing = []
        
        for dep in dependencies:
            result = subprocess.run(['dpkg', '-l'], capture_output=True, text=True)
            if dep not in result.stdout:
                missing.append(dep)
        
        if missing:
            logger.error(f"缺少依赖包: {missing}")
            logger.info("请运行: sudo apt update && sudo apt install " + " ".join(missing))
            return False
        
        logger.info("系统依赖检查通过")
        return True
    
    def find_can_interfaces(self) -> List[Dict]:
        """查找所有CAN接口"""
        try:
            result = subprocess.run(['ip', '-br', 'link', 'show', 'type', 'can'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return []
            
            interfaces = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    iface_name = line.split()[0]
                    
                    # 获取USB地址
                    ethtool_result = subprocess.run(['sudo', 'ethtool', '-i', iface_name], 
                                                  capture_output=True, text=True)
                    usb_address = None
                    if ethtool_result.returncode == 0:
                        for ethtool_line in ethtool_result.stdout.split('\n'):
                            if 'bus-info' in ethtool_line:
                                usb_address = ethtool_line.split()[-1]
                                break
                    
                    interfaces.append({
                        'name': iface_name,
                        'usb_address': usb_address,
                        'status': 'UP' if 'UP' in line else 'DOWN'
                    })
            
            return interfaces
        except Exception as e:
            logger.error(f"查找CAN接口失败: {e}")
            return []
    
    def configure_can_interface(self, interface_name: str) -> bool:
        """配置CAN接口"""
        try:
            can_name = self.config['can_name']
            bitrate = self.config['bitrate']
            
            logger.info(f"配置CAN接口: {interface_name} -> {can_name}, bitrate: {bitrate}")
            
            # 停止接口
            subprocess.run(['sudo', 'ip', 'link', 'set', interface_name, 'down'], 
                         capture_output=True)
            
            # 设置比特率
            result = subprocess.run(['sudo', 'ip', 'link', 'set', interface_name, 'type', 'can', 
                                   'bitrate', str(bitrate)], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"设置比特率失败: {result.stderr}")
                return False
            
            # 启动接口
            result = subprocess.run(['sudo', 'ip', 'link', 'set', interface_name, 'up'], 
                                   capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"启动CAN接口失败: {result.stderr}")
                return False
            
            # 重命名接口
            if interface_name != can_name:
                subprocess.run(['sudo', 'ip', 'link', 'set', interface_name, 'down'], 
                             capture_output=True)
                result = subprocess.run(['sudo', 'ip', 'link', 'set', interface_name, 'name', can_name], 
                                       capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"重命名接口失败: {result.stderr}")
                else:
                    subprocess.run(['sudo', 'ip', 'link', 'set', can_name, 'up'], 
                                 capture_output=True)
                    logger.info(f"接口已重命名: {interface_name} -> {can_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"配置CAN接口失败: {e}")
            return False
    
    def test_can_connection(self, can_port: str) -> bool:
        """测试CAN连接（发送测试消息）"""
        try:
            # 发送CAN测试消息
            result = subprocess.run(['cansend', can_port, '123#deadbeef'], 
                                   capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                logger.info(f"CAN接口 {can_port} 连接正常")
                self.current_can_port = can_port
                return True
            else:
                logger.warning(f"CAN接口 {can_port} 测试失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.warning(f"CAN接口 {can_port} 测试超时")
            return False
        except Exception as e:
            logger.error(f"测试CAN连接失败: {e}")
            return False
    
    def monitor_can_hotplug(self):
        """监控CAN热插拔"""
        last_interfaces = set()
        
        while self.running:
            try:
                current_interfaces = self.find_can_interfaces()
                current_names = {iface['name'] for iface in current_interfaces}
                
                # 检测新插入的接口
                new_interfaces = current_names - last_interfaces
                removed_interfaces = last_interfaces - current_names
                
                if new_interfaces:
                    logger.info(f"检测到新的CAN接口: {new_interfaces}")
                    self.handle_can_change()
                
                if removed_interfaces:
                    logger.info(f"检测到移除的CAN接口: {removed_interfaces}")
                    if self.current_can_port in removed_interfaces:
                        logger.warning("当前使用的CAN接口已断开")
                        self.current_can_port = None
                    self.handle_can_change()
                
                last_interfaces = current_names
                time.sleep(self.config.get('check_interval', 5))
                
            except Exception as e:
                logger.error(f"监控CAN热插拔出错: {e}")
                time.sleep(5)
    
    def handle_can_change(self):
        """处理CAN接口变化"""
        interfaces = self.find_can_interfaces()
        
        if not interfaces:
            logger.warning("未检测到CAN接口")
            return
        
        # 如果配置了特定USB地址，优先选择
        target_interface = None
        usb_address = self.config.get('usb_address')
        
        if usb_address:
            for iface in interfaces:
                if iface['usb_address'] == usb_address:
                    target_interface = iface
                    break
        
        # 如果没有找到指定USB地址的接口，选择第一个
        if not target_interface:
            if len(interfaces) == 1:
                target_interface = interfaces[0]
            else:
                logger.warning(f"检测到多个CAN接口: {[i['name'] for i in interfaces]}")
                logger.info("将使用第一个接口，建议在配置文件中指定usb_address")
                target_interface = interfaces[0]
        
        if target_interface:
            logger.info(f"选择CAN接口: {target_interface['name']} (USB: {target_interface['usb_address']})")
            
            # 配置接口
            if self.configure_can_interface(target_interface['name']):
                # 测试CAN连接
                can_name = self.config['can_name']
                if self.test_can_connection(can_name):
                    logger.info("CAN服务已就绪")
                else:
                    logger.error("CAN连接测试失败")
    
    def start(self):
        """启动服务"""
        logger.info("启动Simple Piper CAN服务")
        
        if not self.check_dependencies():
            return False
        
        self.running = True
        
        # 初始化CAN连接
        self.handle_can_change()
        
        # 启动监控线程
        self.monitoring_thread = threading.Thread(target=self.monitor_can_hotplug, daemon=True)
        self.monitoring_thread.start()
        
        logger.info("Simple Piper CAN服务已启动")
        return True
    
    def stop(self):
        """停止服务"""
        logger.info("停止Simple Piper CAN服务")
        self.running = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Simple Piper CAN服务已停止")
    
    def get_status(self) -> Dict:
        """获取服务状态"""
        interfaces = self.find_can_interfaces()
        
        status = {
            'running': self.running,
            'can_interfaces': interfaces,
            'current_can_port': self.current_can_port,
            'config': self.config
        }
        
        return status

def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"收到信号 {signum}，正在关闭服务...")
    if hasattr(signal_handler, 'service'):
        signal_handler.service.stop()
    sys.exit(0)

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Piper CAN自动连接服务")
    parser.add_argument("--config", default="/etc/piper_service.conf", help="配置文件路径")
    parser.add_argument("--status", action="store_true", help="显示状态")
    
    args = parser.parse_args()
    
    service = SimplePiperService(args.config)
    signal_handler.service = service
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.status:
        status = service.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return
    
    # 前台运行
    if service.start():
        try:
            while service.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            service.stop()

if __name__ == "__main__":
    main()
