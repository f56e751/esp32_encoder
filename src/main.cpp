#include <Arduino.h>
#include "driver/pcnt.h"
#include "driver/gpio.h"

// ─── 핀 설정 ───
#define ENC_A_PIN  21  // A상
#define ENC_B_PIN  22  // B상
#define ENC_Z_PIN  23  // Z상 (인덱스)

// ─── PCNT 설정 ───
#define PCNT_UNIT      PCNT_UNIT_0
#define PCNT_H_LIM     30000
#define PCNT_L_LIM    -30000

// ─── 출력 주기 ───
#define OUTPUT_INTERVAL_MS  50  // 50ms → 20Hz

// 델타 추적 방식 (ISR 불필요)
long total_count_accum = 0;
int16_t prev_raw = 0;
bool first_read = true;

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

    // 글리치 필터 (5us, 80MHz APB 기준 = 400 클럭)
    pcnt_set_filter_value(PCNT_UNIT, 400);
    pcnt_filter_enable(PCNT_UNIT);

    pcnt_counter_pause(PCNT_UNIT);
    pcnt_counter_clear(PCNT_UNIT);

    // 내부 풀업 활성화 (A상, B상)
    gpio_pullup_en((gpio_num_t)ENC_A_PIN);
    gpio_pullup_en((gpio_num_t)ENC_B_PIN);

    pcnt_counter_resume(PCNT_UNIT);
}

// 델타 추적 방식: 50ms마다 호출, 카운터 차이를 누적
long read_total_count() {
    int16_t raw = 0;
    pcnt_get_counter_value(PCNT_UNIT, &raw);

    if (first_read) {
        first_read = false;
        prev_raw = raw;
        return 0;
    }

    int32_t delta = (int32_t)raw - (int32_t)prev_raw;

    // 카운터가 H_LIM(30000)이나 L_LIM(-30000)에서 0으로 리셋된 경우 보정
    // 정상 50ms 간 델타는 최대 수천 수준이므로 15000 초과면 리셋 발생
    if (delta < -15000) {
        delta += PCNT_H_LIM;   // 정방향 회전 중 H_LIM 리셋
    } else if (delta > 15000) {
        delta += PCNT_L_LIM;   // 역방향 회전 중 L_LIM 리셋
    }

    total_count_accum += delta;
    prev_raw = raw;
    return total_count_accum;
}

void setup() {
    Serial.begin(115200);
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
