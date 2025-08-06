#pragma once
#include <memory>
#include <mutex>
#include <string>
namespace mc_sdk {

class HighLevel {
private:
  struct highLevelFunc;
  std::shared_ptr<highLevelFunc> impl_;
  

public:
  HighLevel();
  ~HighLevel();
  void initRobot(const std::string &local_ip, const int local_port, const std::string& dog_ip = "192.168.234.1");
  uint32_t standUp();
  uint32_t lieDown();
  uint32_t passive();
  uint32_t move(const float vx, const float vy, const float yaw_rate);

  uint32_t jump();
  uint32_t frontJump();
  uint32_t backflip();
  uint32_t attitudeControl(const float yaw_vel, const float roll_vel,
                      const float pitch_vel, const float height_vel);

  float getRoll(); // 获取机器人roll角
  float getPitch(); // 获取机器人pitch角
  float getYaw(); // 获取机器人yaw角， 相对机器人开机时刻的头部朝向

  float getBodyAccX(); //获取机身x方向加速度，头部正前方
  float getBodyAccY(); //获取机身y方向加速度，机身左侧
  float getBodyAccZ(); //获取机身z方向加速度，垂直机身向上

  float getBodyGyroX(); //获取绕机身x轴角速度
  float getBodyGyroY(); //获取绕机身y轴角速度
  float getBodyGyroZ(); //获取绕机身z轴角速度

  float getPosWorldX(); //获取机身相对开机时刻原点x轴位置
  float getPosWorldY(); //获取机身相对开机时刻原点y轴位置
  float getPosWorldZ(); //获取机身相对开机时刻原点z轴位置

  float getWorldVelX(); //获取机身相对开机时刻原点x轴速度
  float getWorldVelY(); //获取机身相对开机时刻原点y轴速度
  float getWorldVelZ(); //获取机身相对开机时刻原点z轴速度

  float getBodyVelX(); //获取机身x轴速度
  float getBodyVelY(); //获取机身y轴速度
  float getBodyVelZ(); //获取机身z轴速度

  uint32_t getBatteryPower(); //获取电池电量
};

} // namespace mc_sdk
