#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""컨베이어 벨트 엔코더 속도 퍼블리셔 (ROS 2).

ESP32 엔코더 리더가 시리얼로 송출하는 ``timestamp_ms,total_count`` CSV
프레임을 받아 컨베이어 벨트 속도(m/s)와 누적 이동 거리(mm)를 토픽으로
발행한다. 동시에 pc/receiver.py와 동일한 실시간 TUI를 화면에 출력한다.

토픽:
    /conveyor/speed        (std_msgs/Float64)  벨트 속도 [m/s], EMA 스무딩
    /conveyor/distance_mm  (std_msgs/Float64)  누적 이동거리 [mm]

파라미터:
    port             (str,   기본 '')     시리얼 포트. 빈 문자열이면 자동 감지
    baud             (int,   기본 115200)
    diameter         (float, 기본 80.0)   롤러 직경 mm
    ema_alpha        (float, 기본 0.1)    EMA 스무딩 계수
    deadband         (float, 기본 0.002)  속도 데드밴드 m/s
    publish_hz       (float, 기본 20.0)   토픽 발행 주기 Hz
    show_display     (bool,  기본 True)   TUI 표시 여부
    display_interval (float, 기본 0.5)    TUI 갱신 주기 초
"""

from __future__ import annotations

import math
import sys
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64

try:
    import serial
    import serial.tools.list_ports
except ImportError as e:
    raise ImportError(
        "pyserial 패키지가 필요합니다. `sudo apt install python3-serial` 또는 "
        "`pip install pyserial`로 설치하세요."
    ) from e


# 엔코더 상수 (Autonics E50S8-5000-3-N-24)
PPR = 5000
QUAD_MULT = 4
CPR = PPR * QUAD_MULT  # 20000


def _find_esp32_port() -> str | None:
    """USB-UART 변환기 키워드로 ESP32 포트 자동 감지."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        if any(k in desc for k in ["cp210", "ch340", "usb serial", "silicon labs"]):
            return p.device
    if ports:
        return ports[0].device
    return None


class ConveyorEncoderNode(Node):
    """ESP32 시리얼 → 컨베이어 속도/거리 퍼블리셔 (+ receiver.py 스타일 TUI)."""

    def __init__(self) -> None:
        super().__init__("conveyor_encoder_node")

        # 파라미터 선언 + 읽기
        self.declare_parameter("port", "")
        self.declare_parameter("baud", 115200)
        self.declare_parameter("diameter", 80.0)
        self.declare_parameter("ema_alpha", 0.1)
        self.declare_parameter("deadband", 0.002)
        self.declare_parameter("publish_hz", 20.0)
        self.declare_parameter("show_display", True)
        self.declare_parameter("display_interval", 0.5)

        port_param = self.get_parameter("port").get_parameter_value().string_value
        self.baud = self.get_parameter("baud").get_parameter_value().integer_value
        self.diameter = self.get_parameter("diameter").get_parameter_value().double_value
        self.ema_alpha = self.get_parameter("ema_alpha").get_parameter_value().double_value
        self.deadband = self.get_parameter("deadband").get_parameter_value().double_value
        publish_hz = self.get_parameter("publish_hz").get_parameter_value().double_value
        self.publish_interval = 1.0 / publish_hz if publish_hz > 0 else 0.05
        self.show_display = self.get_parameter("show_display").get_parameter_value().bool_value
        self.display_interval = (
            self.get_parameter("display_interval").get_parameter_value().double_value
        )

        if port_param:
            self.port = port_param
        else:
            self.port = _find_esp32_port()
            if self.port is None:
                self.get_logger().fatal(
                    "ESP32 포트를 찾을 수 없습니다. `port` 파라미터를 지정하세요."
                )
                raise RuntimeError("ESP32 port not found")
            self.get_logger().info(f"자동 감지된 포트: {self.port}")

        self.mm_per_pulse = math.pi * self.diameter / CPR

        self.speed_pub = self.create_publisher(Float64, "/conveyor/speed", 1)
        self.distance_pub = self.create_publisher(Float64, "/conveyor/distance_mm", 1)

        self._prev_t: float | None = None
        self._prev_dist: float | None = None
        self._speed_ema = 0.0
        self._last_publish = 0.0
        self._last_display = 0.0
        self._speed_min = float("inf")
        self._speed_max = float("-inf")

        self.get_logger().info(
            f"Conveyor encoder node started — port: {self.port}, "
            f"diameter: {self.diameter:.1f}mm, CPR: {CPR}"
        )

    # ------------------------------------------------------------------
    # Serial read loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """시리얼 루프 — 이 함수가 리턴하면 노드 종료."""
        try:
            ser = serial.Serial(self.port, self.baud, timeout=1)
        except serial.SerialException as e:
            self.get_logger().error(f"시리얼 포트 열기 실패: {e}")
            return

        time.sleep(2.0)  # ESP32 부트 대기
        ser.reset_input_buffer()
        self.get_logger().info("시리얼 연결 완료, 수신 시작")

        header = self._build_header()
        if self.show_display:
            # 스크롤 방지: 화면 클리어 + 커서 홈
            sys.stdout.write("\033[2J\033[H" + header)
            sys.stdout.flush()

        t_sec = 0.0
        total_count = 0
        distance_mm = 0.0

        try:
            while rclpy.ok():
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

                if self._prev_t is not None:
                    dt = t_sec - self._prev_t
                    dd = distance_mm - self._prev_dist
                    if dt > 0:
                        instant_speed = dd / dt / 1000.0  # mm/s → m/s
                        self._speed_ema = (
                            self.ema_alpha * instant_speed
                            + (1.0 - self.ema_alpha) * self._speed_ema
                        )
                        if abs(self._speed_ema) < self.deadband:
                            self._speed_ema = 0.0

                self._prev_t = t_sec
                self._prev_dist = distance_mm

                now = time.time()

                # Topic publish
                if now - self._last_publish >= self.publish_interval:
                    self._last_publish = now
                    speed_msg = Float64()
                    speed_msg.data = self._speed_ema
                    self.speed_pub.publish(speed_msg)

                    dist_msg = Float64()
                    dist_msg.data = distance_mm
                    self.distance_pub.publish(dist_msg)

                # TUI update
                if self.show_display and now - self._last_display >= self.display_interval:
                    self._last_display = now
                    self._speed_min = min(self._speed_min, self._speed_ema)
                    self._speed_max = max(self._speed_max, self._speed_ema)
                    self._render_tui(header, t_sec, total_count, distance_mm)

        except serial.SerialException as e:
            self.get_logger().error(f"시리얼 에러: {e}")
        finally:
            if self.show_display:
                sys.stdout.write("\033[J\n")
                sys.stdout.flush()
            if ser.is_open:
                ser.close()
                self.get_logger().info("시리얼 포트 닫힘")

    # ------------------------------------------------------------------
    # TUI rendering (identical layout to pc/receiver.py)
    # ------------------------------------------------------------------

    def _build_header(self) -> str:
        return (
            f"\033[1m ESP32 Encoder Receiver (ROS 2)\033[0m\n"
            f" 포트: {self.port}  |  롤러 직경: {self.diameter}mm  |  "
            f"분해능: {CPR} CPR  |  펄스당: {self.mm_per_pulse:.4f}mm\n"
            f"{'─' * 52}\n"
        )

    def _render_tui(
        self, header: str, t_sec: float, total_count: int, distance_mm: float
    ) -> None:
        speed_ms = self._speed_ema
        if speed_ms > 0.0001:
            direction = ">>>"
        elif speed_ms < -0.0001:
            direction = "<<<"
        else:
            direction = "---"

        if self._speed_min == float("inf"):
            min_str = "       N/A"
            max_str = "       N/A"
        else:
            min_str = f"{self._speed_min:>10.4f}"
            max_str = f"{self._speed_max:>10.4f}"

        sys.stdout.write("\033[H")  # cursor home
        sys.stdout.write(header)
        sys.stdout.write(
            f"  시간      {t_sec:>10.2f} s\n"
            f"  펄스      {total_count:>10d}\n"
            f"  거리      {distance_mm:>10.2f} mm\n"
            f"{'─' * 52}\n"
            f"  속도      {speed_ms:>10.4f} m/s  {direction}\n"
            f"  최소      {min_str} m/s\n"
            f"  최대      {max_str} m/s\n"
            f"{'─' * 52}\n"
            f"  \033[2mCtrl+C 로 종료 (토픽은 계속 발행 중)\033[0m\033[J"
        )
        sys.stdout.flush()


def main(args: list | None = None) -> None:
    rclpy.init(args=args)
    try:
        node = ConveyorEncoderNode()
    except RuntimeError:
        rclpy.shutdown()
        return

    # 구독/서비스/타이머가 없는 순수 퍼블리셔라 별도 spin 없이 시리얼 루프만 돌린다.
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
