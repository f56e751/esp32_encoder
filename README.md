# ESP32 Encoder Reader

ESP32 하드웨어 PCNT를 이용한 컨베이어 벨트 엔코더 신호 수신 시스템.

## 하드웨어

- **엔코더**: Autonics E50S8-5000-3-N-24 (5000PPR, ABZ 3상, NPN 오픈콜렉터)
- **MCU**: ESP32 DevKit
- **엔코더 전원**: 24V 어댑터
- **ESP32 전원**: USB (5V)

## 배선

| 엔코더 | 연결 | 비고 |
|---|---|---|
| 전원 (+) | 24V 어댑터 (+) | |
| 전원 (-) | 24V 어댑터 (-) + ESP32 GND | GND 공통 |
| A상 | 10kΩ 풀업(3.3V) → GPIO 21 | |
| B상 | 10kΩ 풀업(3.3V) → GPIO 22 | |
| Z상 | 10kΩ 풀업(3.3V) → GPIO 23 | |

> **주의**: 풀업 저항은 반드시 ESP32의 3.3V에 연결. 24V/5V 연결 시 ESP32 파손.

## 환경 세팅 (최초 1회)

```bash
# uv 설치 (없는 경우)
pip install uv

# 가상환경 생성 및 PlatformIO 설치
uv venv .venv
.venv\Scripts\activate
uv pip install platformio pip
```

## 빌드 & 업로드

```bash
# 가상환경 활성화
.venv\Scripts\activate

# 빌드만
pio run

# 빌드 + 업로드
pio run -t upload --upload-port COM3

# 시리얼 모니터
pio device monitor -p COM3
```

## PC 수신 (Python)

```bash
pip install pyserial
python pc/receiver.py --port COM3 --diameter 100
```

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `--port` | 시리얼 포트 | 자동 감지 |
| `--baud` | 통신 속도 | 115200 |
| `--diameter` | 롤러 직경 (mm) | 100 |

## 다른 PC에서 수신

ESP32에 펌웨어가 올라가 있으면 USB 연결만으로 데이터 수신 가능.

1. [CP210x 드라이버](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers) 설치
2. ESP32를 USB로 연결
3. `python pc/receiver.py --port COM숫자` 실행

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
