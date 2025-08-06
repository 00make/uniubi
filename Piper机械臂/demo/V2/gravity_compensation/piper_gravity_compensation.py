#!/usr/bin/env python3
# -*-coding:utf8-*-
# Piper机械臂重力补偿程序
# 注意demo无法直接运行，需要pip安装sdk后才能运行

import time
import math
import numpy as np
from piper_sdk import *

class PiperGravityCompensation:
    def __init__(self, can_port="can0"):
        """
        初始化重力补偿控制器
        
        Args:
            can_port: CAN端口名称
        """
        self.piper = C_PiperInterface_V2(can_port, dh_is_offset=1)
        self.piper.ConnectPort()
        
        # 等待连接稳定
        time.sleep(0.1)
        
        # 机械臂DH参数 (根据Piper实际参数设置)
        # [a, alpha, d, theta_offset] for each joint
        self.dh_params = [
            [0, 0, 0.1595, 0],          # Joint 1
            [0, -math.pi/2, 0, -math.pi/2],  # Joint 2  
            [0.2105, 0, 0, 0],          # Joint 3
            [0.0855, 0, 0.1281, 0],     # Joint 4
            [0, -math.pi/2, 0, 0],      # Joint 5
            [0, math.pi/2, 0.0605, 0]   # Joint 6
        ]
        
        # 各连杆质量 (kg) - 需要根据实际机械臂参数调整
        self.link_masses = [1.5, 2.0, 1.8, 0.8, 0.5, 0.3]
        
        # 各连杆质心位置 (相对于该连杆坐标系的位置, m)
        self.link_coms = [
            [0, 0, 0.08],    # Link 1 质心
            [0.105, 0, 0],   # Link 2 质心  
            [0.1, 0, 0],     # Link 3 质心
            [0.04, 0, 0],    # Link 4 质心
            [0, 0, 0.03],    # Link 5 质心
            [0, 0, 0.02]     # Link 6 质心
        ]
        
        # 重力加速度
        self.g = 9.81  # m/s^2
        
        # 补偿增益 (可调节补偿强度)
        self.compensation_gain = 0.8
        
        # 使能前向运动学计算
        self.piper.EnableFkCal()
        
        print("重力补偿控制器初始化完成")
    
    def enable_robot(self):
        """使能机械臂"""
        print("正在使能机械臂...")
        while not self.piper.EnablePiper():
            time.sleep(0.01)
        print("机械臂使能成功")
    
    def get_joint_positions(self):
        """获取当前关节角度 (弧度)"""
        joint_msgs = self.piper.GetArmJointMsgs()
        if hasattr(joint_msgs, 'joint_state'):
            # 转换为弧度
            positions = [
                joint_msgs.joint_state.joint_1 * 1e-3,  # mrad -> rad
                joint_msgs.joint_state.joint_2 * 1e-3,
                joint_msgs.joint_state.joint_3 * 1e-3,
                joint_msgs.joint_state.joint_4 * 1e-3,
                joint_msgs.joint_state.joint_5 * 1e-3,
                joint_msgs.joint_state.joint_6 * 1e-3
            ]
            return positions
        return [0, 0, 0, 0, 0, 0]
    
    def forward_kinematics(self, joint_angles):
        """
        计算正向运动学，返回各连杆变换矩阵
        
        Args:
            joint_angles: 关节角度列表 (弧度)
            
        Returns:
            transforms: 各连杆相对于基座标系的变换矩阵列表
        """
        transforms = []
        T = np.eye(4)  # 基座标系变换矩阵
        
        for i, (a, alpha, d, theta_offset) in enumerate(self.dh_params):
            theta = joint_angles[i] + theta_offset
            
            # DH变换矩阵
            T_i = np.array([
                [math.cos(theta), -math.sin(theta)*math.cos(alpha), math.sin(theta)*math.sin(alpha), a*math.cos(theta)],
                [math.sin(theta), math.cos(theta)*math.cos(alpha), -math.cos(theta)*math.sin(alpha), a*math.sin(theta)],
                [0, math.sin(alpha), math.cos(alpha), d],
                [0, 0, 0, 1]
            ])
            
            T = T @ T_i
            transforms.append(T.copy())
        
        return transforms
    
    def calculate_gravity_torques(self, joint_angles):
        """
        计算重力补偿力矩
        
        Args:
            joint_angles: 当前关节角度 (弧度)
            
        Returns:
            gravity_torques: 各关节的重力补偿力矩 (N·m)
        """
        # 计算各连杆变换矩阵
        transforms = self.forward_kinematics(joint_angles)
        
        gravity_torques = [0.0] * 6
        
        # 重力向量 (基座标系)
        gravity_vector = np.array([0, 0, -self.g, 0])  # [x, y, z, 1]
        
        for i in range(6):
            torque = 0.0
            
            # 计算关节i对后续所有连杆的重力力矩贡献
            for j in range(i, 6):
                # 连杆j的质心在基座标系中的位置
                com_local = np.array([*self.link_coms[j], 1])  # 齐次坐标
                com_global = transforms[j] @ com_local
                
                # 关节i的轴向量 (z轴方向)
                if i == 0:
                    joint_axis = np.array([0, 0, 1])  # 基座标系z轴
                    joint_pos = np.array([0, 0, 0])
                else:
                    joint_axis = transforms[i-1][:3, 2]  # 关节i-1的z轴
                    joint_pos = transforms[i-1][:3, 3]   # 关节i-1的位置
                
                # 从关节到质心的向量
                r_vec = com_global[:3] - joint_pos
                
                # 重力在连杆j上的力
                force = self.link_masses[j] * gravity_vector[:3]
                
                # 计算力矩: τ = r × F
                torque_vec = np.cross(r_vec, force)
                
                # 投影到关节轴上
                torque += np.dot(torque_vec, joint_axis)
            
            gravity_torques[i] = torque
        
        return gravity_torques
    
    def apply_gravity_compensation(self, gravity_torques):
        """
        应用重力补偿力矩
        
        Args:
            gravity_torques: 重力补偿力矩列表 (N·m)
        """
        # 设置为MIT控制模式
        self.piper.MotionCtrl_2(0x01, 0x04, 0, 0xAD)
        
        # 对每个关节应用补偿力矩
        for i in range(6):
            joint_id = i + 1  # 关节ID从1开始
            
            # 应用补偿力矩 (参数：关节ID, 位置, 速度, kp, kd, 力矩)
            # 位置和速度设为0，主要使用力矩控制
            compensated_torque = gravity_torques[i] * self.compensation_gain
            
            # 限制力矩范围以确保安全
            max_torque = 10.0  # N·m，根据机械臂规格调整
            compensated_torque = max(-max_torque, min(max_torque, compensated_torque))
            
            # MIT控制: JointMitCtrl(joint_id, position, velocity, kp, kd, torque)
            self.piper.JointMitCtrl(joint_id, 0, 0, 0.5, 0.1, compensated_torque)
    
    def run_gravity_compensation(self):
        """运行重力补偿主循环"""
        print("开始重力补偿...")
        print("按Ctrl+C停止程序")
        
        try:
            while True:
                # 获取当前关节角度
                joint_angles = self.get_joint_positions()
                
                # 计算重力补偿力矩
                gravity_torques = self.calculate_gravity_torques(joint_angles)
                
                # 应用重力补偿
                self.apply_gravity_compensation(gravity_torques)
                
                # 打印调试信息
                if int(time.time() * 10) % 10 == 0:  # 每秒打印一次
                    print(f"关节角度 (度): {[math.degrees(angle) for angle in joint_angles]}")
                    print(f"补偿力矩 (N·m): {[round(torque, 3) for torque in gravity_torques]}")
                    print("-" * 50)
                
                time.sleep(0.01)  # 100Hz控制频率
                
        except KeyboardInterrupt:
            print("\n正在停止重力补偿...")
            self.stop_compensation()
    
    def stop_compensation(self):
        """停止重力补偿，切换到位置控制模式"""
        print("停止重力补偿，机械臂将保持当前位置")
        
        # 获取当前关节位置
        joint_angles = self.get_joint_positions()
        
        # 切换到位置控制模式
        self.piper.MotionCtrl_2(0x01, 0x01, 50, 0x00)
        
        # 保持当前位置
        factor = 57295.7795  # rad to mrad*1000
        joint_commands = [round(angle * factor) for angle in joint_angles]
        
        self.piper.JointCtrl(*joint_commands[:6])
        
        print("重力补偿已停止")

def main():
    """主函数"""
    print("=== Piper机械臂重力补偿程序 ===")
    print("此程序将使机械臂在重力补偿模式下运行")
    print("机械臂将变得非常轻，可以手动移动")
    print()
    
    # 创建重力补偿控制器
    gravity_comp = PiperGravityCompensation("can0")
    
    # 使能机械臂
    gravity_comp.enable_robot()
    
    # 等待用户确认
    input("按Enter键开始重力补偿 (确保机械臂周围无障碍物)...")
    
    # 运行重力补偿
    gravity_comp.run_gravity_compensation()

if __name__ == "__main__":
    main()
