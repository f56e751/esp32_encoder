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

# 화면 갱신 주기 (초)
DISPLAY_INTERVAL = 0.5
# EMA 스무딩 계수 (0~1, 클수록 반응 빠름, 노이즈 많음)
EMA_ALPHA = 0.1
# 속도 데드밴드 (이 이하는 0으로 처리, m/s)
SPEED_DEADBAND = 0.002


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

    # 헤더 (고정 영역)
    header = (
        f"\033[1m ESP32 Encoder Receiver\033[0m\n"
        f" 포트: {port}  |  롤러 직경: {roller_diam}mm  |  "
        f"분해능: {CPR} CPR  |  펄스당: {mm_per_pulse:.4f}mm\n"
        f"{'─' * 52}\n"
    )

    try:
        ser = serial.Serial(port, args.baud, timeout=1)
        # 대기 중 표시
        sys.stdout.write("\033[2J\033[H")  # 화면 클리어
        sys.stdout.write(header)
        sys.stdout.write(" ESP32 리셋 대기 중...")
        sys.stdout.flush()
        time.sleep(2)
        ser.reset_input_buffer()

        last_display = 0.0
        speed_ema = 0.0
        speed_min = float('inf')
        speed_max = float('-inf')
        prev_t = None
        prev_dist = None
        t_sec = 0.0
        total_count = 0
        distance_mm = 0.0

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

            # 매 샘플마다 순간 속도 계산 → EMA 적용
            if prev_t is not None:
                dt = t_sec - prev_t
                dd = distance_mm - prev_dist
                if dt > 0:
                    instant_speed = dd / dt / 1000.0  # mm/s → m/s
                    speed_ema = EMA_ALPHA * instant_speed + (1 - EMA_ALPHA) * speed_ema
                    # 데드밴드: 정지 시 노이즈 제거
                    if abs(speed_ema) < SPEED_DEADBAND:
                        speed_ema = 0.0
            prev_t = t_sec
            prev_dist = distance_mm

            # 화면 갱신 주기
            now = time.monotonic()
            if now - last_display < DISPLAY_INTERVAL:
                continue
            last_display = now

            speed_ms = speed_ema
            if prev_t is not None and prev_dist is not None:
                speed_min = min(speed_min, speed_ms)
                speed_max = max(speed_max, speed_ms)

            # 방향 표시
            if speed_ms > 0.0001:
                direction = ">>>"
            elif speed_ms < -0.0001:
                direction = "<<<"
            else:
                direction = "---"

            # min/max 표시 (아직 기록 없으면 빈칸)
            if speed_min == float('inf'):
                min_str = "       N/A"
                max_str = "       N/A"
            else:
                min_str = f"{speed_min:>10.4f}"
                max_str = f"{speed_max:>10.4f}"

            # 화면 갱신 (커서를 홈으로 이동 후 덮어쓰기)
            sys.stdout.write("\033[H")  # 커서 홈
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
                f"  \033[2mCtrl+C 로 종료\033[0m\033[J"
            )
            sys.stdout.flush()

    except serial.SerialException as e:
        print(f"\n시리얼 에러: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stdout.write("\033[J\n 종료\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
