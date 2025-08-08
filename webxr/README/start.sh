#!/bin/bash

# ==============================================================================
# 脚本配置
# ==============================================================================

# Python 环境的路径
PYTHON_EXECUTABLE="/root/miniconda3/envs/lerobot/bin/python"

# 应用程序脚本和它们对应的端口及日志文件
# 格式: "脚本名称 日志文件路径 端口号"
# 这里的端口号主要用于启动前的清理工作。
declare -a SCRIPTS=(
  "app.py app.log 5000"
  "arm_controller_joystick.py arm.log 12345"
  "dog_controller_joystick.py dog.log 12346"
)


# ==============================================================================
# 1. 杀死占用已知端口的旧进程
# ==============================================================================
echo "### 步骤 1: 清理旧进程 ###"

# 从 SCRIPTS 数组中提取所有唯一的、非零的端口号
ports_to_kill=$(for script_info in "${SCRIPTS[@]}"; do set -- $script_info; echo "$3"; done | grep -v '^0$' | sort -u)

echo "将要检查并关闭以下端口的进程: ${ports_to_kill[*]}"

for port in $ports_to_kill; do
  echo "正在检查端口 ${port}..."
  # 使用 lsof 查找占用指定 TCP 端口的进程 PID
  pids=$(lsof -t -i TCP:${port} -s TCP:LISTEN)

  if [ -n "$pids" ]; then
    # 强制杀死找到的进程
    echo "发现进程 (PIDs: ${pids}) 正在监听端口 ${port}。正在终止..."
    # xargs 确保在有多个 PID 时也能正常工作
    echo "$pids" | xargs kill -9
    echo "端口 ${port} 的进程已被终止。"
  else
    echo "端口 ${port} 当前无活动监听进程。"
  fi
done

# 短暂等待，确保操作系统已完全释放端口
sleep 3

# ==============================================================================
# 2. 按顺序启动所有应用程序脚本
# ==============================================================================
echo -e "\n### 步骤 2: 顺序启动应用程序 ###"

for script_info in "${SCRIPTS[@]}"; do
  # shellcheck disable=SC2086
  set -- $script_info # 分割 "script.py log.txt 1234"
  script_name="$1"
  log_file="$2"
  # port="$3" # 端口号在此步骤中不再用于等待

  echo "--------------------------------------------------"
  echo "准备启动: ${script_name}"

  # 检查脚本文件是否存在
  if [ ! -f "$script_name" ]; then
    echo "错误: 脚本文件 '${script_name}' 不存在。跳过此脚本。"
    continue
  fi

  # 在后台使用 nohup 启动脚本，并将输出重定向到日志文件
  nohup "$PYTHON_EXECUTABLE" "$script_name" > "$log_file" 2>&1 &
  pid=$!
  echo "${script_name} 已启动，进程 PID: ${pid}，日志文件: ${log_file}"

  # 替换原来的端口检查逻辑，统一等待5秒
  echo "等待 5 秒，让 ${script_name} 完成初始化..."
  sleep 5
  echo "初始化等待结束，继续下一个脚本。"

done

echo "--------------------------------------------------"
echo -e "\n### 所有脚本均已启动完毕 ###"
