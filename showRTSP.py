import cv2
import time

def connect_rtsp_opencv():
    # RTSP URL
    rtsp_url = "rtsp://192.168.234.1:8554/test"
    
    # 创建VideoCapture对象
    cap = cv2.VideoCapture(rtsp_url)
    
    # 设置缓冲区大小减少延迟
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    if not cap.isOpened():
        print("无法连接到RTSP流")
        return
    
    print("成功连接到RTSP流")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("无法读取帧")
                break
            
            # 显示视频帧
            cv2.imshow('Robot Dog Camera', frame)
            
            # 按'q'退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("用户中断")
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    connect_rtsp_opencv()
