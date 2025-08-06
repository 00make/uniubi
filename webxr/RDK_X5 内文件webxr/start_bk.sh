#!/bin/bash

# 定义要关闭的端口列表
ports=[5000 12345 12346]

# 杀死占用指定端口的进程
for port in "${ports[@]}"; do
  echo "检查端口 ${port} 的进程..."
  # 使用lsof查找占用端口的PID
  pids=$(lsof -ti :$port)
  if [ -n "$pids" ]; then
    echo "正在杀死端口 ${port} 的进程 (PIDs: ${pids})"
    kill -9 $pids
  else
    echo "端口 ${port} 无活动进程"
  fi
done

# 等待1秒确保进程完全终止
sleep 1

# 按顺序启动后台进程
echo "启动应用程序..."
nohup /root/miniconda3/envs/lerobot/bin/python app.py > app.log 2>&1 &
echo "app.py 已启动 (PID: $!)"

nohup /root/miniconda3/envs/lerobot/bin/python arm_controller_joystick.py > arm.log 2>&1 &
echo "arm_controller_joystick.py 已启动 (PID: $!)"

nohup /root/miniconda3/envs/lerobot/bin/python dog_controller_joystick.py > dog.log 2>&1 &
echo "dog_controller_joystick.py 已启动 (PID: $!)"

nohup /root/miniconda3/envs/lerobot/bin/python dog_controller_hand.py > hand.log 2>&1 &
echo "dog_controller_hand.py 已启动 (PID: $!)"

echo "所有程序已启动!"