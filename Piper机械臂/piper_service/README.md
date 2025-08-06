# Piper机械臂CAN自动连接服务

这是一个支持CAN热插拔检测和自动连接的Piper机械臂CAN接口管理服务。

## 功能特性

- ✅ 自动检测和配置CAN接口
- ✅ 支持CAN设备热插拔
- ✅ 自动配置CAN比特率和接口名称
- ✅ 系统服务集成
- ✅ 配置文件管理
- ✅ 完整的日志记录
- ✅ 简单的管理命令
- ✅ 轻量级，无需复杂依赖

## 📋 文件列表

- `piper_service.py` - 主服务脚本
- `install_service.sh` - 安装脚本
- `uninstall_service.sh` - 卸载脚本
- `test_can.sh` - CAN测试脚本

## 🚀 快速安装

```bash
# 1. 测试CAN设备 (可选)
sudo bash test_can.sh

# 2. 安装服务
sudo bash install_service.sh

# 3. 启动服务
piper-service start
```

## 📱 服务管理

```bash
piper-service start     # 启动服务
piper-service stop      # 停止服务
piper-service restart   # 重启服务
piper-service status    # 查看状态
piper-service logs      # 查看实时日志
piper-service config    # 编辑配置文件
piper-service info      # 显示详细信息
```

## ⚙️ 配置说明

配置文件位置: `/etc/piper_service.conf`

```json
{
  "can_name": "can0",        // CAN接口名称
  "bitrate": 1000000,        // CAN比特率
  "check_interval": 5,       // 检查间隔(秒)
  "usb_address": null,       // USB地址(多设备时指定)
  "log_level": "INFO"        // 日志级别
}
```

## 🔧 工作原理

1. **系统启动时**：
   - 检查系统依赖（ethtool, can-utils）
   - 扫描所有CAN接口
   - 自动配置第一个可用的CAN接口

2. **运行时监控**：
   - 每5秒检查一次CAN接口状态
   - 检测到新插入的CAN设备时自动配置
   - 检测到设备移除时自动重连其他可用设备

3. **CAN接口管理**：
   - 自动配置CAN接口比特率
   - 测试CAN连接可用性
   - 支持多设备环境管理

## 📝 日志查看

```bash
# 实时日志
piper-service logs

# 系统日志
journalctl -u piper-service

# 服务日志文件
tail -f /var/log/piper_service.log
```

## 🗑️ 卸载服务

```bash
sudo bash uninstall_service.sh
```

## 🔧 故障排除

### 1. 服务启动失败

```bash
# 查看详细错误信息
piper-service status
piper-service logs
```

### 2. CAN接口未检测到

```bash
# 手动查看CAN接口
ip link show type can

# 检查USB设备
lsusb

# 查看服务详细信息
piper-service info
```

### 3. CAN通信问题

- 检查CAN接口配置是否正确
- 检查CAN连接线是否正常
- 检查机械臂电源和连接线

### 4. 多个CAN设备冲突

在配置文件中指定具体的USB地址：

```json
{
  "usb_address": "1-2:1.0"
}
```

获取USB地址：
```bash
# 查看所有CAN接口的USB地址
bash find_all_can_port.sh
```

## ⚡ 高级配置

### 指定特定USB端口

如果有多个CAN设备，可以通过USB地址指定使用哪个：

```json
{
  "usb_address": "1-2:1.0"
}
```

### 自定义检查频率

```json
{
  "check_interval": 2  // 每2秒检查一次
}
```

## 📦 依赖说明

- **系统依赖**: ethtool, can-utils
- **Python依赖**: python-can
- **权限**: 需要root权限访问CAN设备

## 📁 安装后的文件结构

```text
/opt/piper_service/
├── piper_service.py         # 主服务脚本
/etc/
├── piper_service.conf       # 配置文件
└── systemd/system/
    └── piper-service.service # systemd服务文件
/usr/local/bin/
└── piper-service           # 管理命令
/var/log/
└── piper_service.log       # 日志文件
```
