"""
bc250-front-mini : smallest board for the ESP32-S3-DevKitC-1 (2x22) with the PSU plug on board.

  * DevKit on two 1x22 female sockets (USB end at the left board edge, antenna hangs over the right)
  * ATX 24-pin header along the top edge - the PSU plug goes straight in (no cable surgery)
  * all small parts (MOSFET, resistors, diode, caps) are 0603/0805 SMD *under* the DevKit,
    between the two socket rows (8.5 mm of clearance with sockets)
  * display: 1x8 pin header GND VCC SCL SDA RES DC CS BL - wire it to the ST7789 module
  * fan, two DS18B20 probes, external WS2812, front-panel buttons: pin headers on the bottom edge
  * PS_ON is pulled low by an N-MOSFET (AO3400A) with a 10 k gate pull-up: PSU is ON while the
    ESP32 is dead / resetting / being flashed -> yaml  relay_inverted: "true"  (same as relay module)
  * fixes vs the v1.0 boards: PWR_OK divider 10k/20k (3.3 V, not 2.5 V), external LED header fed
    from ~4.3 V (D2) so 3.3 V data is valid, 10 k series resistor on FAN TACH
GPIO numbers are identical to the DevKit wiring -> bc250-front*.yaml unchanged (log_uart: UART0).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sexp import Sym, find, find_all

PROJECT = "bc250-front-mini"
TITLE = "BC250 Front Controller - ESP32-S3 DevKitC-1 mini"
REV = "1.0"
DATE = "2026-08-26"
BOARD_W, BOARD_H = 66.0, 50.0
CORNER_R = 2.0

NET_NAMES = [
    "", "GND", "+5V", "+3V3", "+12V", "PS_ON", "PWR_OK", "PWR_OK_SENSE", "RELAY_CTRL",
    "BTN_PWR", "BTN_A", "BTN_B", "OW",
    "SDA_MOSI", "SCL_SCK", "LCD_DC", "LCD_RST", "LCD_CS", "LCD_BL",
    "FAN_PWM", "FAN_TACH", "FAN_TACH_IO", "LED_DIN", "LED_VDD",
]
POWER_NETS = ["GND", "+5V", "+12V"]
FINE_NETS = []

FP_LIB_OF = {
    "Molex_Mini-Fit_Jr_5566-24A_2x12_P4.20mm_Vertical": "Connector_Molex",
    "SOT-23": "Package_TO_SOT_SMD",
    "D_SOD-123": "Diode_SMD",
    "R_0603_1608Metric": "Resistor_SMD",
    "C_0603_1608Metric": "Capacitor_SMD",
    "C_0805_2012Metric": "Capacitor_SMD",
    "PinHeader_1x03_P2.54mm_Vertical": "Connector_PinHeader_2.54mm",
    "PinHeader_1x04_P2.54mm_Vertical": "Connector_PinHeader_2.54mm",
    "PinHeader_1x08_P2.54mm_Vertical": "Connector_PinHeader_2.54mm",
    "MountingHole_3.2mm_M3": "MountingHole",
}

# ESP32-S3-DevKitC-1 socket pads (same numbering as gen_pcb.py / the carrier board)
DEVKIT_PINS = {
    1: "3V3", 2: "3V3", 3: "RST", 4: "IO4", 5: "IO5", 6: "IO6", 7: "IO7", 8: "IO15",
    9: "IO16", 10: "IO17", 11: "IO18", 12: "IO8", 13: "IO3", 14: "IO46", 15: "IO9",
    16: "IO10", 17: "IO11", 18: "IO12", 19: "IO13", 20: "IO14", 21: "5V", 22: "GND",
    23: "GND", 24: "GND", 25: "IO19", 26: "IO20", 27: "IO21", 28: "IO47", 29: "IO48",
    30: "IO45", 31: "IO0", 32: "IO35", 33: "IO36", 34: "IO37", 35: "IO38", 36: "IO39",
    37: "IO40", 38: "IO41", 39: "IO42", 40: "IO2", 41: "IO1", 42: "RX", 43: "TX", 44: "GND",
}
DEVKIT_NETS = {
    1: "+3V3", 2: "+3V3", 21: "+5V", 22: "GND", 23: "GND", 24: "GND", 44: "GND",
    4: "RELAY_CTRL", 5: "PWR_OK_SENSE", 6: "BTN_PWR", 7: "OW",
    12: "SDA_MOSI", 15: "SCL_SCK", 8: "LCD_DC", 9: "LCD_RST", 10: "LCD_CS", 11: "LCD_BL",
    16: "FAN_PWM", 17: "FAN_TACH_IO", 18: "BTN_A", 19: "BTN_B", 29: "LED_DIN",
}
ATX_NETS = {8: "PWR_OK", 9: "+5V", 10: "+12V", 11: "+12V", 16: "PS_ON",
            3: "GND", 5: "GND", 7: "GND", 15: "GND", 17: "GND", 18: "GND", 19: "GND", 24: "GND"}

# ----------------------------------------------------------------------------
# placement (mm, origin top-left, y down)
# ----------------------------------------------------------------------------
DEVKIT_X0, DEVKIT_Y0 = 62.0, 17.3          # socket pad 1 (3V3); rot 270 -> USB end at x=0.66, antenna at x=63.4
DEVKIT_ROW2_Y = DEVKIT_Y0 + 22.86
ATX_X1, ATX_Y1 = 62.5, 11.0                # pin 1; rot 180 -> pins 13-24 at y=5.5, latch side toward the top edge
TOP_Y = 3.6                                # FAN header on the top edge, left of the ATX header
BOT_Y = 46.5                               # bottom header row (pin 1 x given, pins go +x)

R0603 = "R_0603_1608Metric"
C0603 = "C_0603_1608Metric"
C0805 = "C_0805_2012Metric"

COMPONENTS = [
    ("U1", "ESP32-S3-DevKitC-1_Socket", "ESP32-S3-DevKitC-1", DEVKIT_X0, DEVKIT_Y0, 270, DEVKIT_NETS,
     "ESP32-S3-DevKitC-1 dev board on 2x 1x22 female headers (USB end = left board edge)"),
    ("J1", "Molex_Mini-Fit_Jr_5566-24A_2x12_P4.20mm_Vertical", "ATX 24-pin", ATX_X1, ATX_Y1, 180, ATX_NETS,
     "ATX 24-pin motherboard header (Molex 5566-24A / 39-28-1243); the PSU plug goes here"),
    # --- under the DevKit, between the socket rows ---
    ("C1", C0805, "10uF", 12.5, 23.5, 0, {1: "+5V", 2: "GND"}, "5VSB bulk"),
    ("D2", "D_SOD-123", "1N4148W", 17.5, 26.5, 0, {1: "LED_VDD", 2: "+5V"},
     "drops the external LED supply to ~4.3 V so the 3.3 V data line is a valid HIGH"),
    ("C4", C0603, "100nF", 17.5, 30.0, 0, {1: "LED_VDD", 2: "GND"}, "LED supply decoupling"),
    ("R6", R0603, "10k", 22.5, 23.5, 0, {1: "FAN_TACH", 2: "FAN_TACH_IO"}, "TACH series protection"),
    ("R4", R0603, "4.7k", 42.5, 24.5, 0, {1: "OW", 2: "+3V3"}, "DS18B20 1-wire pull-up"),
    ("R2", R0603, "10k", 47.5, 24.5, 0, {1: "PWR_OK", 2: "PWR_OK_SENSE"}, "PWR_OK divider top"),
    ("R3", R0603, "20k", 47.5, 28.0, 0, {1: "PWR_OK_SENSE", 2: "GND"}, "PWR_OK divider bottom (5 V -> 3.3 V)"),
    ("Q1", "SOT-23", "AO3400A", 53.0, 25.5, 0, {1: "RELAY_CTRL", 2: "GND", 3: "PS_ON"},
     "N-MOSFET pulls PS_ON low (PSU on); gate pulled up -> fail-safe on"),
    ("R1", R0603, "10k", 53.0, 30.5, 0, {1: "RELAY_CTRL", 2: "+3V3"}, "gate pull-up (PSU on while ESP32 is dead)"),
    # --- top edge ---
    ("J4", "PinHeader_1x04_P2.54mm_Vertical", "FAN", 3.0, TOP_Y, 90, {1: "GND", 2: "+12V", 3: "FAN_TACH", 4: "FAN_PWM"},
     "4-pin PWM fan: GND 12V TACH PWM"),
    # --- bottom edge ---
    ("J8", "PinHeader_1x04_P2.54mm_Vertical", "PANEL", 4.0, BOT_Y, 90, {1: "BTN_PWR", 2: "BTN_A", 3: "BTN_B", 4: "GND"},
     "front-panel buttons: PWR A B GND"),
    ("J7", "PinHeader_1x03_P2.54mm_Vertical", "LED", 15.5, BOT_Y, 90, {1: "LED_VDD", 2: "LED_DIN", 3: "GND"},
     "external WS2812 status LED: 5V(4.3V) DIN GND"),
    ("J5", "PinHeader_1x03_P2.54mm_Vertical", "T1", 24.5, BOT_Y, 90, {1: "GND", 2: "OW", 3: "+3V3"},
     "DS18B20 #1 (GPU): GND DQ VDD"),
    ("J6", "PinHeader_1x03_P2.54mm_Vertical", "T2", 33.5, BOT_Y, 90, {1: "GND", 2: "OW", 3: "+3V3"},
     "DS18B20 #2 (case): GND DQ VDD"),
    ("J2", "PinHeader_1x08_P2.54mm_Vertical", "LCD", 43.0, BOT_Y, 90,
     {1: "GND", 2: "+3V3", 3: "SCL_SCK", 4: "SDA_MOSI", 5: "LCD_RST", 6: "LCD_DC", 7: "LCD_CS", 8: "LCD_BL"},
     "ST7789 SPI module via wires: GND VCC SCL SDA RES DC CS BL"),
    ("H1", "MountingHole_3.2mm_M3", "M3", 7.0, 28.5, 0, {}, "mounting hole (under the DevKit)"),
    ("H2", "MountingHole_3.2mm_M3", "M3", 38.0, 29.0, 0, {}, "mounting hole (under the DevKit)"),
]
DNP = set()

# LCSC numbers for JLCPCB assembly ('' = not assembled).  Default BOM = SMD parts only (all Basic ->
# Economic assembly, no loading fee); --full adds the ATX header and the 1x03/1x04 headers.
LCSC = {
    "U1": "", "J1": "C114088", "J2": "",
    "C1": "C15850", "C4": "C14663", "D2": "C81598",
    "R1": "C25804", "R2": "C25804", "R6": "C25804", "R3": "C4184", "R4": "C23162",
    "Q1": "C20917",
    "J4": "C124378", "J8": "C124378", "J5": "C49257", "J6": "C49257", "J7": "C49257",
    "H1": "", "H2": "",
}
ASSEMBLE_EXCLUDE = {"J1", "J4", "J5", "J6", "J7", "J8"}
BASIC_PARTS = {"C15850", "C14663", "C81598", "C25804", "C4184", "C23162", "C20917"}

TEXT_POS = {
    "J1": {"Reference": (23.1, 2.75, 0, None), "Value": (10.0, 2.75, 0, None)},
    "U1": {"Reference": (11.43, 30.0, 90, "F.Fab"), "Value": (14.5, 30.0, 90, "F.Fab")},
}
HIDE_REF = {"H1", "H2", "J2", "J4", "J5", "J6", "J7", "J8"}

# ----------------------------------------------------------------------------
# DevKit socket footprint: same as gen_pcb's, but the courtyard only covers the two socket
# rows so that the SMD parts / mounting holes under the DevKit don't trip the courtyard DRC.
# ----------------------------------------------------------------------------
def _rect(x1, y1, x2, y2, layer, w=0.05):
    import uuid
    return [Sym("fp_rect"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
            [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]],
            [Sym("fill"), Sym("no")], [Sym("layer"), layer], [Sym("uuid"), str(uuid.uuid4())]]

def make_devkit_socket_fp_mini():
    m = sys.modules.get("gen_pcb")
    if m is None or not hasattr(m, "make_devkit_socket_fp"):
        m = sys.modules["__main__"]
    fp = m.make_devkit_socket_fp()
    keep = []
    for e in fp:
        if isinstance(e, list) and e and e[0] == "fp_rect":
            ly = find(e, "layer")
            if ly is not None and ly[1] == "F.CrtYd":
                continue
        keep.append(e)
    for sx in (0.0, 22.86):
        keep.append(_rect(sx - 1.6, -1.6, sx + 1.6, 53.34 + 1.6, "F.CrtYd"))
    return keep

CUSTOM_FOOTPRINTS = {"ESP32-S3-DevKitC-1_Socket": make_devkit_socket_fp_mini}

# ----------------------------------------------------------------------------
# silkscreen
# ----------------------------------------------------------------------------
def _row(x0, y, names, dy=-3.3, size=0.8):
    return [(n, x0 + 2.54 * i, y + dy, 90, size, "F.SilkS") for i, n in enumerate(names)]

SILK_TEXT = []
SILK_TEXT += _row(3.0, TOP_Y, ["GND", "12V", "TAC", "PWM"], dy=3.3)
SILK_TEXT += _row(4.0, BOT_Y, ["PWR", "A", "B", "GND"])
SILK_TEXT += _row(15.5, BOT_Y, ["5V", "DIN", "GND"])
SILK_TEXT += _row(24.5, BOT_Y, ["GND", "DQ", "3V3"])
SILK_TEXT += _row(33.5, BOT_Y, ["GND", "DQ", "3V3"])
SILK_TEXT += _row(43.0, BOT_Y, ["GND", "VCC", "SCL", "SDA", "RES", "DC", "CS", "BL"])
SILK_TEXT += [
    ("FAN", 6.8, 10.0, 0, 0.8, "F.SilkS"),
    ("PANEL", 7.8, BOT_Y + 2.6, 0, 0.8, "F.SilkS"),
    ("LED", 18.0, BOT_Y + 2.6, 0, 0.8, "F.SilkS"),
    ("T1", 27.0, BOT_Y + 2.6, 0, 0.8, "F.SilkS"),
    ("T2", 36.0, BOT_Y + 2.6, 0, 0.8, "F.SilkS"),
    ("LCD ST7789 SPI", 51.9, BOT_Y + 2.6, 0, 0.8, "F.SilkS"),
    ("ATX 24-pin  <- PSU plug", 39.0, 1.5, 0, 0.9, "F.SilkS"),
    ("USB", 2.6, 28.7, 90, 0.9, "F.SilkS"),
    ("BC250 Front Controller mini v1.0", 33.0, 22.0, 0, 1.0, "B.SilkS"),
    ("github.com/LeeHueeng/bc250-front-controller", 33.0, 33.5, 0, 1.0, "B.SilkS"),
    ("CHECK 5VSB=5V / 12V BEFORE FITTING ESP32", 33.0, 36.0, 0, 0.9, "B.SilkS"),
]
# DevKit pin labels between the socket rows (visible before the DevKit is fitted)
for n in range(1, 23):
    SILK_TEXT.append((DEVKIT_PINS[n].replace("IO", ""), DEVKIT_X0 - (n - 1) * 2.54, DEVKIT_Y0 + 3.0, 90, 0.8, "F.SilkS"))
for n in range(23, 45):
    SILK_TEXT.append((DEVKIT_PINS[n].replace("IO", ""), DEVKIT_X0 - (44 - n) * 2.54, DEVKIT_ROW2_Y - 3.0, 90, 0.8, "F.SilkS"))
# ATX pin labels (Fab layer, between the rows)
for pin, name in {8: "PWROK", 9: "5VSB", 10: "12V", 11: "12V", 16: "PSON", 17: "GND"}.items():
    SILK_TEXT.append((name, ATX_X1 - 4.2 * ((pin - 1) % 12), ATX_Y1 - 2.75, 90, 0.7, "F.Fab"))

PREROUTES = []
# no copper pour under / around the DevKit antenna (right end of the DevKit)
KEEPOUTS = [("antenna_keepout", DEVKIT_X0 - 5.2, DEVKIT_Y0 - 1.7, BOARD_W, DEVKIT_ROW2_Y + 1.7)]

# ----------------------------------------------------------------------------
# schematic (A4)
# ----------------------------------------------------------------------------
SCH_PAPER = "A4"
SCH_NOTES_Y = 182.88
SCH_PLACE = {
    "U1": ("custom", "ESP32-S3-DevKitC-1", 55.88, 96.52, 0),
    "J1": ("custom", "ATX24", 137.16, 45.72, 0),
    "Q1": ("Transistor_FET", "AO3400A", 205.74, 55.88, 0),
    "R1": ("Device", "R", 187.96, 48.26, 0),
    "R2": ("Device", "R", 114.3, 101.6, 0),
    "R3": ("Device", "R", 129.54, 101.6, 0),
    "R4": ("Device", "R", 144.78, 101.6, 180),
    "R6": ("Device", "R", 160.02, 101.6, 0),
    "D2": ("Diode", "1N4148W", 205.74, 96.52, 0),
    "C4": ("Device", "C", 220.98, 101.6, 0),
    "C1": ("Device", "C", 236.22, 101.6, 0),
    "J2": ("Connector_Generic", "Conn_01x08", 264.16, 30.48, 0),
    "J4": ("Connector_Generic", "Conn_01x04", 264.16, 55.88, 0),
    "J5": ("Connector_Generic", "Conn_01x03", 264.16, 73.66, 0),
    "J6": ("Connector_Generic", "Conn_01x03", 264.16, 88.9, 0),
    "J7": ("Connector_Generic", "Conn_01x03", 264.16, 104.14, 0),
    "J8": ("Connector_Generic", "Conn_01x04", 264.16, 121.92, 0),
    "H1": ("Mechanical", "MountingHole", 38.1, 165.1, 0),
    "H2": ("Mechanical", "MountingHole", 53.34, 165.1, 0),
}
SCH_USE_POWER_SYMBOL = {"Q1", "R1", "R3", "R4", "C1", "C4", "D2"}
SCH_TEXT_SCH = {
    "U1": (0, -33.02, 0, 33.02, None),
    "J1": (0, -20.32, 0, 20.32, None),
    "Q1": (7.62, -2.54, 7.62, 0, "left"),
    "D2": (0, -2.8, 0, 2.8, None),
}
SCH_PWR_FLAGS = {"LED_VDD": (220.98, 83.82)}
SCH_NOTES = [
    "BC250 Front Controller - ESP32-S3 DevKitC-1 mini (66 x 50 mm)",
    "PSU ATX 24-pin plug -> J1.  5VSB -> DevKit 5V pin (its own LDO makes 3V3).  12V only feeds the fan header.",
    "Q1 pulls PS_ON low (PSU ON) while GPIO4 is HIGH or floating (R1 pull-up) -> PSU stays on when the ESP32 is dead.",
    "GPIO4 LOW -> PSU off.  Same polarity as the relay-module wiring: keep  relay_inverted: \"true\"  in the yaml.",
    "PWR_OK 5V -> R2 10k / R3 20k -> 3.3 V -> GPIO5.   DS18B20 x2 on GPIO7 (R4).   FAN TACH -> R6 10k -> GPIO11.",
    "J7 5V pin is fed through D2 (~4.3 V) so a 3.3 V data line is a valid HIGH for a WS2812B.  J2 = ST7789 via wires.",
]
