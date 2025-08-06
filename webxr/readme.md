
## 安装 miniconda

```bash
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm ~/miniconda3/miniconda.sh
echo 'export PATH=~/miniconda3/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

## 安装 lerobot-kinematics

```bash
  # if no lerobot conda env
  conda create -y -n lerobot python=3.10
  conda activate lerobot
  git clone https://github.com/box2ai-robotics/lerobot-kinematics.git
  cd lerobot-kinematics
  pip install -e .
```

## 安装 webxr

```bash
  git clone
  cd webxr
  pip install -r requirements.txt
```

## 运行 webxr

```bash
/root/miniconda3/envs/lerobot/bin/python /root/webxr/app.py
```

## 访问 webxr

```bash
  # 在浏览器中打开 http://localhost:888
```

## 运行机器狗控制

```bash
python dog_controller_hand.py 
/root/miniconda3/envs/lerobot/bin/python /root/webxr/dog_controller_joystick.py
```

## 运行机械臂控制

记得修改串口号

```bash
/root/miniconda3/envs/lerobot/bin/python /root/webxr/lerobot_keycon_gpos_real.py
```

## X5主板创建热点

```shell
sudo apt install network-manager 
sudo apt install dnsmasq 
sudo apt install haveged
```

```shell
git clone https://github.com/oblique/create_ap.git
cd create_ap
sudo make install
```

```shell
sudo update-alternatives --config iptables
选择iptables-legacy
```

```shell
create_ap wlan0 wlan0 X5
```

### 将create_ap加入到开机启动项中

1. **创建 Systemd 服务单元文件:**
你需要创建一个服务单元文件，告诉 systemd 如何启动、停止和管理 `create_ap` 脚本。  通常，这个文件应该放在 `/etc/systemd/system/` 目录下。
使用文本编辑器（例如 `nano`, `vim`）创建文件 `create_ap.service`：

```bash
sudo nano /etc/systemd/system/create_ap.service
```

在文件中粘贴以下内容，并根据你的实际情况进行修改：

```ini
[Unit]
Description=Create AP Hotspot Service
After=network.target 
Wants=network-online.target  
[Service]
Type=simple
WorkingDirectory=/root/webxr/create_ap 
ExecStart=/usr/bin/create_ap wlan0 wlan0 X5
Restart=on-failure  
RestartSec=5 
User=root  
[Install]
WantedBy=multi-user.target 
```

**重要参数解释和修改：**

* **`WorkingDirectory=/path/to/create_ap/directory`**:  **你需要将 `/path/to/create_ap/directory` 替换为 `create_ap` 脚本实际存放的目录。**  例如，如果你是通过 `git clone` 下载的，并且没有移动目录，可能是 `~/create_ap` 或你下载到的其他路径。  你可以使用 `pwd` 命令在 `create_ap` 目录下查看当前路径。
* **`ExecStart=/path/to/create_ap/create_ap <interface_for_upstream> <interface_for_ap> <ssid> <password>`**: **这是最关键的一行，你需要进行以下替换：**
* **`/path/to/create_ap/create_ap`**:  **替换为 `create_ap` 脚本的完整路径。**  你可以使用 `which create_ap` 命令查找 `create_ap` 的完整路径。例如，如果 `which create_ap` 输出 `/usr/local/bin/create_ap`，则替换为 `/usr/local/bin/create_ap`。
* **`<interface_for_upstream>`**:  替换为你用来连接上游网络的无线网卡接口名称。例如 `wlan1`。  **请根据你的实际情况替换。**
* **`<interface_for_ap>`**: 替换为你用来创建热点的无线网卡接口名称。 例如 `wlan0`。 **请根据你的实际情况替换。**
**示例 `ExecStart` 行 (假设 `create_ap` 在 `/usr/local/bin/`，上游接口 `wlan1`，热点接口 `wlan0`，SSID `MyHotspot`，密码 `MyPassword`)**:

```ini
ExecStart=/usr/local/bin/create_ap wlan1 wlan0 MyHotspot MyPassword
```

2. **保存并退出编辑器:**  在 `nano` 中，按 `Ctrl+X`，然后按 `Y` 保存，最后按 `Enter` 退出。
3. **启用 Systemd 服务:**
你需要让 systemd 知道你创建了新的服务，并启用它在开机时启动。

```bash
sudo systemctl daemon-reload  # 重新加载 systemd 配置
sudo systemctl enable create_ap.service # 启用开机自启动
```

4. **启动 Systemd 服务 (可选，用于测试):**

```bash
sudo systemctl start create_ap.service
```

5. **检查服务状态 (可选，用于调试):**

```bash
sudo systemctl status create_ap.service
```

如果服务启动失败，可以查看详细日志：

```bash
journalctl -u create_ap.service
```

6. **重启电脑测试:**
重启你的电脑，检查 `create_ap` 创建的无线热点是否在启动后自动运行。
7. **停止和禁用 Systemd 服务 (如果需要):**

* **停止服务:**

  ```bash
  sudo systemctl stop create_ap.service
  ```

* **禁用开机自启动:**

  ```bash
  sudo systemctl disable create_ap.service
  ```

  ## X5通过SSH连接WiFi(建议x5连接机器狗，机器狗连接手机热点)

  扫描可用的WiFi网络：

  ```bash
  sudo iwlist scan
  ```

  或使用NetworkManager列出WiFi网络：

  ```bash
  nmcli device wifi list
  ```

  连接到指定的WiFi网络：

  ```bash
  sudo nmcli device wifi connect BabyAlpha_52_a6_b6 password 12345678

  sudo nmcli device wifi connect iPhone password 88888888
  ```

  **注意事项：**
  * 将 `iPhone` 替换为你要连接的WiFi网络名称（SSID）
  * 将 `88888888` 替换为对应的WiFi密码
  * 确保WiFi网络在扫描范围内且信号良好
