# ESP32 Encoder Reader

ESP32 하드웨어 PCNT를 이용한 컨베이어 벨트 엔코더 신호 수신 시스템.

## 하드웨어

- **엔코더**: Autonics E50S8-5000-3-N-24 (5000PPR, AB 2상 사용, NPN 오픈콜렉터)
- **MCU**: ESP32 DevKit
- **엔코더 전원**: 24V 어댑터
- **ESP32 전원**: USB (5V)

## 배선

| 엔코더 케이블 | 색상 | 연결 | 비고 |
|---|---|---|---|
| 전원 (+V) | 갈색 | 24V 어댑터 (+) | |
| 전원 (0V) | 파랑 | 24V 어댑터 (-) + ESP32 GND | **GND 공통 필수** |
| A상 | 검정 | 10kΩ 풀업(3.3V) → GPIO 21 | |
| B상 | 백색 | 10kΩ 풀업(3.3V) → GPIO 22 | |
| Z상 | 주황 | 미사용 | 연결 불필요 |
| Shield/FG | - | ESP32 GND | 노이즈 차폐 |

> **주의**: 풀업 저항은 반드시 ESP32의 3.3V에 연결. 24V/5V 연결 시 ESP32 파손.
> 
> **중요**: 엔코더 0V(파랑)와 ESP32 GND를 반드시 공통 연결해야 합니다. 미연결 시 신호 불안정.

## 환경 세팅 (최초 1회)

```bash
# uv 설치 (없는 경우)
# Windows
pip install uv
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# 가상환경 생성 및 PlatformIO 설치
uv venv .venv

# 가상환경 활성화
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

uv pip install platformio setuptools pip
```

## 빌드 & 업로드

```bash
# 가상환경 활성화
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 빌드만
pio run

# 빌드 + 업로드
# Windows
pio run -t upload --upload-port COM3
# Linux
pio run -t upload --upload-port /dev/ttyUSB0

# 시리얼 모니터
# Windows
pio device monitor -p COM3
# Linux
pio device monitor -p /dev/ttyUSB0
```

## PC 수신 (Python)

```bash
pip install pyserial

# Windows
python pc/receiver.py --port COM3 --diameter 100
# Linux
python pc/receiver.py --port /dev/ttyUSB0 --diameter 100
```

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `--port` | 시리얼 포트 | 자동 감지 |
| `--baud` | 통신 속도 | 115200 |
| `--diameter` | 롤러 직경 (mm) | 100 |

## 다른 PC에서 수신

ESP32에 펌웨어가 올라가 있으면 USB 연결만으로 데이터 수신 가능.

1. [CP210x 드라이버](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers) 설치 (Linux는 대부분 기본 내장)
2. ESP32를 USB로 연결
3. 포트 확인 후 실행:
   - Windows: `python pc/receiver.py --port COM숫자`
   - Linux: `python pc/receiver.py --port /dev/ttyUSB0`

## ROS1 노드 (conveyor_encoder_node.py)

ESP32 시리얼 데이터를 받아 컨베이어 벨트 속도를 ROS 토픽으로 퍼블리시하는 노드. Python 2 / ROS1 (catkin) 환경 대상.

### 실행

```bash
# roscore가 실행 중이어야 함
roscore

# 기본 실행 (20Hz, 포트 자동감지)
rosrun my_gp8_control conveyor_encoder_node.py

# 포트, 롤러 직경, 발행 주기 지정
rosrun my_gp8_control conveyor_encoder_node.py _port:=/dev/ttyUSB0 _diameter:=100 _publish_hz:=5
```

> **참고**: `rosrun`으로 실행하려면 이 파일을 catkin 워크스페이스의 패키지 src 폴더에 복사하거나 심볼릭 링크해야 합니다.
> 또는 직접 실행: `python pc/conveyor_encoder_node.py _port:=/dev/ttyUSB0`

| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `_port` | 시리얼 포트 | 자동 감지 |
| `_baud` | 통신 속도 | 115200 |
| `_diameter` | 롤러 직경 (mm) | 100.0 |
| `_ema_alpha` | EMA 스무딩 계수 (0~1) | 0.1 |
| `_deadband` | 속도 데드밴드 (m/s) | 0.002 |
| `_publish_hz` | 토픽 발행 주기 (Hz) | 20.0 |

### 발행 토픽

| 토픽 | 타입 | 설명 |
|---|---|---|
| `/conveyor/speed` | `std_msgs/Float64` | 벨트 속도 (m/s) |
| `/conveyor/distance_mm` | `std_msgs/Float64` | 누적 이동거리 (mm) |

### 다른 노드에서 토픽 수신 예시

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rospy
from std_msgs.msg import Float64

def speed_callback(msg):
    rospy.loginfo("컨베이어 속도: %.4f m/s", msg.data)

def distance_callback(msg):
    rospy.loginfo("누적 거리: %.2f mm", msg.data)

rospy.init_node("conveyor_listener")
rospy.Subscriber("/conveyor/speed", Float64, speed_callback)
rospy.Subscriber("/conveyor/distance_mm", Float64, distance_callback)
rospy.spin()
```

### 토픽 확인 (터미널)

```bash
# 속도 모니터링
rostopic echo /conveyor/speed

# 발행 주기 확인
rostopic hz /conveyor/speed
```

## 시리얼 출력 형식

```
ENCODER_READY
# FORMAT: timestamp_ms,total_count
100,0
150,24
200,51
```

- 50ms 간격 (20Hz)
- 4체배 디코딩: 1회전 = 20000 카운트
- 펄스당 이동거리 = π × 롤러직경 ÷ 20000
