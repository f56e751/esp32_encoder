#include <Arduino.h>

// 엔코더 핀 설정
#define ENCODER_A 32
#define ENCODER_B 33

volatile long encoder_count = 0;
volatile int last_a = 0;
volatile int last_b = 0;

// 엔코더 A상 인터럽트
void IRAM_ATTR encoder_isr_a() {
    int a = digitalRead(ENCODER_A);
    int b = digitalRead(ENCODER_B);
    if (a != last_a) {
        encoder_count += (a == b) ? 1 : -1;
        last_a = a;
    }
}

// 엔코더 B상 인터럽트
void IRAM_ATTR encoder_isr_b() {
    int a = digitalRead(ENCODER_A);
    int b = digitalRead(ENCODER_B);
    if (b != last_b) {
        encoder_count += (a != b) ? 1 : -1;
        last_b = b;
    }
}

void setup() {
    Serial.begin(115200);

    pinMode(ENCODER_A, INPUT_PULLUP);
    pinMode(ENCODER_B, INPUT_PULLUP);

    last_a = digitalRead(ENCODER_A);
    last_b = digitalRead(ENCODER_B);

    attachInterrupt(digitalPinToInterrupt(ENCODER_A), encoder_isr_a, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ENCODER_B), encoder_isr_b, CHANGE);

    Serial.println("Encoder ready");
}

void loop() {
    long count;
    noInterrupts();
    count = encoder_count;
    interrupts();

    Serial.print("Count: ");
    Serial.println(count);

    delay(100);
}
