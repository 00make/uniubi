#!/usr/bin/env python3
# -*-coding:utf8-*-
# Piper机械臂重力补偿参数测试验证工具
# 注意demo无法直接运行，需要pip安装sdk后才能运行

import time
import math
import numpy as np
from piper_sdk import *

class GravityCompensationTester:
    def __init__(self, can_port="can0"):
        """
        重力补偿参数测试器
        
        Args:
            can_port: CAN端口名称
        """
        self.piper = C_PiperInterface_V2(can_port)
        self.piper.ConnectPort()
        time.sleep(0.1)
        
        # 测试位置集合 (角度用弧度表示)
        self.test_positions = [
            {
                'name': '水平伸展位置',
                'angles': [0, 0, 0, 0, 0, 0],
                'description': '测试关节2的主要重力补偿'
            },
            {
                'name': '45度抬升位置', 
                'angles': [0, math.pi/4, 0, 0, 0, 0],
                'description': '测试关节2的角度补偿'
            },
            {
                'name': '手臂前伸位置',
                'angles': [0, 0, math.pi/3, 0, 0, 0],
                'description': '测试关节3的重力补偿'
            },
            {
                'name': '复合工作位置',
                'angles': [0, math.pi/6, math.pi/4, -math.pi/6, 0, 0],
                'description': '测试多关节协调补偿'
            },
            {
                'name': '极限测试位置',
                'angles': [0, -math.pi/3, math.pi/2, math.pi/3, 0, 0],
                'description': '测试极限位置的补偿效果'
            }
        ]
        
        # 测试参数组合
        self.test_parameter_sets = [
            {
                'name': '保守参数',
                'params': {
                    2: {'base_torque': 1.5, 'pos_factor': 1.2},
                    3: {'base_torque': 0.8, 'pos_factor': 0.6},
                    4: {'base_torque': 0.2, 'pos_factor': 0.3}
                },
                'gain': 0.5
            },
            {
                'name': '标准参数',
                'params': {
                    2: {'base_torque': 2.5, 'pos_factor': 1.8},
                    3: {'base_torque': 1.2, 'pos_factor': 0.9},
                    4: {'base_torque': 0.3, 'pos_factor': 0.4}
                },
                'gain': 0.7
            },
            {
                'name': '激进参数',
                'params': {
                    2: {'base_torque': 3.5, 'pos_factor': 2.5},
                    3: {'base_torque': 2.0, 'pos_factor': 1.5},
                    4: {'base_torque': 0.6, 'pos_factor': 0.7}
                },
                'gain': 0.9
            }
        ]
        
        # 当前参数
        self.current_params = {}
        self.current_gain = 0.7
        
        print("重力补偿参数测试器初始化完成")
    
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
    
    def move_to_position(self, target_angles):
        """移动到指定位置"""
        print("移动到目标位置...")
        
        # 转换为控制单位
        factor = 57295.7795  # rad to mrad*1000
        joint_commands = [round(angle * factor) for angle in target_angles]
        
        # 切换到位置控制模式
        self.piper.MotionCtrl_2(0x01, 0x01, 30, 0x00)
        
        # 发送位置命令
        self.piper.JointCtrl(*joint_commands[:6])
        
        # 等待到达位置
        time.sleep(3.0)
        
        # 验证位置
        current_angles = self.get_joint_positions()
        position_error = [abs(current_angles[i] - target_angles[i]) for i in range(6)]
        max_error = max(position_error)
        
        if max_error < 0.1:  # 0.1弧度误差容差
            print("位置到达成功")
            return True
        else:
            print(f"位置误差较大: {math.degrees(max_error):.1f}度")
            return False
    
    def calculate_gravity_torques(self, joint_angles):
        """计算重力补偿力矩"""
        gravity_torques = []
        
        for i in range(6):
            joint_id = i + 1
            angle = joint_angles[i]
            
            if joint_id in self.current_params:
                params = self.current_params[joint_id]
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
                
                torque *= self.current_gain
                torque = max(-8.0, min(8.0, torque))
            else:
                torque = 0.0
            
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
    
    def measure_stability(self, duration=3.0, sample_rate=100):
        """
        测量位置稳定性
        
        Args:
            duration: 测量时间 (秒)
            sample_rate: 采样频率 (Hz)
            
        Returns:
            stability_metrics: 稳定性指标字典
        """
        print(f"测量{duration}秒的稳定性...")
        
        samples = int(duration * sample_rate)
        angle_history = []
        torque_history = []
        
        for i in range(samples):
            joint_angles = self.get_joint_positions()
            gravity_torques = self.calculate_gravity_torques(joint_angles)
            self.apply_gravity_compensation(gravity_torques)
            
            angle_history.append(joint_angles.copy())
            torque_history.append(gravity_torques.copy())
            
            time.sleep(1.0 / sample_rate)
        
        # 计算稳定性指标
        angle_history = np.array(angle_history)
        torque_history = np.array(torque_history)
        
        # 角度标准差 (稳定性指标)
        angle_std = np.std(angle_history, axis=0)
        
        # 角速度估计 (运动指标)
        angular_velocity = np.diff(angle_history, axis=0) * sample_rate
        velocity_rms = np.sqrt(np.mean(angular_velocity**2, axis=0))
        
        # 力矩变化率 (控制平滑性)
        torque_variation = np.std(torque_history, axis=0)
        
        stability_metrics = {
            'angle_std': angle_std,           # 角度标准差 (越小越稳定)
            'velocity_rms': velocity_rms,     # 角速度RMS (越小越稳定)
            'torque_variation': torque_variation,  # 力矩变化 (越小越平滑)
            'overall_stability': np.mean(angle_std),  # 总体稳定性评分
            'max_angular_drift': np.max(angle_std)   # 最大角度漂移
        }
        
        return stability_metrics
    
    def test_single_position(self, position_info, param_set):
        """测试单个位置的补偿效果"""
        print(f"\n--- 测试位置: {position_info['name']} ---")
        print(f"描述: {position_info['description']}")
        print(f"参数集: {param_set['name']}")
        
        # 设置测试参数
        self.current_params = param_set['params']
        self.current_gain = param_set['gain']
        
        # 移动到测试位置
        success = self.move_to_position(position_info['angles'])
        if not success:
            return None
        
        # 切换到重力补偿模式
        print("开始重力补偿...")
        
        # 测量稳定性
        stability_metrics = self.measure_stability(duration=5.0)
        
        # 输出结果
        print(f"稳定性评分: {stability_metrics['overall_stability']:.6f}")
        print(f"最大漂移: {math.degrees(stability_metrics['max_angular_drift']):.3f}度")
        
        return stability_metrics
    
    def comprehensive_test(self):
        """全面参数测试"""
        print("=== 开始全面参数测试 ===")
        
        results = {}
        
        for param_set in self.test_parameter_sets:
            param_name = param_set['name']
            results[param_name] = {}
            
            print(f"\n{'='*50}")
            print(f"测试参数集: {param_name}")
            print(f"{'='*50}")
            
            for position_info in self.test_positions:
                position_name = position_info['name']
                
                # 测试这个参数集在这个位置的表现
                metrics = self.test_single_position(position_info, param_set)
                
                if metrics:
                    results[param_name][position_name] = metrics
                
                # 短暂休息
                time.sleep(1.0)
        
        # 分析和报告结果
        self.analyze_test_results(results)
        
        return results
    
    def analyze_test_results(self, results):
        """分析测试结果"""
        print(f"\n{'='*60}")
        print("测试结果分析")
        print(f"{'='*60}")
        
        # 计算每个参数集的总体评分
        param_scores = {}
        
        for param_name, position_results in results.items():
            scores = []
            for position_name, metrics in position_results.items():
                # 稳定性评分 (越高越好，取倒数使越小越好)
                stability_score = 1.0 / (1.0 + metrics['overall_stability'])
                scores.append(stability_score)
            
            if scores:
                param_scores[param_name] = np.mean(scores)
        
        # 排序并显示结果
        sorted_params = sorted(param_scores.items(), key=lambda x: x[1], reverse=True)
        
        print("\n参数集排名 (按稳定性评分):")
        for i, (param_name, score) in enumerate(sorted_params):
            print(f"{i+1}. {param_name}: {score:.4f}")
        
        # 详细分析
        print(f"\n{'='*40}")
        print("详细分析报告")
        print(f"{'='*40}")
        
        for param_name, position_results in results.items():
            print(f"\n{param_name}:")
            
            for position_name, metrics in position_results.items():
                print(f"  {position_name}:")
                print(f"    稳定性: {metrics['overall_stability']:.6f}")
                print(f"    最大漂移: {math.degrees(metrics['max_angular_drift']):.3f}°")
                print(f"    力矩变化: {np.mean(metrics['torque_variation']):.3f}")
        
        # 推荐最佳参数
        if sorted_params:
            best_param = sorted_params[0][0]
            print(f"\n推荐参数集: {best_param}")
            
            # 找到对应的参数值
            for param_set in self.test_parameter_sets:
                if param_set['name'] == best_param:
                    print(f"推荐参数配置:")
                    for joint_id, params in param_set['params'].items():
                        print(f"  关节{joint_id}: base_torque={params['base_torque']:.2f}, "
                              f"pos_factor={params['pos_factor']:.2f}")
                    print(f"  compensation_gain: {param_set['gain']:.2f}")
                    break
    
    def custom_parameter_test(self):
        """自定义参数测试"""
        print("\n=== 自定义参数测试 ===")
        
        # 获取用户输入的参数
        custom_params = {}
        
        for joint_id in [2, 3, 4]:
            print(f"\n关节{joint_id}参数:")
            try:
                base_torque = float(input(f"  base_torque (默认: {2.5 if joint_id==2 else 1.2 if joint_id==3 else 0.3}): ") or 
                                   (2.5 if joint_id==2 else 1.2 if joint_id==3 else 0.3))
                pos_factor = float(input(f"  pos_factor (默认: {1.8 if joint_id==2 else 0.9 if joint_id==3 else 0.4}): ") or 
                                  (1.8 if joint_id==2 else 0.9 if joint_id==3 else 0.4))
                
                custom_params[joint_id] = {
                    'base_torque': base_torque,
                    'pos_factor': pos_factor
                }
            except ValueError:
                print("输入错误，使用默认值")
                custom_params[joint_id] = {
                    'base_torque': 2.5 if joint_id==2 else 1.2 if joint_id==3 else 0.3,
                    'pos_factor': 1.8 if joint_id==2 else 0.9 if joint_id==3 else 0.4
                }
        
        try:
            custom_gain = float(input(f"\ncompensation_gain (默认: 0.7): ") or 0.7)
        except ValueError:
            custom_gain = 0.7
        
        # 创建自定义参数集
        custom_param_set = {
            'name': '自定义参数',
            'params': custom_params,
            'gain': custom_gain
        }
        
        # 选择测试位置
        print(f"\n选择测试位置:")
        for i, pos in enumerate(self.test_positions):
            print(f"{i+1}. {pos['name']} - {pos['description']}")
        
        try:
            choice = int(input("选择位置 (1-5): ")) - 1
            if 0 <= choice < len(self.test_positions):
                test_position = self.test_positions[choice]
                
                # 执行测试
                metrics = self.test_single_position(test_position, custom_param_set)
                
                if metrics:
                    print(f"\n自定义参数测试结果:")
                    print(f"稳定性评分: {metrics['overall_stability']:.6f}")
                    print(f"最大漂移: {math.degrees(metrics['max_angular_drift']):.3f}度")
                    
                    # 给出建议
                    if metrics['overall_stability'] < 0.001:
                        print("评价: 优秀 - 参数配置良好")
                    elif metrics['overall_stability'] < 0.005:
                        print("评价: 良好 - 参数基本合适")
                    elif metrics['overall_stability'] < 0.01:
                        print("评价: 一般 - 建议微调参数")
                    else:
                        print("评价: 较差 - 建议重新调整参数")
            else:
                print("无效选择")
                
        except ValueError:
            print("输入错误")
    
    def interactive_test_menu(self):
        """交互式测试菜单"""
        while True:
            print(f"\n{'='*50}")
            print("重力补偿参数测试工具")
            print(f"{'='*50}")
            print("1. 全面参数测试 (推荐)")
            print("2. 自定义参数测试")
            print("3. 单个位置快速测试")
            print("4. 退出")
            
            try:
                choice = input("\n选择操作 (1-4): ").strip()
                
                if choice == '1':
                    self.comprehensive_test()
                elif choice == '2':
                    self.custom_parameter_test()
                elif choice == '3':
                    self.quick_position_test()
                elif choice == '4':
                    break
                else:
                    print("无效选择")
                    
            except KeyboardInterrupt:
                print("\n检测到 Ctrl+C，退出测试")
                break
    
    def quick_position_test(self):
        """快速位置测试"""
        print(f"\n选择测试位置:")
        for i, pos in enumerate(self.test_positions):
            print(f"{i+1}. {pos['name']}")
        
        try:
            choice = int(input("选择位置 (1-5): ")) - 1
            if 0 <= choice < len(self.test_positions):
                position = self.test_positions[choice]
                
                # 使用标准参数
                standard_params = {
                    'name': '标准参数',
                    'params': {
                        2: {'base_torque': 2.5, 'pos_factor': 1.8},
                        3: {'base_torque': 1.2, 'pos_factor': 0.9},
                        4: {'base_torque': 0.3, 'pos_factor': 0.4}
                    },
                    'gain': 0.7
                }
                
                self.test_single_position(position, standard_params)
            else:
                print("无效选择")
        except ValueError:
            print("输入错误")

def main():
    """主函数"""
    print("=== Piper机械臂重力补偿参数测试验证工具 ===")
    print("此工具将系统性测试不同参数配置的补偿效果")
    print()
    print("注意事项:")
    print("1. 确保机械臂周围无障碍物")
    print("2. 测试过程中机械臂会自动移动到各个位置")
    print("3. 如有异常请立即按急停按钮")
    print()
    
    try:
        # 创建测试器
        tester = GravityCompensationTester("can0")
        
        # 使能机械臂
        tester.enable_robot()
        
        # 等待用户确认
        input("按Enter键开始测试...")
        
        # 进入交互式测试菜单
        tester.interactive_test_menu()
        
        print("测试完成")
        
    except Exception as e:
        print(f"程序出错: {e}")
        print("请检查机械臂连接和SDK安装")

if __name__ == "__main__":
    main()
