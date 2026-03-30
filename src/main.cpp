#include <Arduino.h>
#include "driver/pcnt.h"

// ─── 핀 설정 ───
#define ENC_A_PIN  34  // A상
#define ENC_B_PIN  35  // B상
#define ENC_Z_PIN  32  // Z상 (인덱스)

// ─── PCNT 설정 ───
#define PCNT_UNIT      PCNT_UNIT_0
#define PCNT_H_LIM     30000
#define PCNT_L_LIM    -30000

// ─── 출력 주기 ───
#define OUTPUT_INTERVAL_MS  50  // 50ms → 20Hz

// 오버플로우 누적용
volatile long overflow_count = 0;

// PCNT 오버플로우 ISR
static void IRAM_ATTR pcnt_overflow_isr(void *arg) {
    uint32_t status = 0;
    pcnt_get_event_status(PCNT_UNIT, &status);

    if (status & PCNT_EVT_H_LIM) {
        overflow_count += PCNT_H_LIM;
    }
    if (status & PCNT_EVT_L_LIM) {
        overflow_count += PCNT_L_LIM;
    }
}

void pcnt_init() {
    pcnt_config_t config = {};

    // A상 → pulse_gpio, B상 → ctrl_gpio
    // 4체배(4x) 디코딩: 양 에지 모두 카운트
    config.pulse_gpio_num = ENC_A_PIN;
    config.ctrl_gpio_num  = ENC_B_PIN;
    config.unit           = PCNT_UNIT;
    config.channel        = PCNT_CHANNEL_0;
    config.pos_mode       = PCNT_COUNT_INC;  // A 상승 + B LOW → 증가
    config.neg_mode       = PCNT_COUNT_DEC;  // A 하강 + B LOW → 감소
    config.lctrl_mode     = PCNT_MODE_REVERSE; // B HIGH → 방향 반전
    config.hctrl_mode     = PCNT_MODE_KEEP;    // B LOW → 유지
    config.counter_h_lim  = PCNT_H_LIM;
    config.counter_l_lim  = PCNT_L_LIM;
    pcnt_unit_config(&config);

    // 채널1: B상 에지도 카운트 → 4체배
    config.pulse_gpio_num = ENC_B_PIN;
    config.ctrl_gpio_num  = ENC_A_PIN;
    config.channel        = PCNT_CHANNEL_1;
    config.pos_mode       = PCNT_COUNT_DEC;
    config.neg_mode       = PCNT_COUNT_INC;
    config.lctrl_mode     = PCNT_MODE_REVERSE;
    config.hctrl_mode     = PCNT_MODE_KEEP;
    pcnt_unit_config(&config);

    // 글리치 필터 (1us, 80MHz APB 기준 = 80 클럭)
    pcnt_set_filter_value(PCNT_UNIT, 80);
    pcnt_filter_enable(PCNT_UNIT);

    // 오버플로우 이벤트 설정
    pcnt_event_enable(PCNT_UNIT, PCNT_EVT_H_LIM);
    pcnt_event_enable(PCNT_UNIT, PCNT_EVT_L_LIM);

    pcnt_counter_pause(PCNT_UNIT);
    pcnt_counter_clear(PCNT_UNIT);

    // ISR 등록
    pcnt_isr_service_install(0);
    pcnt_isr_handler_add(PCNT_UNIT, pcnt_overflow_isr, NULL);

    pcnt_counter_resume(PCNT_UNIT);
}

// 현재 총 카운트 읽기 (오버플로우 포함)
long read_total_count() {
    int16_t raw = 0;
    pcnt_get_counter_value(PCNT_UNIT, &raw);

    long total;
    noInterrupts();
    total = overflow_count + raw;
    interrupts();
    return total;
}

void setup() {
    Serial.begin(115200);
    pinMode(ENC_Z_PIN, INPUT);

    pcnt_init();

    Serial.println("ENCODER_READY");
    Serial.println("# FORMAT: timestamp_ms,total_count");
}

void loop() {
    static unsigned long last_time = 0;
    unsigned long now = millis();

    if (now - last_time >= OUTPUT_INTERVAL_MS) {
        long count = read_total_count();
        // CSV 형식: timestamp_ms, total_pulse_count
        Serial.print(now);
        Serial.print(",");
        Serial.println(count);
        last_time = now;
    }
}
