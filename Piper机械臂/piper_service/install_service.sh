#!/bin/bash

# Piper机械臂CAN服务安装脚本

set -e

echo "=== Piper机械臂CAN服务安装脚本 ==="

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "错误: 请使用root权限运行此脚本"
    echo "使用方法: sudo bash install_service.sh"
    exit 1
fi

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="/opt/piper_service"
CONFIG_FILE="/etc/piper_service.conf"
SERVICE_FILE="/etc/systemd/system/piper-service.service"

SERVICE_SCRIPT="piper_service.py"
SERVICE_DESC="Piper CAN自动连接服务"

echo "安装 $SERVICE_DESC..."

echo "1. 检查系统依赖..."

# 检查并安装系统依赖
if ! dpkg -l | grep -q "ethtool"; then
    echo "安装 ethtool..."
    apt update && apt install -y ethtool
fi

if ! dpkg -l | grep -q "can-utils"; then
    echo "安装 can-utils..."
    apt update && apt install -y can-utils
fi

echo "2. 检查Python依赖..."

# 检查Python和pip
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "安装 pip3..."
    apt install -y python3-pip
fi

# 安装Python依赖
echo "安装Python依赖包..."
pip3 install python-can

echo "3. 创建服务目录..."

# 创建服务目录
mkdir -p "$SERVICE_DIR"

# 复制服务文件
echo "复制服务文件..."
if [ ! -f "$SCRIPT_DIR/$SERVICE_SCRIPT" ]; then
    echo "错误: 未找到服务脚本 $SERVICE_SCRIPT"
    exit 1
fi

cp "$SCRIPT_DIR/$SERVICE_SCRIPT" "$SERVICE_DIR/"
chmod +x "$SERVICE_DIR/$SERVICE_SCRIPT"

# 创建配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo "创建配置文件..."
    cat > "$CONFIG_FILE" << 'EOF'
{
  "can_name": "can0",
  "bitrate": 1000000,
  "check_interval": 5,
  "usb_address": null,
  "log_level": "INFO"
}
EOF
    echo "配置文件已创建: $CONFIG_FILE"
else
    echo "配置文件已存在: $CONFIG_FILE"
fi

# 创建systemd服务文件
echo "创建systemd服务文件..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=$SERVICE_DESC
Documentation=https://github.com/your-repo/piper-service
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$SERVICE_DIR
ExecStart=/usr/bin/python3 $SERVICE_DIR/$SERVICE_SCRIPT --config $CONFIG_FILE
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=piper-service

# 环境变量
Environment=PYTHONPATH=/usr/local/lib/python3.8/site-packages

[Install]
WantedBy=multi-user.target
EOF

echo "4. 配置系统服务..."

# 重新加载systemd
systemctl daemon-reload

# 启用服务
systemctl enable piper-service

echo "5. 创建管理脚本..."

# 创建管理脚本
cat > /usr/local/bin/piper-service << 'EOF'
#!/bin/bash

case "$1" in
    start)
        echo "启动Piper服务..."
        systemctl start piper-service
        ;;
    stop)
        echo "停止Piper服务..."
        systemctl stop piper-service
        ;;
    restart)
        echo "重启Piper服务..."
        systemctl restart piper-service
        ;;
    status)
        systemctl status piper-service
        ;;
    logs)
        journalctl -u piper-service -f
        ;;
    config)
        nano /etc/piper_service.conf
        ;;
    info)
        python3 /opt/piper_service/piper_service.py --status 2>/dev/null || echo "服务脚本未找到"
        ;;
    *)
        echo "Piper机械臂服务管理工具"
        echo "用法: $0 {start|stop|restart|status|logs|config|info}"
        echo ""
        echo "命令说明:"
        echo "  start   - 启动服务"
        echo "  stop    - 停止服务"
        echo "  restart - 重启服务"
        echo "  status  - 查看服务状态"
        echo "  logs    - 查看实时日志"
        echo "  config  - 编辑配置文件"
        echo "  info    - 显示详细信息"
        exit 1
        ;;
esac
EOF

chmod +x /usr/local/bin/piper-service

echo "6. 配置CAN权限..."

# 创建udev规则以允许普通用户访问CAN设备
cat > /etc/udev/rules.d/99-piper-can.rules << 'EOF'
# Piper CAN设备权限规则
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="gs_usb", MODE="0666"
KERNEL=="can*", MODE="0666"
EOF

# 重新加载udev规则
udevadm control --reload-rules

echo ""
echo "=== 安装完成 ==="
echo ""
echo "已安装: $SERVICE_DESC"
echo "服务脚本: $SERVICE_DIR/$SERVICE_SCRIPT"
echo ""
echo "配置文件位置: $CONFIG_FILE"
echo "日志文件位置: /var/log/piper_service.log"
echo ""
echo "管理命令:"
echo "  piper-service start    # 启动服务"
echo "  piper-service stop     # 停止服务"
echo "  piper-service status   # 查看状态"
echo "  piper-service logs     # 查看日志"
echo "  piper-service config   # 编辑配置"
echo "  piper-service info     # 显示详细信息"
echo ""

# 询问是否立即启动
read -p "是否现在启动服务？(y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "启动服务..."
    systemctl start piper-service
    sleep 3
    echo ""
    echo "服务状态:"
    systemctl status piper-service --no-pager
    echo ""
    echo "实时日志 (按Ctrl+C退出):"
    echo "----------------------------------------"
    journalctl -u piper-service -f --since "1 minute ago"
fi

echo ""
echo "安装完成！"
