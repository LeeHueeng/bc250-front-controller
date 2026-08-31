# BC250 Front Controller — 반조립 PCBA v1.0 (JLCPCB Economic 조립)

JLCPCB가 저항·콘덴서·MOSFET·LDO·USB-C·ATX 헤더·핀헤더·버튼을 전부 실장해서 보내고, **ESP32-S3 모듈 · 디스플레이 소켓 · (선택) 상태 LED 세 가지만 직접 납땜**하는 버전입니다. 이 세 부품을 빼면 JLCPCB의 저렴한 **Economic 조립**이 가능해져(ESP32 모듈과 5050 LED는 "Standard 전용" 부품) 고정비가 약 $22 줄어듭니다.

[🇺🇸 English](README.md) · 전부 직접 납땜하는 DevKit 버전은 [`../bc250-front-carrier/`](../bc250-front-carrier/README.ko.md)

![보드 렌더링](images/board-iso.png)

| | |
|---|---|
| 크기 | 90 × 56 mm, 2층, 1.6 mm, M3 홀 4개 |
| MCU | **ESP32-S3-WROOM-1** 모듈 (직접 납땜; N4/N8/N8R2/N16R8 아무거나) + USB-C 네이티브 USB (USB-시리얼 칩 없음) |
| 전원 제어 | **MOSFET(AO3400A)** 이 PS_ON을 접지 — 릴레이 없음, 무소음, fail-safe 동일 (ESP32가 죽어도 PSU ON) |
| 전원 | ATX 헤더의 5VSB → AMS1117-3.3. 12V는 팬 전용 |
| 디스플레이 | 1×8 소켓 자리(직접 납땜)에 **ST7789(8핀) 또는 SSD1306 OLED(앞 4핀)** |
| 센서 | T1·T2 3핀 헤더 — DS18B20 **또는 10 kΩ NTC** (4.7 k 풀업 내장) |
| 기타 | 4핀 PWM 팬, WS2812B 상태 LED 자리(선택) + 외장 LED 헤더, 전면패널 4핀, PWR/A/B/BOOT/RESET 버튼 |
| 검증 | KiCad 10 ERC / DRC / 회로도-PCB 정합성 0건. **실물 검증은 아직 없음** — 첫 보드는 아래 점검 절차대로 |

## 파일

| 파일 | 용도 |
|---|---|
| [`gerbers/bc250-front-pcba-v1.0-gerbers.zip`](gerbers/bc250-front-pcba-v1.0-gerbers.zip) | JLCPCB 1단계: 거버 업로드 |
| [`jlcpcb-bom.csv`](jlcpcb-bom.csv) · [`jlcpcb-cpl.csv`](jlcpcb-cpl.csv) | JLCPCB 2단계: **기본(반조립)** BOM/CPL — U1·J2·LED1 제외 |
| `jlcpcb-bom-full.csv` · `jlcpcb-cpl-full.csv` | 전부 조립시키고 싶을 때 (Standard 조립 필요, 약 +$30) |
| `bc250-front-pcba.kicad_pro` / `.kicad_sch` / `.kicad_pcb` | KiCad 10 프로젝트 (라이브러리 동봉) |
| [`bc250-front-pcba-schematic.pdf`](bc250-front-pcba-schematic.pdf) | 회로도 |
| `images/` | 렌더링·레이아웃·회로도 SVG |
| [`../tools/`](../tools/) | `build.sh pcba` 로 전체 재생성 |

## JLCPCB 주문

1. [jlcpcb.com](https://jlcpcb.com) → **Order now** → `gerbers/bc250-front-pcba-v1.0-gerbers.zip` 업로드. PCB 옵션 기본값(FR-4, 1.6 mm, HASL). 수량 **최소 2장**, 5장 추천.
2. **PCB Assembly** ON → **Economic** · Top side · 조립 수량 = 보드 수량.
3. **Add BOM / CPL**: `jlcpcb-bom.csv` + `jlcpcb-cpl.csv` 업로드 → 22줄 전부 LCSC 번호로 자동 매칭되는지 확인. (Extended 부품은 ATX 헤더·USB-C·핀헤더 2종 = 4종, 나머지는 Basic)
4. **배치 미리보기** 확인: `J3` USB-C 입구가 보드 **아래 가장자리**, `Q1`(SOT-23)·`U2`(SOT-223)·`D1`/`D2` 방향이 실크와 일치. 어긋나면 미리보기에서 회전.
5. 결제 → 1~2주 후 도착.

### 비용 (5장 기준 추정, 2026-08 — JLCPCB 견적이 정확)

| 항목 | 금액 |
|---|---|
| PCB 5장 | ~$2 |
| Economic 조립 셋업 + 스텐실 | ~$8 + ~$1.5 |
| Extended 부품 로딩비 4종 | ~$12 |
| 실장 부품값 (장당 ≈ $2.6) | ~$13 |
| 조립비 SMT+THT (장당 ≈ $1.7) | ~$8.5 |
| **JLCPCB 합계 (5장)** | **≈ $45 + 배송 → 장당 ≈ $9** |
| **JLCPCB 합계 (2장)** | **≈ $32 + 배송** |
| + 직접 구매: ESP32-S3-WROOM-1 (알리/LCSC ~$3.5), 1×8 암소켓 (₩100), WS2812B 5050 (선택, ₩100) | 장당 ≈ $4 |

→ **장당 ≈ $13 + 디스플레이·센서·팬**. 전부 조립(Standard, `*-full.csv`)은 5장 ≈ $100.

### 이 버전의 원가 절감 내역

| 항목 | 전 | 후 |
|---|---|---|
| 조립 등급 | Standard ($25 + $7) | **Economic ($8 + $1.5)** — 모듈·LED만 직접 납땜 |
| 릴레이 + 드라이버 (SRD-05V, S8050, 1N4148, 100 µF) | ~$0.7 + THT 4개 | **AO3400A MOSFET 1개** ($0.09), 무소음 |
| DevKit ($4.5~5) | 소켓 2개 + 별도 구매 | **WROOM 모듈** ($3.5) + USB-C ($0.31) + LDO ($0.12) |
| 관통형 R/C | THT 7개 | **0603/0805 Basic 부품** (로딩비 $0) |
| OLED 소켓 + LCD 소켓 | 2개 | **1×8 소켓 하나** (OLED는 앞 4핀) |
| 전면패널 헤더 1×6 | Extended 1종 | **1×4** → FAN과 같은 부품 |
| 택트 스위치 | 6×6 THT | **TS-1187A SMD (Basic, $0.02)** ×5 |
| 온도 센서 | DS18B20 ×2 (~₩3,000/개) | **10 kΩ NTC 겸용** (~₩300/개) |
| ESP32-S3 | N16R8 | **N4/N8도 가능** (PSRAM 불필요) — 직접 사니 아무거나 |

ESP32-C3 다운그레이드는 넣지 않았습니다: 풀옵션에 GPIO 15개가 필요한데 C3는 13개, 절감액도 $1 미만. OLED/최소 구성 전용이면 가능합니다.

## 직접 납땜할 부품 3개

| 부품 | 어떻게 |
|---|---|
| **U1 ESP32-S3-WROOM-1** | 가장자리 캐스텔레이션 패드(1.27 mm 피치)를 인두로: 플럭스 → 모서리 두 곳 가납땜으로 정렬 → 나머지 패드. 가운데 큰 GND 패드는 **안 해도 됨**(GND는 가장자리 1·40번 핀으로 연결됨; 열풍기 있으면 해도 좋음). 안테나가 보드 왼쪽 가장자리(실크 안테나 그림) 쪽. |
| **J2 디스플레이** | 1×8 2.54 mm 암소켓을 납땜해 모듈을 꽂거나(권장), 모듈의 핀헤더를 보드에 직접 납땜. OLED는 GND·VCC·SCL·SDA 4핀 자리에. |
| **LED1 WS2812B** (선택) | 5050 4패드, 1번 핀 표시(실크 `1`)가 왼쪽 위. 안 달아도 외장 LED 헤더 `LED`(J7)가 같은 데이터선을 받으므로 기능은 동일. |

## 사용법

### 펌웨어 (기존 yaml 그대로, substitutions 두 줄만)
```yaml
substitutions:
  relay_inverted: "true"        # 릴레이 모듈과 같은 극성 (GPIO4 LOW = 전원 차단)
  log_uart: USB_SERIAL_JTAG     # 네이티브 USB로 로그
```
GPIO 번호는 DevKit 배선과 100% 동일 — `bc250-front.yaml` / `bc250-front-st7789.yaml` / `bc250-front-minimal.yaml` 모두 그대로. 첫 굽기는 USB-C(`esphome run`), 이후 OTA. 자동 다운로드가 안 잡히면 **BOOT** 누른 채 **RESET**. 외장 LED만 쓰면 `num_leds: 1` 그대로(LED1과 같은 픽셀 0을 보여줌).

### 온도 센서 — DS18B20 또는 NTC
- **DS18B20 두 개(기본)**: T1·T2 모두 GPIO7 1-Wire 버스. yaml 그대로.
- **NTC 두 개 (가장 저렴)**: 뒷면 솔더 점퍼 **JP1** 을 `1-2`(기본, 실크 7)에서 `2-3`(실크 2)으로 옮기면 T2가 GPIO2 전용 채널. NTC를 SIG–GND 사이에 연결하고 yaml의 `one_wire`/`dallas_temp` 대신:
  ```yaml
  sensor:
    - platform: adc
      pin: GPIO7            # T1 (T2는 GPIO2)
      id: t1_adc
      attenuation: 12db
      update_interval: 5s
    - platform: resistance
      sensor: t1_adc
      configuration: DOWNSTREAM   # NTC가 GND 쪽, 4.7k 풀업이 3V3 쪽
      resistor: 4.7kOhm
      reference_voltage: 3.3V
      id: t1_res
    - platform: ntc
      sensor: t1_res
      id: gpu_temp
      name: "GPU 온도"
      calibration:
        b_constant: 3950
        reference_temperature: 25°C
        reference_resistance: 10kOhm
  ```

### 커넥터
| 라벨 | 핀 | 비고 |
|---|---|---|
| `LCD / OLED` (J2) | GND VCC SCL SDA RES DC CS BL | ST7789 8핀 / OLED는 앞 4핀 |
| `FAN` (J4) | GND 12V TACH PWM | 4핀 PWM 팬 |
| `T1` `T2` (J5 J6) | GND SIG 3V3 | DS18B20(GND DQ VDD) 또는 NTC(GND–SIG) |
| `LED` (J7) | 5V DIN GND | 외장 WS2812 (LED1과 병렬, 픽셀 0) |
| `PANEL` (J8) | PWR A B GND | 전면 버튼 (온보드 버튼과 병렬) |
| `UART` (J9, 미실장) | TX RX GND | 디버그용 |

### ⚠️ 첫 전원 인가
1. 모듈·디스플레이·센서를 달기 **전에** PSU 24핀만 꽂고 PSU on → **PSU가 바로 켜지는 게 정상**(fail-safe).
2. `T1` `3V3`–`GND` = 3.3 V, `FAN` `12V` = 12 V, `LED` `5V` = 5 V 확인 (뒷면 실크에도 표기). 이상 없으면 PSU 끄고 모듈 납땜.
3. USB-C 연결 → `esphome run` → 웹 대시보드에서 "서버 전원" 끄기 → PSU 꺼지면 OK.

## 설계 메모
- **PS_ON**: Q1 드레인 → PS_ON, 소스 → GND, 게이트 ← GPIO4 + R1 10 k 풀업(3V3). ESP32가 리셋/다운로드/사망이면 풀업이 게이트를 HIGH로 → PSU ON. 펌웨어가 GPIO4를 LOW로 → PSU OFF. 릴레이 모듈(active-low)과 같은 논리라 `relay_inverted: "true"`.
- **USB**: VBUS → D1(B5819W) → 5V 레일: USB만 꽂아도 동작, PSU 5VSB는 USB로 역류하지 않음. D+/D−는 커넥터 양면 패드를 고정 배선으로 브리지.
- **LED**: WS2812B VDD를 D2(1N4148W)로 ~4.3 V로 낮춰 3.3 V 데이터를 인식. J7은 같은 데이터선(병렬).
- **BOOT/RESET**: R7/R6 10 k 풀업, C5 1 µF EN 지연.
- **안테나**: 모듈 안테나가 왼쪽 가장자리로 향하고 그 아래 양면 구리 제거.
- **CPL 회전값**: KiCad 풋프린트와 JLCPCB(EasyEDA) 풋프린트의 1번 핀 위치를 실제 비교해 보정 (SOT-23·SOT-223 +180°, 나머지 0°).
