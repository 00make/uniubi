#!/usr/bin/env python3
# -*-coding:utf8-*-
# Piper机械臂重力补偿实时调参工具
# 注意demo无法直接运行，需要pip安装sdk后才能运行

import time
import math
import threading
import json
import os
from datetime import datetime
from piper_sdk import *

class RealTimeParameterTuner:
    def __init__(self, can_port="can0"):
        """
        实时参数调节工具
        
        Args:
            can_port: CAN端口名称
        """
        self.piper = C_PiperInterface_V2(can_port)
        self.piper.ConnectPort()
        time.sleep(0.1)
        
        # 当前调节的关节
        self.current_joint = 2
        
        # 重力补偿参数
        self.gravity_compensation_params = {
            1: {"base_torque": 0.0, "pos_factor": 0.0},
            2: {"base_torque": 2.5, "pos_factor": 1.8},
            3: {"base_torque": 1.2, "pos_factor": 0.9},
            4: {"base_torque": 0.3, "pos_factor": 0.4},
            5: {"base_torque": 0.0, "pos_factor": 0.0},
            6: {"base_torque": 0.0, "pos_factor": 0.0}
        }
        
        # 补偿增益
        self.compensation_gain = 0.7
        self.max_torque = 8.0
        
        # 控制状态
        self.compensation_running = False
        self.compensation_thread = None
        
        # 调节步长
        self.torque_step = 0.1
        self.factor_step = 0.05
        self.gain_step = 0.05
        
        # 性能监控
        self.performance_data = []
        
        print("实时参数调节工具初始化完成")
    
    def enable_robot(self):
        """使能机械臂"""
        print("正在使能机械臂...")
        while not self.piper.EnablePiper():
            time.sleep(0.01)
        print("机械臂使能成功")
    
    def get_joint_positions(self):
        """获取当前关节角度 (弧度)"""
        try:
            joint_msgs = self.piper.GetArmJointMsgs()
            if hasattr(joint_msgs, 'joint_state'):
                positions = [
                    joint_msgs.joint_state.joint_1 * 1e-3,
                    joint_msgs.joint_state.joint_2 * 1e-3,
                    joint_msgs.joint_state.joint_3 * 1e-3,
                    joint_msgs.joint_state.joint_4 * 1e-3,
                    joint_msgs.joint_state.joint_5 * 1e-3,
                    joint_msgs.joint_state.joint_6 * 1e-3
                ]
                return positions
        except:
            pass
        return [0, 0, 0, 0, 0, 0]
    
    def calculate_gravity_torques(self, joint_angles):
        """计算重力补偿力矩"""
        gravity_torques = []
        
        for i in range(6):
            joint_id = i + 1
            angle = joint_angles[i]
            
            params = self.gravity_compensation_params[joint_id]
            base_torque = params["base_torque"]
            pos_factor = params["pos_factor"]
            
            if joint_id == 2:
                torque = base_torque * math.sin(angle + math.pi/2) * pos_factor
            elif joint_id == 3:
                torque = base_torque * math.sin(joint_angles[1] + angle) * pos_factor
            elif joint_id == 4:
                torque = base_torque * math.sin(joint_angles[1] + joint_angles[2]) * pos_factor
            else:
                torque = 0.0
            
            torque *= self.compensation_gain
            torque = max(-self.max_torque, min(self.max_torque, torque))
            gravity_torques.append(torque)
        
        return gravity_torques
    
    def apply_gravity_compensation(self, gravity_torques):
        """应用重力补偿力矩"""
        self.piper.MotionCtrl_2(0x01, 0x04, 0, 0xAD)
        
        for i in range(6):
            joint_id = i + 1
            compensated_torque = gravity_torques[i]
            
            try:
                self.piper.JointMitCtrl(joint_id, 0, 0, 0.3, 0.05, compensated_torque)
            except Exception as e:
                print(f"关节{joint_id}控制出错: {e}")
    
    def compensation_loop(self):
        """重力补偿主循环"""
        while self.compensation_running:
            try:
                joint_angles = self.get_joint_positions()
                gravity_torques = self.calculate_gravity_torques(joint_angles)
                self.apply_gravity_compensation(gravity_torques)
                
                # 记录性能数据
                self.record_performance_data(joint_angles, gravity_torques)
                
                time.sleep(0.01)  # 100Hz
            except Exception as e:
                print(f"补偿循环错误: {e}")
                break
    
    def start_compensation(self):
        """开始重力补偿"""
        if not self.compensation_running:
            self.compensation_running = True
            self.compensation_thread = threading.Thread(target=self.compensation_loop)
            self.compensation_thread.start()
            print("重力补偿已开始")
    
    def stop_compensation(self):
        """停止重力补偿"""
        if self.compensation_running:
            self.compensation_running = False
            if self.compensation_thread:
                self.compensation_thread.join()
            print("重力补偿已停止")
    
    def record_performance_data(self, joint_angles, gravity_torques):
        """记录性能数据"""
        if len(self.performance_data) > 1000:  # 限制数据量
            self.performance_data.pop(0)
        
        self.performance_data.append({
            'timestamp': time.time(),
            'joint_angles': joint_angles.copy(),
            'gravity_torques': gravity_torques.copy(),
            'parameters': {k: v.copy() for k, v in self.gravity_compensation_params.items()},
            'compensation_gain': self.compensation_gain
        })
    
    def display_current_status(self):
        """显示当前状态"""
        joint_angles = self.get_joint_positions()
        gravity_torques = self.calculate_gravity_torques(joint_angles)
        
        print("\n" + "="*60)
        print(f"当前时间: {datetime.now().strftime('%H:%M:%S')}")
        print(f"补偿状态: {'运行中' if self.compensation_running else '已停止'}")
        print(f"当前调节关节: 关节{self.current_joint}")
        print("-"*60)
        
        print("关节角度 (度):")
        for i, angle in enumerate(joint_angles):
            print(f"  关节{i+1}: {math.degrees(angle):6.1f}°")
        
        print("\n当前补偿力矩 (N·m):")
        for i, torque in enumerate(gravity_torques):
            print(f"  关节{i+1}: {torque:6.2f}")
        
        print(f"\n当前关节{self.current_joint}参数:")
        current_params = self.gravity_compensation_params[self.current_joint]
        print(f"  base_torque: {current_params['base_torque']:6.2f}")
        print(f"  pos_factor:  {current_params['pos_factor']:6.2f}")
        print(f"  补偿增益:    {self.compensation_gain:6.2f}")
        print("="*60)
    
    def adjust_base_torque(self, delta):
        """调整base_torque"""
        old_value = self.gravity_compensation_params[self.current_joint]['base_torque']
        new_value = max(0, old_value + delta)
        self.gravity_compensation_params[self.current_joint]['base_torque'] = new_value
        print(f"关节{self.current_joint} base_torque: {old_value:.2f} -> {new_value:.2f}")
    
    def adjust_pos_factor(self, delta):
        """调整pos_factor"""
        old_value = self.gravity_compensation_params[self.current_joint]['pos_factor']
        new_value = max(0, old_value + delta)
        self.gravity_compensation_params[self.current_joint]['pos_factor'] = new_value
        print(f"关节{self.current_joint} pos_factor: {old_value:.2f} -> {new_value:.2f}")
    
    def adjust_compensation_gain(self, delta):
        """调整补偿增益"""
        old_value = self.compensation_gain
        new_value = max(0, min(1.0, old_value + delta))
        self.compensation_gain = new_value
        print(f"补偿增益: {old_value:.2f} -> {new_value:.2f}")
    
    def switch_joint(self, joint_id):
        """切换当前调节的关节"""
        if 1 <= joint_id <= 6:
            self.current_joint = joint_id
            print(f"切换到关节{joint_id}")
        else:
            print("关节号必须在1-6之间")
    
    def reset_joint_params(self):
        """重置当前关节参数"""
        default_params = {
            1: {"base_torque": 0.0, "pos_factor": 0.0},
            2: {"base_torque": 2.5, "pos_factor": 1.8},
            3: {"base_torque": 1.2, "pos_factor": 0.9},
            4: {"base_torque": 0.3, "pos_factor": 0.4},
            5: {"base_torque": 0.0, "pos_factor": 0.0},
            6: {"base_torque": 0.0, "pos_factor": 0.0}
        }
        
        self.gravity_compensation_params[self.current_joint] = default_params[self.current_joint].copy()
        print(f"关节{self.current_joint}参数已重置为默认值")
    
    def save_parameters(self):
        """保存参数到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gravity_comp_params_{timestamp}.json"
        
        config = {
            'timestamp': timestamp,
            'parameters': self.gravity_compensation_params,
            'compensation_gain': self.compensation_gain,
            'max_torque': self.max_torque
        }
        
        with open(filename, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"参数已保存到: {filename}")
    
    def load_parameters(self, filename=None):
        """从文件加载参数"""
        if filename is None:
            # 列出可用的配置文件
            config_files = [f for f in os.listdir('.') if f.startswith('gravity_comp_params_') and f.endswith('.json')]
            if not config_files:
                print("没有找到配置文件")
                return
            
            print("可用配置文件:")
            for i, f in enumerate(config_files):
                print(f"{i+1}. {f}")
            
            try:
                choice = int(input("选择配置文件序号: ")) - 1
                filename = config_files[choice]
            except (ValueError, IndexError):
                print("无效选择")
                return
        
        try:
            with open(filename, 'r') as f:
                config = json.load(f)
            
            self.gravity_compensation_params = config['parameters']
            self.compensation_gain = config['compensation_gain']
            self.max_torque = config.get('max_torque', 8.0)
            
            print(f"参数已从 {filename} 加载")
        except Exception as e:
            print(f"加载配置文件失败: {e}")
    
    def print_help(self):
        """打印帮助信息"""
        print("\n" + "="*60)
        print("实时参数调节工具 - 快捷键说明")
        print("="*60)
        print("基本控制:")
        print("  space    - 开始/停止重力补偿")
        print("  s        - 显示当前状态")
        print("  h        - 显示此帮助信息")
        print("  q        - 退出程序")
        print()
        print("参数调节:")
        print("  w/x      - 增加/减少 base_torque")
        print("  a/d      - 减少/增加 pos_factor") 
        print("  z/c      - 减少/增加 compensation_gain")
        print()
        print("关节选择:")
        print("  1-6      - 切换到对应关节")
        print("  r        - 重置当前关节参数")
        print()
        print("参数管理:")
        print("  save     - 保存当前参数")
        print("  load     - 加载参数文件")
        print("="*60)
    
    def interactive_tuning(self):
        """交互式调参主循环"""
        print("\n=== Piper机械臂重力补偿实时调参工具 ===")
        self.print_help()
        
        while True:
            try:
                command = input("\n输入命令 (输入 h 查看帮助): ").strip().lower()
                
                if command == 'q' or command == 'quit':
                    break
                elif command == ' ' or command == 'space':
                    if self.compensation_running:
                        self.stop_compensation()
                    else:
                        self.start_compensation()
                elif command == 's' or command == 'status':
                    self.display_current_status()
                elif command == 'h' or command == 'help':
                    self.print_help()
                elif command == 'w':
                    self.adjust_base_torque(self.torque_step)
                elif command == 'x':
                    self.adjust_base_torque(-self.torque_step)
                elif command == 'a':
                    self.adjust_pos_factor(-self.factor_step)
                elif command == 'd':
                    self.adjust_pos_factor(self.factor_step)
                elif command == 'z':
                    self.adjust_compensation_gain(-self.gain_step)
                elif command == 'c':
                    self.adjust_compensation_gain(self.gain_step)
                elif command in '123456':
                    self.switch_joint(int(command))
                elif command == 'r' or command == 'reset':
                    self.reset_joint_params()
                elif command == 'save':
                    self.save_parameters()
                elif command == 'load':
                    self.load_parameters()
                else:
                    print("未知命令，输入 h 查看帮助")
                    
            except KeyboardInterrupt:
                print("\n检测到 Ctrl+C，正在退出...")
                break
            except Exception as e:
                print(f"命令执行错误: {e}")
        
        # 清理
        self.stop_compensation()
        print("调参工具已退出")

def main():
    """主函数"""
    print("=== Piper机械臂重力补偿实时调参工具 ===")
    print("注意事项:")
    print("1. 确保机械臂周围无障碍物")
    print("2. 随时准备按急停按钮") 
    print("3. 建议从小参数开始调节")
    print()
    
    try:
        # 创建调参工具
        tuner = RealTimeParameterTuner("can0")
        
        # 使能机械臂
        tuner.enable_robot()
        
        # 开始交互式调参
        tuner.interactive_tuning()
        
    except Exception as e:
        print(f"程序出错: {e}")
        print("请检查机械臂连接和SDK安装")

if __name__ == "__main__":
    main()
