# BC250 Front Controller — DevKit mini board v1.0 (66 × 50 mm)

The smallest variant: an **ESP32-S3-DevKitC-1 on two 1×22 sockets, the PSU's ATX 24-pin plug straight on the board**, every small part (MOSFET, resistors, diode, caps) tucked *under* the DevKit between the socket rows. The display is wired to a 1×8 pin header. No cable surgery anywhere.

[🇰🇷 한국어](README.ko.md) · other boards: [DIY carrier (96×64)](../bc250-front-carrier/README.md) · [semi-assembled PCBA (90×56)](../bc250-front-pcba/README.md)

![render](images/board-iso.png)

| | |
|---|---|
| Size | **66 × 50 mm**, 2 layers, 1.6 mm, 2× M3 (under the DevKit) |
| MCU | ESP32-S3-DevKitC-1 (any N8R2 / N16R8) on 2× 1×22 female headers — USB end at the left board edge, antenna right |
| Power | ATX 24-pin header on board. 5VSB → DevKit `5V` pin (its own LDO makes 3V3). 12 V only feeds the fan |
| Power switch | **MOSFET (AO3400A)** grounds PS_ON — silent, fail-safe (PSU stays ON when the ESP32 is dead) |
| Display | 1×8 header `GND VCC SCL SDA RES DC CS BL` → ST7789 module via wires (≤ 15 cm) |
| Sensors | T1 · T2 3-pin headers — 2× DS18B20 on the GPIO7 1-wire bus (4.7 k pull-up on board) |
| Other | 4-pin PWM fan (top edge), external WS2812 header, front-panel 4-pin header (PWR A B GND) |
| Checks | KiCad 10 ERC / DRC / schematic parity **0 issues**. **Not yet verified on a physical board** |

Fixes vs the v1.0 boards: PWR_OK divider 10k/**20k** (3.3 V instead of a marginal 2.5 V) · external LED header fed from ~4.3 V (D2) so 3.3 V data is a valid HIGH · 10 k series resistor on FAN TACH.

## Files

| File | Use |
|---|---|
| [`gerbers/bc250-front-mini-v1.0-gerbers.zip`](gerbers/bc250-front-mini-v1.0-gerbers.zip) | Gerbers + drill for JLCPCB |
| [`jlcpcb-bom.csv`](jlcpcb-bom.csv) · [`jlcpcb-cpl.csv`](jlcpcb-cpl.csv) | optional JLCPCB Economic assembly — the **8 SMD parts only** (all Basic, no loading fee) |
| `jlcpcb-bom-full.csv` · `jlcpcb-cpl-full.csv` | also assembles the ATX header and 1×3 / 1×4 headers (3 Extended parts, +$9) |
| `bc250-front-mini.kicad_pro` / `.kicad_sch` / `.kicad_pcb` | KiCad 10 project (self-contained libraries) — edit freely |
| [`bc250-front-mini-schematic.pdf`](bc250-front-mini-schematic.pdf) | schematic |
| [`../tools/`](../tools/) | `build.sh mini` regenerates everything from `designs/mini.py` |

## BOM

| Ref | Qty | Part | LCSC |
|---|---|---|---|
| U1 | 1 | ESP32-S3-DevKitC-1 with pin headers | — |
| U1 sockets | 2 | 1×22 female header 2.54 mm | — |
| J1 | 1 | ATX 24-pin header Molex 5566-24A (4.2 mm 2×12 vertical) | C114088 |
| Q1 | 1 | AO3400A SOT-23 | C20917 |
| R1 R2 R6 | 3 | 10 kΩ 0603 | C25804 |
| R3 | 1 | 20 kΩ 0603 | C4184 |
| R4 | 1 | 4.7 kΩ 0603 | C23162 |
| D2 | 1 | 1N4148W SOD-123 | C81598 |
| C1 | 1 | 10 µF 0805 | C15850 |
| C4 | 1 | 100 nF 0603 | C14663 |
| J2 | 1 | 1×8 male pin header | — |
| J4 J8 | 2 | 1×4 male pin header | C124378 |
| J5 J6 J7 | 3 | 1×3 male pin header | C49257 |

## Build order
1. SMD parts under the DevKit (skip if JLCPCB assembles them). Silk `1` on D2 = cathode.
2. Pin headers J2, J4–J8.
3. DevKit sockets: plug the two sockets onto the DevKit first, insert the whole stack, solder. **USB end at the left edge** (silk `USB`), antenna right.
4. ATX header last (large thermal mass). Latch side toward the top edge.

## ⚠️ First power-up — before fitting the DevKit
1. Only the PSU plug on the board → PSU AC on. **The PSU turns on immediately — that is the fail-safe working.**
2. Multimeter: socket `5V` ↔ `GND` ≈ 5 V · `FAN` `12V` = 12 V.
3. 0 V or 12 V on `5V` → check J1 orientation / solder joints and **stop**. Otherwise PSU off, fit the DevKit.
4. USB → `esphome run bc250-front-st7789.yaml` → switch "server power" off in the dashboard → PSU turns off = OK.

## Firmware
```yaml
substitutions:
  relay_inverted: "true"   # same polarity as the relay module (GPIO4 LOW = power cut)
```
GPIOs are identical to the jumper-wire build — all `bc250-front*.yaml` files work unchanged (`log_uart` stays `UART0`).

## Connectors
| Label | Pins | Notes |
|---|---|---|
| `LCD` (J2) | GND VCC SCL SDA RES DC CS BL | same names as on the ST7789 module — wire like to like |
| `FAN` (J4, top edge) | GND 12V TAC PWM | 4-pin PWM fan |
| `T1` `T2` (J5 J6) | GND DQ 3V3 | DS18B20 (both on GPIO7) |
| `LED` (J7) | 5V DIN GND | external WS2812 (the 5V pin is really ~4.3 V — intended) |
| `PANEL` (J8) | PWR A B GND | three buttons, other legs to GND |

## Design notes
- **PS_ON**: Q1 drain → PS_ON, source → GND, gate ← GPIO4 + R1 10 k pull-up to 3V3. Reset / download / dead ESP32 → gate HIGH → PSU on. Firmware drives GPIO4 LOW → PSU off.
- **PWR_OK**: 5 V → R2 10 k / R3 20 k → 3.3 V → GPIO5.
- **LED**: 5 V → D2 → ~4.3 V → J7 so the 3.3 V data line satisfies the WS2812B 0.7×VDD input threshold. 1N4148W = 150 mA → up to 2 LEDs.
- **FAN TACH**: R6 10 k in series protects GPIO11 from fans with an internal 12 V pull-up.
- **Antenna**: copper-free zone under the DevKit's antenna end. **Holes**: M3 ×2 under the DevKit (8.5 mm socket clearance).
- **ATX header orientation** follows the KiCad Molex 5566-24A footprint (same as the other two boards) — unverified on hardware, hence the power-up check above.
