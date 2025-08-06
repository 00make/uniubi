#include "sdk/highlevel.h"
#include <fcntl.h>
#include <iostream>
#include <termios.h>
#include <thread>
#include <unistd.h>
#include <csignal>  // 添加信号处理头文件
#include <atomic>   // 添加原子操作支持

using namespace mc_sdk;

// 全局原子标志，用于安全检测Ctrl+C信号
std::atomic<bool> g_exit_requested(false);

// 信号处理函数
void signal_handler(int signal) {
    if (signal == SIGINT) {
        g_exit_requested.store(true);
    }
}
// 设置终端为非阻塞模式
void set_conio_terminal_mode() {
  struct termios new_termios;
  tcgetattr(STDIN_FILENO, &new_termios);
  new_termios.c_lflag &= ~(ICANON | ECHO); // 关闭规范模式和回显
  tcsetattr(STDIN_FILENO, TCSANOW, &new_termios);
}

// 检查是否有输入
int kbhit() {
  struct termios oldt, newt;
  int oldf;
  tcgetattr(STDIN_FILENO, &oldt);
  newt = oldt;
  newt.c_lflag &= ~(ICANON | ECHO);
  tcsetattr(STDIN_FILENO, TCSANOW, &newt);
  oldf = fcntl(STDIN_FILENO, F_GETFL, 0);
  fcntl(STDIN_FILENO, F_SETFL, oldf | O_NONBLOCK);

  int ch = getchar();

  tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
  fcntl(STDIN_FILENO, F_SETFL, oldf);

  if (ch != EOF) {
    ungetc(ch, stdin);
    return 1;
  }

  return 0;
}

int main() {
  // 注册信号处理函数
  std::signal(SIGINT, signal_handler);
  set_conio_terminal_mode(); // 设置终端为非阻塞模式

  constexpr int CLIENT_PORT = 43988;   // local port
  std::string CLIENT_IP = "192.168.30.142"; // local IP address
  std::string DOG_IP = "192.168.30.44";    // dog ip

  HighLevel highlevel;                                   // high level
  std::cout << "Initializing..." << std::endl;
  std::this_thread::sleep_for(std::chrono::milliseconds(10000));
  highlevel.initRobot(CLIENT_IP, CLIENT_PORT, DOG_IP); // 创建连接, DOG_IP 默认 192.168.234.1， 需要修改时需手动传入DOG_IP
  std::cout << "Initialization completed" << std::endl;

  while (!g_exit_requested.load()) {
    int ret;
    // 检测键盘输入
    ret = highlevel.getBatteryPower();
    // std::cout << ret << std::endl;
    if (kbhit()) {
      char ch = getchar(); // 获取按键
      switch (ch) {
      case 'w': // 向前 move(vx, vy, yaw_rate) 以1m/s的速度向前移动，
                // 侧向速度vy为零， 旋转速度yaw_rate为零
        ret = highlevel.move(1.0, 0.0, 0.0);
        break;
      case 's': // 向后 move(vx, vy, yaw_rate) 以-1m/s的速度向后移动，
                // 侧向速度vy为零， 旋转速度yaw_rate为零
        ret = highlevel.move(-1.0, 0.0, 0.0);
        break;
      case 'a': // 向左 move(vx, vy, yaw_rate) 以1m/s的速度向左移动，
                // 前向速度vx为零， 旋转速度yaw_rate为零
        ret = highlevel.move(0.0, 1.0, 0.0);
        break;
      case 'd': // 向右 move(vx, vy, yaw_rate) 以-1m/s的速度向右移动，
                // 前向速度vx为零， 旋转速度yaw_rate为零
        ret = highlevel.move(0.0, -1.0, 0.0);
        break;
      case 'q': // 左转 move(vx, vy, yaw_rate) 以1m/s的速度向左转动，
                // 侧向速度vy为零， 前向速度vx为零
        ret = highlevel.move(0.0, 0.0, 1.0);
        break;
      case 'e': // 右转 move(vx, vy, yaw_rate) 以-1m/s的速度向右转动，
                // 侧向速度vy为零， 前向速度vx为零
        ret = highlevel.move(0.0, 0.0, -1.0);
        break;
      case 'c': // 停止 move(vx, vy, yaw_rate) 前向速度vx为零， 侧向速度vy为零，
                // 前向速度vx为零  停止移动
        ret = highlevel.move(0.0, 0.0, 0.0);
        break;
      case '0': // 切换到失能状态，机器狗软急停
        ret = highlevel.passive();
        break;
      case '1': // 切换到趴下
        std::cout << "get command lieDown" << std::endl;
        ret = highlevel.lieDown();
        ret = highlevel.getBatteryPower();
        std::cout << ret << std::endl;
        std::cout << "lie down success" << std::endl;
        std::this_thread::sleep_for(std::chrono::milliseconds(10000));
        std::cout << "sleep success" << std::endl;
        ret = highlevel.passive();
        std::cout << "passive success" << std::endl;
        break;

      case '2': // 切换到站立
        ret = highlevel.standUp();
        break;

      case '3': // 切换到跳跃
        ret = highlevel.jump();
        break;

      case '4': // 切换到向前跳跃
        ret = highlevel.frontJump();
        break;
      case '6': // 切换到后空翻
        ret = highlevel.backflip();
        break;
      case '7': // 切换到姿态控制
        ret = highlevel.attitudeControl(
            0.0, 0.0, 0.5,
            0.0); // 参数1传入yaw角速度机器狗进行左右转头，
                  // 参数2传入roll角速度机器狗身体左右滚转，
                  // 参数3传入pitch角速度机器狗身体前后转动，
                  // 参数4传入身体高度调节速率，机器狗身体上下移动。参数范围（0
                  // ~1m/s）
        break;
      default:
        continue; // 忽略其他按键
      }
    }

    std::this_thread::sleep_for(std::chrono::milliseconds(2)); // 限制发送频率
  }
  // 发送所有关节命令为0的指令
  highlevel.passive();
  std::this_thread::sleep_for(std::chrono::milliseconds(2000));
  std::cout << "Sent zero command and exiting..." << std::endl;

  return 0;
}
