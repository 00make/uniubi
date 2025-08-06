# Piper SDK 入门教程

## 系统要求

- Linux 操作系统

## 安装步骤

### 1. 安装系统依赖

```bash
sudo apt update && sudo apt install can-utils ethtool
```

### 2. 安装Python依赖包

```bash
pip3 install python-can
pip3 install piper_sdk
```

### 3. 配置环境变量

```bash
export PIPER_SDK_PATH=$(pip3 show piper_sdk | grep ^Location: | awk '{print $2}')
```

## CAN总线配置

### 1. 查找CAN端口

```bash
bash $PIPER_SDK_PATH/piper_sdk/find_all_can_port.sh
```

### 2. 激活CAN端口

#### 注意：PC只插入一个USB转CAN模块

方法一：

```bash
bash $PIPER_SDK_PATH/piper_sdk/can_activate.sh can0 1000000
```

方法二：

```bash
sudo ip link set can0 up type can bitrate 1000000
```

### 3. 检测机械臂

```bash
python3 $PIPER_SDK_PATH/piper_sdk/demo/detect_arm.py --can_port can0 --hz 10 --req_flag 1
```

## 控制脚本使用指南

### 1. 使能机械臂脚本 (piper_ctrl_enable)

```python
from piper_sdk import C_PiperInterface_V2
import time

piper = C_PiperInterface_V2()
piper.ConnectPort()
while(not piper.EnablePiper()):
    time.sleep(0.01)
```

### 2. 回零点脚本 (piper_ctrl_go_zero)

```python
from piper_sdk import C_PiperInterface_V2
import time

piper = C_PiperInterface_V2("can0")
piper.ConnectPort()
while(not piper.EnablePiper()):
    time.sleep(0.01)

factor = 57295.7795  # 1000*180/3.1415926
position = [0,0,0,0,0,0,0]

joint_0 = round(position[0]*factor)
joint_1 = round(position[1]*factor)
joint_2 = round(position[2]*factor)
joint_3 = round(position[3]*factor)
joint_4 = round(position[4]*factor)
joint_5 = round(position[5]*factor)
joint_6 = round(position[6]*1000*1000)

piper.ModeCtrl(0x01, 0x01, 30, 0x00)
piper.JointCtrl(joint_0, joint_1, joint_2, joint_3, joint_4, joint_5)
piper.GripperCtrl(abs(joint_6), 1000, 0x01, 0)
```

### 3. 末端控制脚本 (piper_ctrl_end_pose)

```python
from piper_sdk import C_PiperInterface_V2
import time

piper = C_PiperInterface_V2("can0")
piper.ConnectPort()
while(not piper.EnablePiper()):
    time.sleep(0.01)

piper.GripperCtrl(0,1000,0x01, 0)
factor = 1000
position = [57.0, 0.0, 215.0, 0, 85.0, 0, 0]

count = 0
while True:
    print(piper.GetArmEndPoseMsgs())
    count = count + 1
    
    if(count == 0):
        print("位置1-----------")
        position = [57.0, 0.0, 215.0, 0, 85.0, 0, 0]
    elif(count == 200):
        print("位置2-----------")
        position = [57.0, 0.0, 260.0, 0, 85.0, 0, 60]
    elif(count == 400):
        print("位置1-----------")
        position = [57.0, 0.0, 215.0, 0, 85.0, 0, 0]
        count = 0
    
    X = round(position[0]*factor)
    Y = round(position[1]*factor)
    Z = round(position[2]*factor)
    RX = round(position[3]*factor)
    RY = round(position[4]*factor)
    RZ = round(position[5]*factor)
    joint_6 = round(position[6]*factor)
    
    print(X,Y,Z,RX,RY,RZ)
    piper.MotionCtrl_2(0x01, 0x00, 100, 0x00)
    piper.EndPoseCtrl(X,Y,Z,RX,RY,RZ)
    piper.GripperCtrl(abs(joint_6), 1000, 0x01, 0)
    time.sleep(0.01)
```

### 4. 急停脚本 (piper_ctrl_disable)

```python
from piper_sdk import C_PiperInterface_V2
import time

piper = C_PiperInterface_V2()
piper.ConnectPort()
while(piper.DisablePiper()):
    time.sleep(0.01)
```
