#pragma once
// bc250-front-st7789.yaml 전용 (esphome: includes) — 2026-09-07
// 콜드 부팅(5V 투입·RST 버튼 = POWERON) 직후 ESP32 를 1회 자동 재부팅한다. 콜드 부팅 첫 부팅에서는 LCD 에 아무것도
// 안 나오고(초기화·하드 복구를 다시 해도 안 됨) 칩을 리셋해야만 나오는 현상이 있는데, 소프트 재부팅으로도 해결됨을
// 실측(2026-09-07)했다 → RST 버튼을 펌웨어가 대신 눌러 준다. 두 번째 부팅은 리셋 원인이 SW 라서, RTC 메모리 플래그로
// "콜드 부팅에서 이어진 부팅"임을 넘겨 전원 정책(콜드 부팅 = 서버 ON)이 그대로 유지되게 한다.
#include <esp_attr.h>
#include <esp_system.h>
#include <stdint.h>

static const uint32_t BC250_COLD_MAGIC = 0xC01DB007u;
RTC_NOINIT_ATTR uint32_t bc250_cold_flag;   // RTC 메모리: 소프트 재부팅에도 유지, 전원 차단 때만 사라짐(무작위값)

// 이번 부팅을 "콜드 부팅"으로 취급해야 하나: 직접 POWERON 이거나, POWERON 직후 자동 재부팅으로 넘어온 2차 부팅
inline bool bc250_is_cold_boot() {
  esp_reset_reason_t r = esp_reset_reason();
  return r == ESP_RST_POWERON || (r == ESP_RST_SW && bc250_cold_flag == BC250_COLD_MAGIC);
}
