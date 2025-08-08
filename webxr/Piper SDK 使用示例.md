# Piper SDK 使用示例

本文档提供了一系列使用 Piper SDK 控制机械臂的 Python 代码示例。


sudo ip link set can1 up type can bitrate 1000000

## 1. 基础设置与连接

### 连接机械臂

```python
import time
from piper_sdk import *

# 初始化并连接到机械臂
# 如果使用can0，可以写作 C_PiperInterface_V2("can0")
piper = C_PiperInterface_V2("can1")
piper.ConnectPort()
```

### 使能机械臂

在发送大多数控制指令之前，需要先使能机械臂。

```python
# 循环直到机械臂成功使能
while not piper.EnablePiper():
    time.sleep(0.01)
```

## 2. 机械臂参数配置

### 2.1 `ArmParamEnquiryAndConfig` 函数详解

该函数用于查询和配置机械臂的多种参数。

```python
(method) def ArmParamEnquiryAndConfig(
    param_enquiry: Literal[0, 1, 2, 3, 4] = 0,
    param_setting: Literal[0, 1, 2] = 0,
    data_feedback_0x48x: Literal[0, 1, 2] = 0,
    end_load_param_setting_effective: Literal[0, 174] = 0,
    set_end_load: Literal[0, 1, 2, 3] = 3
) -> None
```

**参数说明:**

关节最大加速度 默认 300


- `param_enquiry`: 参数查询
  - `0x01`: 查询末端 V/acc (`0x478`)
  - `0x02`: 查询碰撞防护等级 (`0x47B`)
  - `0x03`: 查询当前轨迹索引
  - `0x04`: 查询夹爪/示教器参数索引 (V1.5-2版本后)
- `param_setting`: 参数设置
  - `0x01`: 设置末端 V/acc 参数为初始值
  - `0x02`: 设置全部关节限位、关节最大速度、关节加速度为默认值
- `data_feedback_0x48x`: `0x48X` 报文反馈设置
  - `0x00`: 无效
  - `0x01`: 开启周期反馈 (上报1~6号关节当前末端速度/加速度)
  - `0x02`: 关闭周期反馈
- `end_load_param_setting_effective`: 末端负载参数设置是否生效
  - `0xAE`: 生效
- `set_end_load`: 设置末端负载
  - `0x00`: 空载
  - `0x01`: 半载
  - `0x02`: 满载
  - `0x03`: 无效
### 3.2 设置末端负载参数

根据实际负载情况设置正确的负载参数。

```python
# 设置负载等级
# 0: 空载
# 1: 半载
# 2: 满载
load = 2  # 根据实际情况选择
piper.ArmParamEnquiryAndConfig(0, 0, 0, 0xAE, load)
```


### 2.2 设定安装位置为水平正装

```python 
piper.MotionCtrl_2(0x01, 0x01, 0, 0, 0, 0x01) 
```

### 2.3 设置参数为默认值

将全部关节限位、关节最大速度、关节加速度设置为默认值。

```python
import time
from piper_sdk import *

if __name__ == "__main__":
    piper = C_PiperInterface_V2("can0")
    piper.ConnectPort()
    # 设置参数为默认值
    piper.ArmParamEnquiryAndConfig(0x01, 0x02, 0, 0, 0x02)
    
    # 循环查询以确认设置
    while True:
        piper.SearchAllMotorMaxAngleSpd()
        print(piper.GetAllMotorAngleLimitMaxSpd())
        time.sleep(0.01)
```

## 3. 运动与过载保护调整

调整以下参数可以帮助解决运动过程中的过载保护问题。

### 3.1 调整碰撞防护等级

机械臂有碰撞防护等级设置，可以降低其敏感度。

```python
# 示例：设置所有关节的碰撞防护等级为0（不检测碰撞）
piper.CrashProtectionConfig(0, 0, 0, 0, 0, 0)

# 示例：设置为较低的等级（1-8，数值越高检测阈值越大）
piper.CrashProtectionConfig(8, 8, 8, 8, 8, 8)
```

**检查当前碰撞防护等级:**

```python
piper.ArmParamEnquiryAndConfig(0x02, 0x00, 0x00, 0x00, 0x03)
print(piper.GetCrashProtectionLevelFeedback())
```




### 3.3 调整关节最大加速度

降低关节的最大加速度可以减少冲击，从而避免误触发过载保护。

```python
# 设置所有关节的最大加速度（0-500，对应0-5 rad/s²）
for i in range(1, 7):
    # 注意：数据的写入需要时间，发送完指令后需要延时
    piper.JointMaxAccConfig(i, 200)
    print(f"设置关节 {i} 最大加速度")
    time.sleep(0.5)

# 循环查询以确认设置
while True:
    piper.SearchAllMotorMaxAccLimit()
    print(piper.GetAllMotorMaxAccLimit())
    time.sleep(0.1)
```

参考 demo: `piper_set_motor_max_acc_limit.py`

### 3.4 调整运动速度百分比

在位置控制模式下，降低运动速度可以使运动更平滑。

```python
# 设置运动速度为30%
piper.MotionCtrl_2(0x01, 0x01, 30, 0x00)
```

## 4. 电机参数读写

### 4.1 单独设定某个电机的最大速度

**注意**: 此指令直接将数据写入驱动Flash，不可实时更新。如需动态调速，请使用位置速度模式中的速度百分比。

```python
import time
from piper_sdk import *

if __name__ == "__main__":
    piper = C_PiperInterface_V2("can0")
    piper.ConnectPort()
    while not piper.EnablePiper():
        time.sleep(0.01)

    # 为所有关节设置最大速度为 3 rad/s
    for i in range(1, 7):
        piper.MotorMaxSpdSet(i, 3000)
        time.sleep(0.1)

    # 循环查询以确认设置
    while True:
        piper.SearchAllMotorMaxAngleSpd()
        print(piper.GetAllMotorAngleLimitMaxSpd())
        time.sleep(0.01)
```

### 4.2 读取所有电机的最大加速度限制

```python
import time
from piper_sdk import *

if __name__ == "__main__":
    piper = C_PiperInterface_V2()
    piper.ConnectPort()
    while True:
        piper.SearchAllMotorMaxAccLimit()
        print(piper.GetAllMotorMaxAccLimit())
        time.sleep(0.01)
```

### 4.3 读取所有电机的最大角速度限制

```python
import time
from piper_sdk import *

if __name__ == "__main__":
    piper = C_PiperInterface_V2()
    piper.ConnectPort()
    while True:
        piper.SearchAllMotorMaxAngleSpd()
        print(piper.GetAllMotorAngleLimitMaxSpd())
        time.sleep(0.01)
```

## 5. 夹爪控制

### 设置夹爪力度大小

```python
# 设置夹爪力为 1N
piper.GripperCtrl(0, 1000, 0x01, 0)

# 设置夹爪力为 5N
piper.GripperCtrl(0, 5000, 0x01, 0)
```

## 6. 完整设置示例

以下代码整合了多项设置，用于调整过载保护相关的参数。

```python
from piper_sdk import *
import time

if __name__ == "__main__":
    piper = C_PiperInterface_V2("can0")
    piper.ConnectPort()
    
    # 1. 使能机械臂
    while not piper.EnablePiper():
        time.sleep(0.01)
    
    # 2. 设置碰撞防护等级为较低值或关闭
    print("设置碰撞防护等级为关闭...")
    piper.CrashProtectionConfig(0, 0, 0, 0, 0, 0)
    time.sleep(0.1)
    
    # 3. 设置为无负载模式
    print("设置为无负载模式...")
    piper.ArmParamEnquiryAndConfig(0, 0, 0, 0xAE, 0)
    time.sleep(0.1)
    
    # 4. 降低最大加速度限制
    print("降低所有关节最大加速度...")
    for i in range(1, 7):
        piper.JointMaxAccConfig(i, 200)  # 降低加速度至 2 rad/s²
        time.sleep(0.1)
    
    # 5. 使用较低的运动速度百分比进行运动
    print("设置运动速度为 30%...")
    piper.MotionCtrl_2(0x01, 0x01, 30, 0x00)
    
    print("过载保护相关参数已调整完毕。")

```
