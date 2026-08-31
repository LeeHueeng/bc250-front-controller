# BC250 Front Controller — 캐리어 PCB v1.0

ESP32-S3 DevKitC-1을 꽂는 캐리어 보드입니다. **PSU의 ATX 24핀 플러그가 보드에 그대로 꽂히므로** 점퍼선·글루건 없이 5VSB / PS_ON / PWR_OK / 12V / GND가 전부 자동으로 연결됩니다. 부품은 전부 관통형(THT)이라 인두기 하나면 조립할 수 있습니다.

[🇺🇸 English](README.md)

![보드 렌더링](images/board-iso.png)

| | |
|---|---|
| 크기 | 96 × 64 mm, 2층, 1.6 mm, M3 홀 4개 (간격 87 × 55 mm) |
| MCU | ESP32-S3-DevKitC-1 (2×22핀) → 암소켓 2개에 꽂음 |
| 전원 | ATX 24핀 헤더 (Molex Mini-Fit Jr 5566-24A) 온보드 |
| 릴레이 | SRD-05VDC-SL-C + S8050 NPN 드라이버 온보드 — 기존과 같은 **NC fail-safe** 배선 |
| 디스플레이 | ST7789 2.4″ SPI 8핀 소켓 **과** SSD1306 OLED 4핀 소켓 (둘 중 하나만 꽂으면 됨) |
| 기타 커넥터 | 4핀 PWM 팬, DS18B20 ×2, 외장 WS2812, 전면패널 버튼 6핀 + 온보드 택트 3개 |
| 검증 | KiCad 10 ERC / DRC / 회로도-PCB 정합성 **모두 0건** (실물 검증은 아직 — 아래 첫 전원 절차 참고) |

## 파일

| 파일 | 용도 |
|---|---|
| [`gerbers/bc250-front-carrier-v1.0-gerbers.zip`](gerbers/bc250-front-carrier-v1.0-gerbers.zip) | **JLCPCB에 올리는 파일** (거버 + Excellon 드릴 + 잡파일) |
| `bc250-front-carrier.kicad_pro` / `.kicad_sch` / `.kicad_pcb` | KiCad 10 프로젝트 (풋프린트·심볼 라이브러리 동봉, 다른 PC에서도 바로 열림) |
| [`bc250-front-carrier-schematic.pdf`](bc250-front-carrier-schematic.pdf) | 회로도 |
| [`bom.csv`](bom.csv) | 부품표 |
| `bc250-front-carrier-pos.csv` | 부품 좌표 (조립 참고용) |
| `images/` | 앞·뒤·입체 렌더링, 레이아웃 SVG, 회로도 SVG |
| [`../tools/`](../tools/) | 보드 전체를 스크립트로 재생성 (`build.sh`) |

## JLCPCB 주문

1. [jlcpcb.com](https://jlcpcb.com) → **Order now** → *Add gerber file* → `gerbers/bc250-front-carrier-v1.0-gerbers.zip` 업로드
2. 96 × 64 mm, 2 layers로 자동 인식됩니다. 옵션은 **기본값 그대로** 두면 됩니다: FR-4, 1.6 mm, 1 oz, HASL, 수량 5장 (색은 취향, Remove Order Number는 No).
3. SMT 조립 서비스는 필요 없습니다 — 전부 직접 납땜합니다.
4. 5장에 보드값 약 $2 + 배송비 수준입니다.

## 부품표 (BOM)

| 참조 | 수량 | 부품 | 비고 |
|---|---|---|---|
| U1 | 1 | ESP32-S3-DevKitC-1 (N8R2 / N16R8 무관) | 수핀 헤더가 납땜된 것 |
| U1 소켓 | 2 | 1×22 암 핀소켓 2.54 mm | DevKit을 꽂은 채로 납땜하면 정렬이 쉬움 |
| J1 | 1 | ATX 24핀 보드용 커넥터 (Molex 5566-24A / 39-28-1243 호환, 4.2 mm 2×12 수직) | 국내: 디바이스마트·엘레파츠 "ATX 24핀 커넥터 보드용" |
| K1 | 1 | SRD-05VDC-SL-C 릴레이 (Songle / Sanyou SRD) | |
| Q1 | 1 | S8050 NPN (2N2222A·BC337도 가능) | TO-92, E-B-C |
| D1 | 1 | 1N4148 | 띠(캐소드)를 실크 **K** 쪽으로 |
| R1 | 1 | 1 kΩ | |
| R2, R3, R4 | 3 | 10 kΩ | |
| R5 | 1 | 4.7 kΩ | |
| C1 | 1 | 100 µF 16 V 전해 (5 mm) | 긴 다리(+)를 실크 **+** 쪽으로 |
| C2 | 1 | 100 nF 세라믹 | |
| J2 | 1 | 1×8 암 핀소켓 | ST7789 LCD 모듈이 그대로 꽂힘 |
| J3 | 1 | 1×4 암 핀소켓 | SSD1306 OLED 모듈이 그대로 꽂힘 |
| J4 | 1 | 1×4 수 핀헤더 | 4핀 팬 (진짜 팬 헤더도 꽂힘) |
| J5, J6, J7 | 3 | 1×3 수 핀헤더 | DS18B20 ×2, WS2812 |
| J8 | 1 | 1×6 수 핀헤더 | 전면 패널 버튼 (선택) |
| SW1–SW3 | 3 | 6×6 mm 택트 스위치 | 온보드 PWR / A / B |
| H1–H4 | 4 | M3 서포트 | 선택 |

## 조립 순서

1. **낮은 부품부터**: R1–R5 → D1 (띠를 `K` 쪽) → Q1 (평평한 면을 실크 모양과 맞춤) → C2 → C1 (`+` 확인)
2. **소켓·헤더**: J2·J3 암소켓, J4–J8 핀헤더, SW1–SW3, U1용 1×22 암소켓 ×2
3. **큰 부품**: K1 릴레이, J1 ATX 헤더 — 래치 홈이 있는 면이 보드 위쪽 가장자리(`ATX 24-pin ← PSU plug` 글자 쪽)를 향하게

## ⚠️ 첫 전원 인가 — ESP32를 꽂기 **전에**

ATX 헤더의 핀 번호는 KiCad 표준 Molex 5566-24A 풋프린트를 따랐지만, 실물로 검증된 보드는 아직 없습니다. 1분이면 확인됩니다.

1. DevKit **없이** PSU 24핀만 꽂고 PSU를 켭니다. 릴레이가 쉬는 상태(NC)라 **PSU가 바로 켜지는 게 정상**입니다 (ESP32가 죽어도 서버는 켜져 있다는 그 fail-safe).
2. 멀티미터로 확인 (보드 뒷면 실크에도 적혀 있음):
   - U1 소켓 윗줄 `5V` 핀 ↔ `GND` = **약 5 V**
   - `FAN` 헤더 `12V` 핀 ↔ `GND` = **12 V**
   - `5V` 자리에 0 V나 12 V가 나오면 J1 방향·납땜을 확인하고 **진행을 멈추세요.**
3. PSU를 끄고 DevKit 장착: USB 커넥터가 보드 **왼쪽 가장자리**(`USB` 실크), 안테나가 릴레이 쪽.

## 펌웨어

- yaml의 `substitutions:`에서 **`relay_inverted: "false"`** 로 바꿉니다 (이 보드는 NPN 직결 active-high; 시판 릴레이 모듈은 `"true"`).
- 외장 WS2812를 J7에 달면 `light:`의 `num_leds`를 조정하세요 (DevKit 내장 LED가 첫 번째 픽셀).
- 나머지 핀맵은 [배선 가이드](../../docs/wiring-guide.html)와 동일 — 보드가 그 배선을 그대로 구현한 것입니다.

## 설계 메모

- **릴레이**: COM=PS_ON, NC=GND. 평상시 PS_ON이 접지돼 PSU ON. GPIO4 HIGH → Q1 → 코일 여자 → NC 열림 → PSU OFF. R2(10 k) 풀다운으로 ESP32 부팅 중 코일이 뜨지 않게 하고, D1이 플라이백을 잡습니다. NO 접점은 비워둠.
- **PWR_OK**: 5 V → R3/R4 10 k/10 k → 2.5 V → GPIO5.
- **1-Wire**: GPIO7, R5 4.7 k → 3V3. DS18B20 두 개는 J5/J6에 병렬.
- **전원**: 5VSB → DevKit `5V` 핀(내장 LDO) + 릴레이 코일 (C1 100 µF). 3V3는 DevKit LDO 출력을 J2/J3/J5/J6/R5에 분배. 12V는 팬 전용(PSU 켜져 있을 때만).
- **레이아웃**: 신호 0.3 mm, 전원 0.7 mm, 양면 GND 폴, WROOM 안테나 아래 구리 제거(keepout). 배선은 Freerouting 자동 배선 후 DRC 통과.

## 재생성 (수정하고 싶을 때)

`.kicad_pcb`를 손으로 고치기보다 `../tools/gen_pcb.py`(배치·넷)와 `gen_sch.py`(회로도)를 고친 뒤 `../tools/build.sh`를 돌리세요. KiCad 10과 Java 21+가 필요하며, Freerouting은 스크립트가 자동으로 내려받습니다. 결과물은 이 폴더에 다시 설치됩니다.
