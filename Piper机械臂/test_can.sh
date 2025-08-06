#!/bin/bash

# CAN设备快速测试脚本

echo "=== Piper CAN设备测试工具 ==="

# 检查系统依赖
echo "1. 检查系统依赖..."
missing_deps=()

if ! command -v ip &> /dev/null; then
    missing_deps+=("iproute2")
fi

if ! command -v ethtool &> /dev/null; then
    missing_deps+=("ethtool")
fi

if ! command -v cansend &> /dev/null; then
    missing_deps+=("can-utils")
fi

if [ ${#missing_deps[@]} -ne 0 ]; then
    echo "错误: 缺少依赖包: ${missing_deps[*]}"
    echo "请运行: sudo apt update && sudo apt install ${missing_deps[*]}"
    exit 1
fi

echo "✓ 系统依赖检查通过"

# 查找CAN接口
echo ""
echo "2. 查找CAN接口..."
can_interfaces=$(ip -br link show type can | awk '{print $1}')

if [ -z "$can_interfaces" ]; then
    echo "❌ 未找到CAN接口"
    echo "请检查:"
    echo "  - USB转CAN设备是否已连接"
    echo "  - 设备驱动是否正确安装"
    echo "  - 运行 'lsusb' 查看USB设备"
    exit 1
fi

echo "✓ 找到CAN接口:"
for iface in $can_interfaces; do
    usb_info=""
    if command -v ethtool &> /dev/null; then
        usb_info=$(sudo ethtool -i "$iface" 2>/dev/null | grep "bus-info" | awk '{print $2}')
    fi
    echo "  - $iface (USB: $usb_info)"
done

# 选择CAN接口
if [ $(echo "$can_interfaces" | wc -w) -eq 1 ]; then
    selected_iface=$can_interfaces
    echo "✓ 自动选择接口: $selected_iface"
else
    echo ""
    echo "检测到多个CAN接口，请选择:"
    select selected_iface in $can_interfaces; do
        if [ -n "$selected_iface" ]; then
            break
        fi
    done
fi

echo ""
echo "3. 配置CAN接口..."

# 配置CAN接口
bitrate=1000000
echo "配置 $selected_iface (bitrate: $bitrate)..."

# 停止接口
sudo ip link set "$selected_iface" down 2>/dev/null

# 设置比特率
if sudo ip link set "$selected_iface" type can bitrate $bitrate; then
    echo "✓ 比特率设置成功"
else
    echo "❌ 比特率设置失败"
    exit 1
fi

# 启动接口
if sudo ip link set "$selected_iface" up; then
    echo "✓ 接口启动成功"
else
    echo "❌ 接口启动失败"
    exit 1
fi

echo ""
echo "4. 测试CAN通信..."

# 测试CAN发送
echo "发送测试消息..."
if timeout 5 cansend "$selected_iface" "123#DEADBEEF" 2>/dev/null; then
    echo "✓ CAN发送测试成功"
else
    echo "⚠ CAN发送测试失败 (这可能是正常的，如果没有接收设备)"
fi

# 显示CAN接口状态
echo ""
echo "5. CAN接口状态:"
echo "----------------------------------------"
ip -details link show "$selected_iface"

echo ""
echo "6. 监听CAN消息 (按Ctrl+C停止):"
echo "----------------------------------------"
echo "正在监听 $selected_iface ..."
echo "如果连接了Piper机械臂，您应该能看到CAN消息"
echo ""

# 启动CAN监听
timeout 10 candump "$selected_iface" 2>/dev/null || echo "10秒内未检测到CAN消息"

echo ""
echo "=== 测试完成 ==="
echo ""
echo "如果看到CAN消息，说明连接正常。"
echo "如果没有消息，请检查:"
echo "  - 机械臂是否已通电"
echo "  - CAN连接线是否正确"
echo "  - 机械臂CAN_H和CAN_L是否接对"
echo ""
echo "接下来可以运行服务安装脚本:"
echo "  sudo bash install_service.sh"
