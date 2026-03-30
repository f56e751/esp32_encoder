"""
ESP32 엔코더 시리얼 수신기
컨베이어 벨트 속도/거리 계산

사용법:
    python receiver.py                    # 기본 COM 포트 자동 감지
    python receiver.py --port COM3        # 포트 지정
    python receiver.py --diameter 100     # 롤러 직경 지정 (mm)
"""

import argparse
import sys
import time
from collections import deque

import serial
import serial.tools.list_ports

# ─── 엔코더 / 롤러 상수 ───
PPR = 5000          # 엔코더 펄스/회전 (Pulse Per Revolution)
QUAD_MULT = 4       # 4체배 디코딩
CPR = PPR * QUAD_MULT  # 20000 카운트/회전

# 속도 계산용 이동평균 윈도우
SPEED_WINDOW = 5


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


def pulse_to_mm(pulses, roller_diameter_mm):
    """펄스 수 → 이동 거리 (mm)"""
    circumference = 3.141592653589793 * roller_diameter_mm
    return pulses * circumference / CPR


def main():
    parser = argparse.ArgumentParser(description="ESP32 엔코더 수신기")
    parser.add_argument("--port", type=str, default=None, help="시리얼 포트 (예: COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="통신 속도")
    parser.add_argument("--diameter", type=float, default=100.0,
                        help="롤러 직경 (mm), 기본값: 100mm")
    args = parser.parse_args()

    port = args.port or find_esp32_port()
    if not port:
        print("ERROR: ESP32 포트를 찾을 수 없습니다. --port 옵션으로 지정해주세요.")
        sys.exit(1)

    roller_diam = args.diameter
    mm_per_pulse = 3.141592653589793 * roller_diam / CPR

    print(f"포트: {port}")
    print(f"롤러 직경: {roller_diam}mm")
    print(f"펄스당 이동거리: {mm_per_pulse:.4f}mm")
    print(f"분해능(CPR): {CPR} counts/rev")
    print("-" * 60)
    print(f"{'시간(s)':>8}  {'펄스':>10}  {'거리(mm)':>10}  {'속도(m/s)':>10}")
    print("-" * 60)

    # 속도 계산용 버퍼: (timestamp_s, distance_mm)
    history = deque(maxlen=SPEED_WINDOW + 1)

    try:
        ser = serial.Serial(port, args.baud, timeout=1)
        time.sleep(2)  # ESP32 리셋 대기
        ser.reset_input_buffer()

        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
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
            distance_mm = total_count * mm_per_pulse

            # 속도 계산 (이동평균)
            history.append((t_sec, distance_mm))
            speed_ms = 0.0
            if len(history) >= 2:
                dt = history[-1][0] - history[0][0]
                dd = history[-1][1] - history[0][1]
                if dt > 0:
                    speed_ms = dd / dt / 1000.0  # mm/s → m/s

            print(f"{t_sec:8.2f}  {total_count:10d}  {distance_mm:10.2f}  {speed_ms:10.4f}")

    except serial.SerialException as e:
        print(f"시리얼 에러: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n종료")


if __name__ == "__main__":
    main()
