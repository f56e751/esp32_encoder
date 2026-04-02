#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
컨베이어 벨트 엔코더 속도 퍼블리셔 (ROS1 / Python 2)

ESP32 엔코더 리더로부터 시리얼 데이터를 받아
컨베이어 벨트 속도(m/s)를 ROS 토픽으로 퍼블리시한다.

토픽:
    /conveyor/speed  (std_msgs/Float64)  - 벨트 속도 [m/s], EMA 스무딩 적용
    /conveyor/distance_mm (std_msgs/Float64) - 누적 이동거리 [mm]

파라미터:
    ~port        (str)   - 시리얼 포트 (기본: 자동감지)
    ~baud        (int)   - 통신 속도 (기본: 115200)
    ~diameter    (float) - 롤러 직경 mm (기본: 100.0)
    ~ema_alpha   (float) - EMA 스무딩 계수 (기본: 0.1)
    ~deadband    (float) - 속도 데드밴드 m/s (기본: 0.002)
    ~publish_hz  (float) - 토픽 발행 주기 Hz (기본: 20.0)
"""

import math
import time
import rospy
from std_msgs.msg import Float64

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    rospy.logfatal("pyserial 패키지가 필요합니다: pip install pyserial")
    raise

# 엔코더 상수
PPR = 5000
QUAD_MULT = 4
CPR = PPR * QUAD_MULT  # 20000


def find_esp32_port():
    """ESP32 시리얼 포트 자동 감지"""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        if any(k in desc for k in ["cp210", "ch340", "usb serial", "silicon labs"]):
            return p.device
    if ports:
        return ports[0].device
    return None


class ConveyorEncoderNode(object):
    def __init__(self):
        rospy.init_node("conveyor_encoder_node")

        # 파라미터
        port_param = rospy.get_param("~port", "")
        self.baud = rospy.get_param("~baud", 115200)
        self.diameter = rospy.get_param("~diameter", 100.0)
        self.ema_alpha = rospy.get_param("~ema_alpha", 0.1)
        self.deadband = rospy.get_param("~deadband", 0.002)
        self.publish_interval = 1.0 / rospy.get_param("~publish_hz", 20.0)

        # 포트 결정
        if port_param:
            self.port = port_param
        else:
            self.port = find_esp32_port()
            if self.port is None:
                rospy.logfatal("ESP32 포트를 찾을 수 없습니다. ~port 파라미터를 지정하세요.")
                raise RuntimeError("ESP32 port not found")
            rospy.loginfo("자동 감지된 포트: %s", self.port)

        self.mm_per_pulse = math.pi * self.diameter / CPR

        # 퍼블리셔
        self.speed_pub = rospy.Publisher("/conveyor/speed", Float64, queue_size=1)
        self.distance_pub = rospy.Publisher("/conveyor/distance_mm", Float64, queue_size=1)

        # 상태
        self.prev_t = None
        self.prev_dist = None
        self.speed_ema = 0.0
        self.last_publish = 0.0

        rospy.loginfo(
            "컨베이어 엔코더 노드 시작 - 포트: %s, 롤러직경: %.1fmm, CPR: %d",
            self.port, self.diameter, CPR,
        )

    def run(self):
        ser = None
        try:
            ser = serial.Serial(self.port, self.baud, timeout=1)
            rospy.sleep(2.0)  # ESP32 리셋 대기
            ser.reset_input_buffer()
            rospy.loginfo("시리얼 연결 완료, 데이터 수신 시작")

            while not rospy.is_shutdown():
                raw_line = ser.readline()
                if not raw_line:
                    continue

                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line or line.startswith("#") or line.startswith("ENCODER"):
                    continue

                parts = line.split(",")
                if len(parts) != 2:
                    continue

                try:
                    esp_time_ms = int(parts[0])
                    total_count = int(parts[1])
                except ValueError:
                    continue

                t_sec = esp_time_ms / 1000.0
                distance_mm = total_count * self.mm_per_pulse

                # 속도 계산 (EMA 스무딩)
                if self.prev_t is not None:
                    dt = t_sec - self.prev_t
                    dd = distance_mm - self.prev_dist
                    if dt > 0:
                        instant_speed = dd / dt / 1000.0  # mm/s -> m/s
                        self.speed_ema = (
                            self.ema_alpha * instant_speed
                            + (1 - self.ema_alpha) * self.speed_ema
                        )
                        if abs(self.speed_ema) < self.deadband:
                            self.speed_ema = 0.0

                self.prev_t = t_sec
                self.prev_dist = distance_mm

                # 발행 주기 제어
                now = time.time()
                if now - self.last_publish < self.publish_interval:
                    continue
                self.last_publish = now

                # 퍼블리시
                self.speed_pub.publish(Float64(data=self.speed_ema))
                self.distance_pub.publish(Float64(data=distance_mm))

        except serial.SerialException as e:
            rospy.logerr("시리얼 에러: %s", str(e))
        finally:
            if ser and ser.is_open:
                ser.close()
                rospy.loginfo("시리얼 포트 닫힘")


if __name__ == "__main__":
    try:
        node = ConveyorEncoderNode()
        node.run()
    except rospy.ROSInterruptException:
        pass
