#include "sdk/lowlevel.h"
#include <iostream>
#include <thread>
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

int main() {
    
    // 注册信号处理函数
    std::signal(SIGINT, signal_handler);

    float init_q_abad[4];
    float init_q_hip[4];
    float init_q_kneep[4];

    float default_abad_pos = 0.0;
    float default_hip_pos = 1.4;
    float default_knee_pos = -2.4;

    bool flag = true;
    int count = 0;

    constexpr int CLIENT_PORT = 43988;   // local port
    std::string CLIENT_IP = "192.168.234.17"; // local IP address
    std::string DOG_IP = "192.168.234.1";    // dog ip

    LowLevel lowlevel;
    motorCmd cmd;
    std::cout << "Initializing..." << std::endl;
    std::this_thread::sleep_for(std::chrono::milliseconds(10000));
    lowlevel.initRobot(CLIENT_IP, CLIENT_PORT, DOG_IP);
    std::cout << "Initialization completed" << std::endl;

    while (!g_exit_requested.load()) {
        auto state = lowlevel.getMotorState();
        if (lowlevel.haveMotorData()) {
            static bool first_triger = false;
            if (!first_triger) {
                first_triger = true;
                for (size_t i = 0; i < 4; i++) {
                    init_q_abad[i] = state->q_abad[i];
                    init_q_hip[i] = state->q_hip[i];
                    init_q_kneep[i] = state->q_knee[i];
                }
            }

            static double stage1_progress = 0.0;
            static double stage2_progress = 0.0;
            static int stage = 0;
            stage1_progress += 0.002;
            double duration = 2.0;
            double ratio = stage1_progress / duration;
            if (ratio > 1.0) {
                ratio = 1.0;
                stage = 1;
            }

            if (stage == 1) {
                default_abad_pos = 0.0;
                default_hip_pos = 0.8;
                default_knee_pos = -1.5;
                stage2_progress += 0.002;
                ratio = stage2_progress / duration;
                if (ratio > 1.0) {
                    ratio = 1.0;
                }

                static bool stage2_start = false;

                if (!stage2_start) {
                    stage2_start = true;
                    for (size_t i = 0; i < 4; i++) {
                        init_q_abad[i] = state->q_abad[i];
                        init_q_hip[i] = state->q_hip[i];
                        init_q_kneep[i] = state->q_knee[i];
                    }
                }
            }

            for (size_t i = 0; i < 4; i++) {
                cmd.q_des_abad[i] =
                    ratio * default_abad_pos + (1.0 - ratio) * init_q_abad[i];
                cmd.q_des_hip[i] =
                    ratio * default_hip_pos + (1.0 - ratio) * init_q_hip[i];
                cmd.q_des_knee[i] =
                    ratio * default_knee_pos + (1.0 - ratio) * init_q_kneep[i];
                cmd.kp_abad[i] = 80;
                cmd.kp_hip[i] = 80;
                cmd.kp_knee[i] = 80;
                cmd.kd_abad[i] = 1;
                cmd.kd_hip[i] = 1;
                cmd.kd_knee[i] = 1;
            }

            int ret = lowlevel.sendMotorCmd(cmd);
            if (ret < 0) {
                std::cout << "send cmd error" << std::endl;
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(2));
    }

    
    // 发送所有关节命令为0的指令
    motorCmd zero_cmd = {};
    for (int i = 0; i < 4; i++) {
        zero_cmd.q_des_abad[i] = 0.0f;
        zero_cmd.q_des_hip[i] = 0.0f;
        zero_cmd.q_des_knee[i] = -1.5f;
        zero_cmd.kp_abad[i] = 0.0f;
        zero_cmd.kp_hip[i] = 0.0f;
        zero_cmd.kp_knee[i] = 0.0f;
        zero_cmd.kd_abad[i] = 3.0f;
        zero_cmd.kd_hip[i] = 3.0f;
        zero_cmd.kd_knee[i] = 3.0f;
    }
    while (flag) {
      lowlevel.sendMotorCmd(zero_cmd);
      if (count++ > 1500){
        flag = false;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(2));

    }
    
    std::cout << "Sent zero command and exiting..." << std::endl;

    return 0;
}