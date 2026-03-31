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
