#!/usr/bin/env python3
# -*-coding:utf8-*-
# Piper机械臂重力补偿程序 (简化版本)
# 注意demo无法直接运行，需要pip安装sdk后才能运行

import time
import math
from piper_sdk import *

class SimpleGravityCompensation:
    def __init__(self, can_port="can0"):
        """
        初始化简单重力补偿控制器
        
        Args:
            can_port: CAN端口名称
        """
        self.piper = C_PiperInterface_V2(can_port)
        self.piper.ConnectPort()
        
        # 等待连接稳定
        time.sleep(0.1)
        
        # 简化的重力补偿参数 - 根据关节位置估算重力力矩
        # 这些参数需要根据实际机械臂进行调优
        self.gravity_compensation_params = {
            1: {"base_torque": 0.0, "pos_factor": 0.0},     # 关节1 (基座旋转，无重力影响)
            2: {"base_torque": 2.5, "pos_factor": 1.8},     # 关节2 (肩部，主要承受重力)
            3: {"base_torque": 1.2, "pos_factor": 0.9},     # 关节3 (手臂，承受部分重力)
            4: {"base_torque": 0.3, "pos_factor": 0.4},     # 关节4 (前臂)
            5: {"base_torque": 0.0, "pos_factor": 0.0},     # 关节5 (腕部旋转)
            6: {"base_torque": 0.0, "pos_factor": 0.0}      # 关节6 (末端旋转)
        }
        
        # 补偿增益系数 (0-1之间，调节补偿强度)
        self.compensation_gain = 0.7
        
        # 最大补偿力矩限制 (安全保护)
        self.max_torque = 8.0  # N·m
        
        print("简单重力补偿控制器初始化完成")
    
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
                # 转换为弧度 (从毫弧度转换)
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
    
    def calculate_simple_gravity_torques(self, joint_angles):
        """
        计算简化的重力补偿力矩
        基于关节角度的简单模型
        
        Args:
            joint_angles: 当前关节角度 (弧度)
            
        Returns:
            gravity_torques: 各关节的重力补偿力矩 (N·m)
        """
        gravity_torques = []
        
        for i in range(6):
            joint_id = i + 1
            angle = joint_angles[i]
            
            # 获取该关节的补偿参数
            params = self.gravity_compensation_params[joint_id]
            base_torque = params["base_torque"]
            pos_factor = params["pos_factor"]
            
            # 简单的重力补偿模型：
            # 主要考虑关节2和3，因为它们承受最大的重力影响
            if joint_id == 2:
                # 关节2 (肩部): 重力力矩与sin(角度)成正比
                torque = base_torque * math.sin(angle + math.pi/2) * pos_factor
            elif joint_id == 3:
                # 关节3 (手臂): 考虑关节2和3的组合影响
                torque = base_torque * math.sin(joint_angles[1] + angle) * pos_factor
            elif joint_id == 4:
                # 关节4 (前臂): 较小的重力影响
                torque = base_torque * math.sin(joint_angles[1] + joint_angles[2]) * pos_factor
            else:
                # 其他关节基本不受重力影响
                torque = 0.0
            
            # 应用补偿增益
            torque *= self.compensation_gain
            
            # 限制力矩范围
            torque = max(-self.max_torque, min(self.max_torque, torque))
            
            gravity_torques.append(torque)
        
        return gravity_torques
    
    def apply_gravity_compensation(self, gravity_torques):
        """
        应用重力补偿力矩到各关节
        
        Args:
            gravity_torques: 重力补偿力矩列表 (N·m)
        """
        # 设置为MIT控制模式
        self.piper.MotionCtrl_2(0x01, 0x04, 0, 0xAD)
        
        # 对每个关节应用补偿力矩
        for i in range(6):
            joint_id = i + 1
            compensated_torque = gravity_torques[i]
            
            # MIT控制参数设置
            # JointMitCtrl(joint_id, position, velocity, kp, kd, torque)
            # 位置和速度设为0，主要使用力矩控制
            # kp和kd设置较小，以实现柔顺控制
            try:
                self.piper.JointMitCtrl(
                    joint_id,           # 关节ID
                    0,                  # 目标位置 (rad)
                    0,                  # 目标速度 (rad/s)
                    0.3,                # 位置增益 kp
                    0.05,               # 阻尼增益 kd  
                    compensated_torque  # 补偿力矩 (N·m)
                )
            except Exception as e:
                print(f"关节{joint_id}控制出错: {e}")
    
    def run_gravity_compensation(self):
        """运行重力补偿主循环"""
        print("开始重力补偿...")
        print("机械臂现在应该变得很轻，可以手动移动")
        print("按Ctrl+C停止程序")
        
        loop_count = 0
        
        try:
            while True:
                # 获取当前关节角度
                joint_angles = self.get_joint_positions()
                
                # 计算重力补偿力矩
                gravity_torques = self.calculate_simple_gravity_torques(joint_angles)
                
                # 应用重力补偿
                self.apply_gravity_compensation(gravity_torques)
                
                # 定期打印调试信息
                loop_count += 1
                if loop_count % 100 == 0:  # 每秒打印一次 (100Hz控制频率)
                    print(f"关节角度 (度): {[round(math.degrees(angle), 1) for angle in joint_angles]}")
                    print(f"补偿力矩 (N·m): {[round(torque, 2) for torque in gravity_torques]}")
                    print("-" * 60)
                
                time.sleep(0.01)  # 100Hz控制频率
                
        except KeyboardInterrupt:
            print("\n正在停止重力补偿...")
            self.stop_compensation()
    
    def stop_compensation(self):
        """停止重力补偿，机械臂进入失能状态"""
        print("停止重力补偿...")
        
        try:
            # 失能机械臂
            while self.piper.DisablePiper():
                time.sleep(0.01)
            print("机械臂已失能，重力补偿已停止")
        except:
            print("停止补偿时出现错误")
    
    def manual_parameter_tuning(self):
        """手动参数调节模式"""
        print("\n=== 参数调节模式 ===")
        print("可以手动调节各关节的重力补偿参数")
        
        while True:
            print("\n当前补偿参数:")
            for joint_id, params in self.gravity_compensation_params.items():
                print(f"关节{joint_id}: base_torque={params['base_torque']:.2f}, pos_factor={params['pos_factor']:.2f}")
            
            print(f"补偿增益: {self.compensation_gain:.2f}")
            
            try:
                cmd = input("\n输入命令 (格式: 关节号 base_torque pos_factor, 或'gain 值'设置增益, 或'run'开始运行, 或'quit'退出): ")
                
                if cmd.lower() == 'quit':
                    break
                elif cmd.lower() == 'run':
                    self.run_gravity_compensation()
                    break
                elif cmd.startswith('gain'):
                    parts = cmd.split()
                    if len(parts) == 2:
                        self.compensation_gain = float(parts[1])
                        print(f"补偿增益已设置为: {self.compensation_gain}")
                else:
                    parts = cmd.split()
                    if len(parts) == 3:
                        joint_id = int(parts[0])
                        base_torque = float(parts[1])
                        pos_factor = float(parts[2])
                        
                        if 1 <= joint_id <= 6:
                            self.gravity_compensation_params[joint_id] = {
                                "base_torque": base_torque,
                                "pos_factor": pos_factor
                            }
                            print(f"关节{joint_id}参数已更新")
                        else:
                            print("关节号必须在1-6之间")
                    else:
                        print("输入格式错误")
            except ValueError:
                print("输入值格式错误")
            except KeyboardInterrupt:
                break

def main():
    """主函数"""
    print("=== Piper机械臂简单重力补偿程序 ===")
    print("此程序将使机械臂在重力补偿模式下运行")
    print("机械臂将变得非常轻，可以手动移动")
    print()
    print("注意事项:")
    print("1. 确保机械臂周围无障碍物")
    print("2. 随时准备按急停按钮")
    print("3. 首次使用时建议调小补偿增益")
    print()
    
    try:
        # 创建重力补偿控制器
        gravity_comp = SimpleGravityCompensation("can0")
        
        # 使能机械臂
        gravity_comp.enable_robot()
        
        # 询问用户选择模式
        mode = input("选择模式: [1] 直接运行  [2] 参数调节模式 (推荐首次使用): ")
        
        if mode == "2":
            gravity_comp.manual_parameter_tuning()
        else:
            # 等待用户确认
            input("按Enter键开始重力补偿...")
            
            # 运行重力补偿
            gravity_comp.run_gravity_compensation()
    
    except Exception as e:
        print(f"程序出错: {e}")
        print("请检查机械臂连接和SDK安装")

if __name__ == "__main__":
    main()
