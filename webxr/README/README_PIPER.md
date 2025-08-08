# Piper WebXR控制器使用说明

## 文件说明

- `piper_controller_joystick.py` - 使用Piper SDK的WebXR控制器（推荐使用）
- `arm_controller_joystick.py` - 原始的使用其他机械臂SDK的控制器

## 安装依赖

### 1. 安装系统依赖

```bash
sudo apt update && sudo apt install can-utils ethtool
```

### 2. 安装Python依赖

```bash
pip3 install python-can
pip3 install piper_sdk
pip3 install numpy
```

## 硬件准备

### 1. 连接CAN总线

- 将USB转CAN模块连接到PC
- 确保机械臂通过CAN总线连接

### 2. 配置CAN端口

```bash
# 查找CAN端口
bash find_all_can_port.sh

# 激活CAN端口（假设是can0）
sudo ip link set can0 up type can bitrate 1000000
```

### 3. 测试机械臂连接

```bash
python3 -c "
from piper_sdk import C_PiperInterface_V2
piper = C_PiperInterface_V2('can0')
print('连接状态:', piper.ConnectPort())
"
```

## 运行程序

### 1. 启动WebXR控制器

```bash
cd webxr
python3 piper_controller_joystick.py
```

### 2. 控制说明

#### WebXR控制器映射

- **位置控制**: 控制器的位置变化直接映射到机械臂末端位置
  - X轴: 控制器左右 → 机械臂前后（取反）
  - Y轴: 控制器前后 → 机械臂左右（取反）
  - Z轴: 控制器上下 → 机械臂上下
  
- **姿态控制**: 控制器的旋转映射到机械臂末端姿态
  - RX: 控制器X轴旋转
  - RY: 控制器Y轴旋转
  - RZ: 通过axes[2]控制

- **夹爪控制**:
  - 按下按钮[0]: 夹爪闭合
  - 松开按钮[0]: 夹爪打开

#### 安全限制

- X轴: -300mm 到 300mm
- Y轴: -300mm 到 300mm
- Z轴: 50mm 到 400mm
- 旋转: -180° 到 180°
- 夹爪: 0 到 1000

## 代码修改要点

### 主要变化

1. **移除了复杂的运动学计算**: Piper SDK直接支持末端位置控制
2. **简化了坐标系统**: 直接使用笛卡尔坐标系（mm和度）
3. **使用Piper SDK API**:
   - `C_PiperInterface_V2()`: 创建接口
   - `EnablePiper()`: 使能机械臂
   - `EndPoseCtrl()`: 末端位置控制
   - `GripperCtrl()`: 夹爪控制
   - `MotionCtrl_2()`: 运动模式设置

### 控制流程

1. 初始化Piper SDK连接
2. 设置安全的初始位置
3. 接收WebXR控制器数据
4. 将控制器数据映射到机械臂坐标
5. 应用安全限制
6. 发送控制命令到Piper机械臂

## 故障排除

### 常见问题

1. **无法连接CAN**: 检查CAN端口是否正确激活
2. **机械臂不响应**: 确认机械臂已正确连接并使能
3. **UDP数据接收问题**: 检查WebXR应用是否正确发送数据到127.0.0.1:12345

### 调试命令

```bash
# 检查CAN接口状态
ip link show can0

# 监听CAN总线数据
candump can0

# 测试UDP连接
nc -u 127.0.0.1 12345
```

## 注意事项

1. **安全第一**: 在测试前确保机械臂周围无人员或障碍物
2. **急停功能**: 程序支持Ctrl+C中断，会安全断开连接
3. **坐标系对应**: 根据实际安装情况调整AXIS_MAPPING参数
4. **速度调整**: 可以通过MOVEMENT_SCALE和ROTATION_SCALE调整灵敏度
