# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ESP32-based conveyor belt encoder signal reader using hardware PCNT (Pulse Counter). The system reads quadrature encoder signals (Autonics E50S8-5000-3-N-24, 5000PPR) via ESP32's PCNT peripheral with 4x decoding (20000 counts/revolution), and streams CSV data over serial to a Python receiver on PC.

## Build & Upload

PlatformIO project (Arduino framework, esp32dev board). Requires virtual environment with PlatformIO installed.

```bash
source .venv/bin/activate
pio run                                          # build only
pio run -t upload --upload-port /dev/ttyUSB0     # build + flash
pio device monitor -p /dev/ttyUSB0               # serial monitor
```

## Architecture

Two components:

- **`src/main.cpp`** — ESP32 firmware. Configures PCNT unit 0 with two channels for 4x quadrature decoding (A→CH0, B→CH1). Uses delta-tracking (no ISR) to accumulate counts across PCNT counter resets at ±30000 limits. Outputs `timestamp_ms,total_count` CSV at 20Hz over 115200 baud serial. Glitch filter set to 400 APB clocks (~5µs).

- **`pc/receiver.py`** — Python serial receiver. Parses CSV stream, converts pulses to distance using roller diameter, calculates speed with EMA smoothing (α=0.1) and deadband filtering. Displays live TUI via ANSI escape codes. Depends on `pyserial`.

## Key Constants

- Encoder: 5000 PPR × 4 = 20000 CPR
- GPIO pins: A=21, B=22, Z=23 (Z unused)
- PCNT limits: ±30000 (delta overflow threshold: 15000)
- Serial: 115200 baud, 50ms output interval
- Protocol: first line `ENCODER_READY`, then `timestamp_ms,total_count`

## Language

README and code comments are in Korean (한국어).
