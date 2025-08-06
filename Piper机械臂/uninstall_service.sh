#!/bin/bash

# Piper机械臂服务卸载脚本

set -e

echo "=== Piper机械臂服务卸载脚本 ==="

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "错误: 请使用root权限运行此脚本"
    echo "使用方法: sudo bash uninstall_service.sh"
    exit 1
fi

SERVICE_DIR="/opt/piper_service"
CONFIG_FILE="/etc/piper_service.conf"
SERVICE_FILE="/etc/systemd/system/piper-service.service"
MANAGEMENT_SCRIPT="/usr/local/bin/piper-service"
UDEV_RULES="/etc/udev/rules.d/99-piper-can.rules"

echo "1. 停止并禁用服务..."

# 停止服务
if systemctl is-active --quiet piper-service; then
    echo "停止服务..."
    systemctl stop piper-service
fi

# 禁用服务
if systemctl is-enabled --quiet piper-service; then
    echo "禁用服务..."
    systemctl disable piper-service
fi

echo "2. 删除服务文件..."

# 删除systemd服务文件
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    echo "已删除: $SERVICE_FILE"
fi

# 重新加载systemd
systemctl daemon-reload

echo "3. 删除程序文件..."

# 删除服务目录
if [ -d "$SERVICE_DIR" ]; then
    rm -rf "$SERVICE_DIR"
    echo "已删除: $SERVICE_DIR"
fi

# 删除管理脚本
if [ -f "$MANAGEMENT_SCRIPT" ]; then
    rm -f "$MANAGEMENT_SCRIPT"
    echo "已删除: $MANAGEMENT_SCRIPT"
fi

echo "4. 删除配置文件..."

# 询问是否删除配置文件
read -p "是否删除配置文件 $CONFIG_FILE ? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "$CONFIG_FILE" ]; then
        rm -f "$CONFIG_FILE"
        echo "已删除: $CONFIG_FILE"
    fi
else
    echo "保留配置文件: $CONFIG_FILE"
fi

echo "5. 删除udev规则..."

if [ -f "$UDEV_RULES" ]; then
    rm -f "$UDEV_RULES"
    echo "已删除: $UDEV_RULES"
    # 重新加载udev规则
    udevadm control --reload-rules
fi

echo "6. 清理日志文件..."

# 询问是否删除日志文件
read -p "是否删除日志文件 /var/log/piper_service.log ? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "/var/log/piper_service.log" ]; then
        rm -f "/var/log/piper_service.log"
        echo "已删除: /var/log/piper_service.log"
    fi
else
    echo "保留日志文件: /var/log/piper_service.log"
fi

echo ""
echo "=== 卸载完成 ==="
echo ""
echo "Piper机械臂服务已成功卸载。"
echo ""
echo "注意: 以下依赖包未被删除，如不再需要可手动卸载:"
echo "  - ethtool"
echo "  - can-utils"
echo "  - python3-can"
echo "  - piper_sdk"
echo ""
