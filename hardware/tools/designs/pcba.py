"""
bc250-front-pcba : fully assembled (JLCPCB PCBA) version of the BC250 front controller.

Differences from the DevKit carrier (designs built into gen_pcb.py):
  * ESP32-S3-WROOM-1 module soldered on the board, native USB-C for flashing/logs
  * relay replaced by an N-MOSFET (AO3400A) pulling PS_ON low; gate pulled up to 3V3
    -> PSU is ON whenever the ESP32 is dead/resetting (same fail-safe), and the
       firmware polarity is the same as the off-the-shelf relay module (relay_inverted: "true")
  * all passives 0603/0805 SMD, on-board WS2812B status LED (optional), BOOT/RESET buttons
  * the ESP32 module, the display socket and the 5050 LED are hand-soldered by the user so that
    JLCPCB can use *Economic* assembly (the module and 5050 LEDs are "Standard only" parts)
  * one 1x8 female socket serves both the ST7789 (8 pins) and the SSD1306 OLED (first 4 pins)
  * T2 sensor header can be moved from the shared 1-wire bus (GPIO7) to GPIO2 with a solder
    jumper, which also makes both channels usable as NTC thermistor ADC inputs
GPIO numbers are identical to the DevKit wiring, so the existing ESPHome yamls work unchanged.
"""
import os, sys, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sexp import Sym, find, find_all, parse, num

PROJECT = "bc250-front-pcba"
TITLE = "BC250 Front Controller - ESP32-S3 PCBA"
REV = "1.0"
DATE = "2026-08-25"
BOARD_W, BOARD_H = 90.0, 56.0
CORNER_R = 3.0

NET_NAMES = [
    "", "GND", "+5V", "+3V3", "+12V", "VBUS", "PS_ON", "PWR_OK", "PWR_OK_SENSE",
    "RELAY_CTRL", "BTN_PWR", "BTN_A", "BTN_B", "OW", "OW2", "T2_SIG",
    "SDA_MOSI", "SCL_SCK", "LCD_DC", "LCD_RST", "LCD_CS", "LCD_BL",
    "FAN_PWM", "FAN_TACH", "LED_DIN", "LED_VDD",
    "EN", "IO0", "USB_DP", "USB_DN", "CC1", "CC2", "TXD0", "RXD0",
]
POWER_NETS = ["GND", "+5V", "+12V"]
FINE_NETS = ["CC1", "CC2", "USB_DP", "USB_DN"]

# ----------------------------------------------------------------------------
# footprints: KiCad library name for each footprint file we use
# ----------------------------------------------------------------------------
FP_LIB_OF = {
    "ESP32-S3-WROOM-1": "RF_Module",
    "Molex_Mini-Fit_Jr_5566-24A_2x12_P4.20mm_Vertical": "Connector_Molex",
    "SOT-223-3_TabPin2": "Package_TO_SOT_SMD",
    "SOT-23": "Package_TO_SOT_SMD",
    "D_SOD-123": "Diode_SMD",
    "R_0603_1608Metric": "Resistor_SMD",
    "C_0603_1608Metric": "Capacitor_SMD",
    "C_0805_2012Metric": "Capacitor_SMD",
    "LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm": "LED_SMD",
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": "Connector_USB",
    "SolderJumper-3_P1.3mm_Bridged12_Pad1.0x1.5mm": "Jumper",
    "PinHeader_1x03_P2.54mm_Vertical": "Connector_PinHeader_2.54mm",
    "PinHeader_1x04_P2.54mm_Vertical": "Connector_PinHeader_2.54mm",
    "PinSocket_1x08_P2.54mm_Vertical": "Connector_PinSocket_2.54mm",
    "MountingHole_3.2mm_M3": "MountingHole",
}

# XKB TS-1187A-B-A-B: 5.1 x 5.1 mm, 4 side leads.  Pad positions from the JLCPCB/EasyEDA
# footprint (SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5): pads at x=+-3.00, y=+-1.85, 1.0x0.75 mm.
# Pins 1-2 (same row, y=-1.85) are one contact, 3-4 the other; the switch closes between rows.
TACT_PAD_X, TACT_PAD_Y = 3.0, 1.85           # pad centre offsets
TACT_PAD_W, TACT_PAD_H = 1.1, 0.8

def _uid():
    import uuid
    return str(uuid.uuid4())

def _line(x1, y1, x2, y2, layer, w=0.12):
    return [Sym("fp_line"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
            [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]],
            [Sym("layer"), layer], [Sym("uuid"), _uid()]]

def _rect(x1, y1, x2, y2, layer, w=0.1):
    return [Sym("fp_rect"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
            [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]],
            [Sym("fill"), Sym("no")], [Sym("layer"), layer], [Sym("uuid"), _uid()]]

def _prop(key, val, x, y, layer, hide=False):
    e = [Sym("property"), key, val, [Sym("at"), x, y, 0], [Sym("layer"), layer]]
    if hide:
        e.append([Sym("hide"), Sym("yes")])
    e += [[Sym("uuid"), _uid()], [Sym("effects"), [Sym("font"), [Sym("size"), 1, 1], [Sym("thickness"), 0.15]]]]
    return e

def make_tact_fp():
    fp = [Sym("footprint"), "SW_TS-1187A", [Sym("layer"), "F.Cu"],
          [Sym("descr"), "XKB TS-1187A-B-A-B 5.1x5.1mm SMD tactile switch (LCSC C318884)"],
          [Sym("tags"), "tact switch smd"], [Sym("attr"), Sym("smd")],
          _prop("Reference", "REF**", 0, -4.0, "F.SilkS"), _prop("Value", "SW_TS-1187A", 0, 4.0, "F.Fab"),
          _prop("Datasheet", "", 0, 0, "F.Fab", True), _prop("Description", "", 0, 0, "F.Fab", True)]
    for num_, (x, y) in (("1", (-TACT_PAD_X, -TACT_PAD_Y)), ("1", (TACT_PAD_X, -TACT_PAD_Y)),
                         ("2", (-TACT_PAD_X, TACT_PAD_Y)), ("2", (TACT_PAD_X, TACT_PAD_Y))):
        fp.append([Sym("pad"), num_, Sym("smd"), Sym("roundrect"), [Sym("at"), x, y], [Sym("size"), TACT_PAD_W, TACT_PAD_H],
                   [Sym("layers"), "F.Cu", "F.Paste", "F.Mask"], [Sym("roundrect_rratio"), 0.2], [Sym("uuid"), _uid()]])
    h = 2.55
    fp.append(_rect(-h, -h, h, h, "F.Fab"))
    fp.append([Sym("fp_circle"), [Sym("center"), 0, 0], [Sym("end"), 1.5, 0],
               [Sym("stroke"), [Sym("width"), 0.1], [Sym("type"), Sym("solid")]], [Sym("fill"), Sym("no")],
               [Sym("layer"), "F.Fab"], [Sym("uuid"), _uid()]])
    fp.append(_line(-1.4, -2.7, 1.4, -2.7, "F.SilkS"))
    fp.append(_line(-1.4, 2.7, 1.4, 2.7, "F.SilkS"))
    fp.append(_rect(-3.5, -2.9, 3.5, 2.9, "F.CrtYd", 0.05))
    return fp

def make_esp32_fp():
    """KiCad's ESP32-S3-WROOM-1 with the huge antenna courtyard replaced by the module outline.
    The board keeps the antenna free of copper via a rule area; the module sits at the board edge."""
    kicad_fp = os.environ.get("KICAD_FP") or os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
    fp = parse(open(os.path.join(kicad_fp, "RF_Module.pretty", "ESP32-S3-WROOM-1.kicad_mod")).read())[0]
    fp[1] = "ESP32-S3-WROOM-1_edge"
    keep = []
    for e in fp:
        if isinstance(e, list) and e and e[0] in ("fp_line", "fp_rect", "fp_poly", "fp_circle", "fp_arc"):
            ly = find(e, "layer")
            if ly and ly[1] == "F.CrtYd":
                continue
        keep.append(e)
    fp = keep
    for pad in find_all(fp, "pad"):
        dr = find(pad, "drill")
        if dr is not None and num(dr[1]) is not None and num(dr[1]) < 0.3:
            dr[1] = 0.3
            sz = find(pad, "size")
            sz[1], sz[2] = 0.6, 0.6
    fp.append(_rect(-9.75, -13.25, 9.75, 13.25, "F.CrtYd", 0.05))
    return fp

CUSTOM_FOOTPRINTS = {"SW_TS-1187A": make_tact_fp, "ESP32-S3-WROOM-1_edge": make_esp32_fp}

# ----------------------------------------------------------------------------
# placement (mm, origin top-left, y down)
# ----------------------------------------------------------------------------
ESP_X, ESP_Y = 14.0, 33.0        # module centre; rot 90 -> antenna points to the left board edge
ATX_X1, ATX_Y1 = 66.0, 11.5      # ATX pin 1; rot 180 -> latch ramp toward the top edge
BOT_Y = 52.0
SW_Y = 41.5

ESP_NETS = {
    1: "GND", 2: "+3V3", 3: "EN", 4: "RELAY_CTRL", 5: "PWR_OK_SENSE", 6: "BTN_PWR", 7: "OW",
    8: "LCD_DC", 9: "LCD_RST", 10: "LCD_CS", 11: "LCD_BL", 12: "SDA_MOSI", 13: "USB_DN", 14: "USB_DP",
    17: "SCL_SCK", 18: "FAN_PWM", 19: "FAN_TACH", 20: "BTN_A", 21: "BTN_B", 25: "LED_DIN",
    27: "IO0", 36: "RXD0", 37: "TXD0", 38: "OW2", 40: "GND", 41: "GND",
}
ATX_NETS = {8: "PWR_OK", 9: "+5V", 10: "+12V", 11: "+12V", 16: "PS_ON",
            3: "GND", 5: "GND", 7: "GND", 15: "GND", 17: "GND", 18: "GND", 19: "GND", 24: "GND"}
USB_NETS = {"A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "A4": "VBUS", "B4": "VBUS", "A9": "VBUS", "B9": "VBUS",
            "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN", "SH": "GND"}

R0603 = "R_0603_1608Metric"
C0603 = "C_0603_1608Metric"
C0805 = "C_0805_2012Metric"

COMPONENTS = [
    ("U1", "ESP32-S3-WROOM-1_edge", "ESP32-S3-WROOM-1-N16R8", ESP_X, ESP_Y, 90, ESP_NETS,
     "ESP32-S3 WiFi module (N4/N8/N8R2 also fine)"),
    ("J1", "Molex_Mini-Fit_Jr_5566-24A_2x12_P4.20mm_Vertical", "ATX 24-pin", ATX_X1, ATX_Y1, 180, ATX_NETS,
     "ATX 24-pin header - the PSU plug goes here"),
    ("U2", "SOT-223-3_TabPin2", "AMS1117-3.3", 74.5, 10.0, 0, {1: "GND", 2: "+3V3", 3: "+5V"}, "3.3 V LDO"),
    ("C1", C0805, "10uF", 71.0, 16.0, 0, {1: "+5V", 2: "GND"}, "LDO input"),
    ("C2", C0805, "10uF", 77.0, 16.0, 0, {1: "+3V3", 2: "GND"}, "LDO output"),
    ("Q1", "SOT-23", "AO3400A", 50.0, 17.8, 0, {1: "RELAY_CTRL", 2: "GND", 3: "PS_ON"},
     "N-MOSFET pulls PS_ON low (PSU on); gate pulled up -> fail-safe on"),
    ("R1", R0603, "10k", 45.0, 17.5, 0, {1: "RELAY_CTRL", 2: "+3V3"}, "gate pull-up (PSU on while ESP32 is dead)"),
    ("R2", R0603, "10k", 40.5, 17.5, 0, {1: "PWR_OK", 2: "PWR_OK_SENSE"}, "PWR_OK divider top"),
    ("R3", R0603, "10k", 40.5, 20.5, 0, {1: "PWR_OK_SENSE", 2: "GND"}, "PWR_OK divider bottom"),
    ("R7", R0603, "10k", 38.5, 23.5, 0, {1: "IO0", 2: "+3V3"}, "BOOT strap pull-up"),
    ("SW4", "SW_TS-1187A", "BOOT", 32.0, 23.0, 0, {1: "IO0", 2: "GND"}, "hold at reset to enter the bootloader"),
    ("SW5", "SW_TS-1187A", "RESET", 32.0, 30.0, 0, {1: "EN", 2: "GND"}, "ESP32 reset"),
    ("J9", "PinHeader_1x03_P2.54mm_Vertical", "UART0", 29.5, 38.5, 90, {1: "TXD0", 2: "RXD0", 3: "GND"},
     "debug UART (not populated)"),
    ("C3", C0603, "100nF", 9.5, 45.5, 0, {1: "+3V3", 2: "GND"}, "module decoupling"),
    ("C6", C0805, "10uF", 13.5, 45.5, 0, {1: "+3V3", 2: "GND"}, "module bulk"),
    ("C5", C0603, "1uF", 13.5, 48.5, 0, {1: "EN", 2: "GND"}, "EN reset delay"),
    ("R6", R0603, "10k", 9.5, 48.5, 0, {1: "EN", 2: "+3V3"}, "EN pull-up"),
    ("J3", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", "USB-C", 32.0, 51.5, 0, USB_NETS, "USB-C (native USB: flash + logs)"),
    ("R8", R0603, "5.1k", 39.2, 46.6, 0, {1: "CC1", 2: "GND"}, "CC pull-down"),
    ("R9", R0603, "5.1k", 39.2, 49.2, 0, {1: "CC2", 2: "GND"}, "CC pull-down"),
    ("D1", "D_SOD-123", "B5819W", 31.5, 43.6, 0, {1: "+5V", 2: "VBUS"}, "USB power ORing (K = +5V)"),
    ("SW1", "SW_TS-1187A", "PWR", 40.0, SW_Y, 0, {1: "BTN_PWR", 2: "GND"}, "power button"),
    ("SW2", "SW_TS-1187A", "MENU A", 48.0, SW_Y, 0, {1: "BTN_A", 2: "GND"}, "menu navigate"),
    ("SW3", "SW_TS-1187A", "MENU B", 56.0, SW_Y, 0, {1: "BTN_B", 2: "GND"}, "menu select"),
    ("LED1", "LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm", "WS2812B", 66.0, 30.0, 0,
     {1: "LED_VDD", 3: "GND", 4: "LED_DIN"}, "status LED (optional, hand-soldered); J7 gets the same data line"),
    ("D2", "D_SOD-123", "1N4148W", 66.0, 23.5, 0, {1: "LED_VDD", 2: "+5V"}, "drops LED VDD to ~4.3 V so 3.3 V data is valid"),
    ("C4", C0603, "100nF", 71.5, 30.0, 0, {1: "LED_VDD", 2: "GND"}, "LED decoupling"),
    ("J2", "PinSocket_1x08_P2.54mm_Vertical", "LCD / OLED", 85.0, 20.0, 0,
     {1: "GND", 2: "+3V3", 3: "SCL_SCK", 4: "SDA_MOSI", 5: "LCD_RST", 6: "LCD_DC", 7: "LCD_CS", 8: "LCD_BL"},
     "ST7789 8-pin module, or SSD1306 OLED on pins 1-4"),
    ("JP1", "SolderJumper-3_P1.3mm_Bridged12_Pad1.0x1.5mm", "T2 sel", 67.5, 44.5, 0,
     {1: "OW", 2: "T2_SIG", 3: "OW2"}, "T2: 1-2 shared 1-wire bus GPIO7 (default) / 2-3 GPIO2"),
    ("R4", R0603, "4.7k", 62.5, 44.5, 0, {1: "OW", 2: "+3V3"}, "1-wire / NTC pull-up ch1"),
    ("R5", R0603, "4.7k", 72.5, 44.5, 0, {1: "OW2", 2: "+3V3"}, "1-wire / NTC pull-up ch2"),
    ("J8", "PinHeader_1x04_P2.54mm_Vertical", "PANEL", 41.0, BOT_Y, 90, {1: "BTN_PWR", 2: "BTN_A", 3: "BTN_B", 4: "GND"},
     "front-panel buttons: PWR A B GND"),
    ("J7", "PinHeader_1x03_P2.54mm_Vertical", "LED", 52.5, BOT_Y, 90, {1: "+5V", 2: "LED_DIN", 3: "GND"},
     "external WS2812 (parallel to LED1, shows pixel 0): 5V DIN GND"),
    ("J5", "PinHeader_1x03_P2.54mm_Vertical", "T1", 61.5, BOT_Y, 90, {1: "GND", 2: "OW", 3: "+3V3"},
     "temp sensor 1 (DS18B20 or NTC): GND SIG 3V3"),
    ("J6", "PinHeader_1x03_P2.54mm_Vertical", "T2", 70.5, BOT_Y, 90, {1: "GND", 2: "T2_SIG", 3: "+3V3"},
     "temp sensor 2 (DS18B20 or NTC): GND SIG 3V3"),
    ("J4", "PinHeader_1x04_P2.54mm_Vertical", "FAN", 79.3, BOT_Y, 90, {1: "GND", 2: "+12V", 3: "FAN_TACH", 4: "FAN_PWM"},
     "4-pin PWM fan: GND 12V TACH PWM"),
    ("H1", "MountingHole_3.2mm_M3", "M3", 4.0, 4.5, 0, {}, "mounting hole"),
    ("H2", "MountingHole_3.2mm_M3", "M3", 85.5, 4.5, 0, {}, "mounting hole"),
    ("H3", "MountingHole_3.2mm_M3", "M3", 3.5, 47.5, 0, {}, "mounting hole"),
    ("H4", "MountingHole_3.2mm_M3", "M3", 86.5, 45.0, 0, {}, "mounting hole"),
]
DNP = {"J9"}

# LCSC part numbers for JLCPCB assembly ('' = not assembled)
LCSC = {
    "U1": "C2913202", "J1": "C114088", "U2": "C6186", "C1": "C15850", "C2": "C15850", "C6": "C15850",
    "Q1": "C20917", "R1": "C25804", "R2": "C25804", "R3": "C25804", "R6": "C25804", "R7": "C25804",
    "R4": "C23162", "R5": "C23162", "R8": "C23186", "R9": "C23186",
    "C3": "C14663", "C4": "C14663", "C5": "C15849",
    "SW1": "C318884", "SW2": "C318884", "SW3": "C318884", "SW4": "C318884", "SW5": "C318884",
    "J3": "C165948", "D1": "C8598", "D2": "C81598", "LED1": "C2761795",
    "J2": "C27438", "J4": "C124378", "J8": "C124378", "J5": "C49257", "J6": "C49257", "J7": "C49257",
    "JP1": "", "J9": "", "H1": "", "H2": "", "H3": "", "H4": "",
}
# parts the user solders (excluded from the default JLCPCB BOM/CPL; jlc_export --full includes them)
ASSEMBLE_EXCLUDE = {"U1", "J2", "LED1"}
BASIC_PARTS = {"C6186", "C15850", "C20917", "C25804", "C23162", "C23186", "C14663", "C15849", "C8598", "C81598", "C318884"}

# text overrides (footprint-local coords): ref -> {"Reference"/"Value": (x, y, rot, layer)}
TEXT_POS = {
    "J1": {"Reference": (23.1, 2.75, 0, None), "Value": (10.0, 2.75, 0, None)},
    "J2": {"Reference": (2.7, 8.89, 90, None)},
    "U1": {"Reference": (0, 0, 0, "F.Fab"), "Value": (0, 2.0, 0, "F.Fab")},
}
HIDE_REF = {"H1", "H2", "H3", "H4", "J4", "J5", "J6", "J7", "J8", "J9", "SW1", "SW2", "SW3", "SW4", "SW5", "JP1",
            "LED1", "D1", "D2", "J3"}

def _row(x0, y, names, dy=-3.3, size=0.8):
    return [(n, x0 + 2.54 * i, y + dy, 90, size, "F.SilkS") for i, n in enumerate(names)]

SILK_TEXT = []
SILK_TEXT += _row(79.3, BOT_Y, ["GND", "12V", "TAC", "PWM"])
SILK_TEXT += _row(61.5, BOT_Y, ["GND", "SIG", "3V3"])
SILK_TEXT += _row(70.5, BOT_Y, ["GND", "SIG", "3V3"])
SILK_TEXT += _row(52.5, BOT_Y, ["5V", "DIN", "GND"])
SILK_TEXT += _row(41.0, BOT_Y, ["PWR", "A", "B", "GND"])
SILK_TEXT += [
    ("FAN", 83.1, BOT_Y + 2.7, 0, 0.8, "F.SilkS"),
    ("T1", 64.0, BOT_Y + 2.7, 0, 0.8, "F.SilkS"),
    ("T2", 73.0, BOT_Y + 2.7, 0, 0.8, "F.SilkS"),
    ("LED", 55.0, BOT_Y + 2.7, 0, 0.8, "F.SilkS"),
    ("PANEL", 44.8, BOT_Y + 2.7, 0, 0.8, "F.SilkS"),
    ("PWR", 40.0, SW_Y - 4.6, 0, 1.0, "F.SilkS"),
    ("A", 48.0, SW_Y - 4.6, 0, 1.0, "F.SilkS"),
    ("B", 56.0, SW_Y - 4.6, 0, 1.0, "F.SilkS"),
    ("BOOT", 32.0, 18.6, 0, 0.9, "F.SilkS"),
    ("RST", 32.0, 34.5, 0, 0.9, "F.SilkS"),
    ("UART", 33.5, 41.9, 0, 0.8, "F.SilkS"),
    ("USB", 27.6, 44.0, 0, 0.8, "F.SilkS"),
    ("STATUS", 66.0, 35.0, 0, 0.8, "F.SilkS"),
    ("7 <   > 2", 67.5, 42.2, 0, 0.8, "F.SilkS"),
    ("LCD / OLED", 81.5, 17.6, 0, 0.8, "F.SilkS"),
    ("ATX 24-pin  <- PSU plug", 43.0, 1.5, 0, 0.9, "F.SilkS"),
    ("BC250 Front Controller PCBA v1.0", 49.0, 33.2, 0, 1.0, "F.SilkS"),
    ("github.com/LeeHueeng/bc250-front-controller", 44.0, 28.0, 0, 1.0, "B.SilkS"),
    ("CHECK 5V / 12V PINS BEFORE FITTING SENSORS", 44.0, 31.0, 0, 0.9, "B.SilkS"),
]
for i, n in enumerate(["GND", "VCC", "SCL", "SDA", "RES", "DC", "CS", "BL"]):
    SILK_TEXT.append((n, 82.1, 20.0 + 2.54 * i, 0, 0.8, "F.SilkS"))
for pin, name in {8: "PWROK", 9: "5VSB", 10: "12V", 11: "12V", 16: "PSON", 17: "GND"}.items():
    SILK_TEXT.append((name, ATX_X1 - 4.2 * ((pin - 1) % 12), ATX_Y1 - 2.75, 90, 0.7, "F.Fab"))

# USB-C D+/D- pad pairs are 0.5 mm apart and interleaved; bridge them with locked 0.2 mm tracks
# (outside the pad row for D+, inside for D-) so the autorouter only needs one route per net.
_JX, _JY = 32.0, 51.5
_PY = _JY - 4.045
PREROUTES = [
    # D+ : A6 (x-0.25) <-> B6 (x+0.75) bridged outside the pad row, then to module pad 14 (25.25, 41.75)
    ("USB_DP", "F.Cu", 0.25, [(_JX - 0.25, _PY), (_JX - 0.25, _PY - 1.1), (_JX + 0.75, _PY - 1.1), (_JX + 0.75, _PY)]),
    ("USB_DP", "F.Cu", 0.25, [(_JX + 0.25, _PY - 1.1), (_JX + 0.25, 45.3), (25.25, 45.3), (25.25, 42.2)]),
    # D- : A7 (x+0.25) <-> B7 (x-0.75) bridged inside (under the connector), around the shell pads
    # on the left, up to module pad 13 (23.98, 41.75)
    ("USB_DN", "F.Cu", 0.25, [(_JX + 0.25, _PY), (_JX + 0.25, _PY + 1.15), (_JX - 0.75, _PY + 1.15), (_JX - 0.75, _PY)]),
    ("USB_DN", "F.Cu", 0.25, [(_JX - 0.75, _PY + 1.15), (_JX - 0.75, 50.4), (24.6, 50.4), (24.6, 43.4), (23.98, 43.4), (23.98, 42.2)]),
]

# copper keep-out under the module antenna (module antenna end is at x = ESP_X - 12.75)
KEEPOUTS = [("antenna_keepout", 0.0, ESP_Y - 11.5, ESP_X - 12.75 + 7.0, ESP_Y + 11.5)]

# ----------------------------------------------------------------------------
# schematic (A3)
# ----------------------------------------------------------------------------
SCH_PAPER = "A3"
SCH_NOTES_Y = 262.0
SCH_PLACE = {
    "U1": ("RF_Module", "ESP32-S3-WROOM-1", 63.5, 110.49, 0),
    "J1": ("custom", "ATX24", 154.94, 45.72, 0),
    "U2": ("Regulator_Linear", "AMS1117-3.3", 241.3, 33.02, 0),
    "C1": ("Device", "C", 223.52, 45.72, 0),
    "C2": ("Device", "C", 259.08, 45.72, 0),
    "C3": ("Device", "C", 223.52, 66.04, 0),
    "C6": ("Device", "C_Polarized" if False else "C", 259.08, 66.04, 0),
    "D1": ("Device", "D_Schottky", 289.56, 33.02, 0),
    "J3": ("Connector", "USB_C_Receptacle_USB2.0_16P", 330.2, 63.5, 0),
    "R8": ("Device", "R", 355.6, 55.88, 0),
    "R9": ("Device", "R", 368.3, 55.88, 0),
    "Q1": ("Transistor_FET", "AO3400A", 236.22, 91.44, 0),
    "R1": ("Device", "R", 218.44, 83.82, 0),
    "R2": ("Device", "R", 121.92, 152.4, 0),
    "R3": ("Device", "R", 137.16, 152.4, 0),
    "R4": ("Device", "R", 152.4, 152.4, 180),
    "R5": ("Device", "R", 167.64, 152.4, 180),
    "JP1": ("Jumper", "SolderJumper_3_Bridged12", 187.96, 165.1, 0),
    "R6": ("Device", "R", 121.92, 185.42, 0),
    "C5": ("Device", "C", 137.16, 185.42, 0),
    "R7": ("Device", "R", 152.4, 185.42, 0),
    "LED1": ("LED", "WS2812B", 254.0, 127.0, 0),
    "D2": ("Diode", "1N4148W", 236.22, 114.3, 0),
    "C4": ("Device", "C", 274.32, 127.0, 0),
    "SW4": ("Switch", "SW_Push", 218.44, 154.94, 0),
    "SW5": ("Switch", "SW_Push", 218.44, 167.64, 0),
    "SW1": ("Switch", "SW_Push", 218.44, 187.96, 0),
    "SW2": ("Switch", "SW_Push", 218.44, 200.66, 0),
    "SW3": ("Switch", "SW_Push", 218.44, 213.36, 0),
    "J2": ("Connector_Generic", "Conn_01x08", 388.62, 38.1, 0),
    "J4": ("Connector_Generic", "Conn_01x04", 388.62, 76.2, 0),
    "J5": ("Connector_Generic", "Conn_01x03", 388.62, 96.52, 0),
    "J6": ("Connector_Generic", "Conn_01x03", 388.62, 111.76, 0),
    "J7": ("Connector_Generic", "Conn_01x03", 388.62, 127.0, 0),
    "J8": ("Connector_Generic", "Conn_01x04", 388.62, 147.32, 0),
    "J9": ("Connector_Generic", "Conn_01x03", 388.62, 167.64, 0),
    "H1": ("Mechanical", "MountingHole", 40.64, 220.98, 0),
    "H2": ("Mechanical", "MountingHole", 55.88, 220.98, 0),
    "H3": ("Mechanical", "MountingHole", 71.12, 220.98, 0),
    "H4": ("Mechanical", "MountingHole", 86.36, 220.98, 0),
}
SCH_USE_POWER_SYMBOL = {"U2", "C1", "C2", "D1", "Q1", "R1", "R3", "R4", "R5", "R6", "R7", "C3", "C4", "C5", "C6",
                        "SW1", "SW2", "SW3", "SW4", "SW5", "LED1", "D2", "R8", "R9"}
SCH_TEXT_SCH = {
    "U1": (0, -30.48, 0, 30.48, None),
    "J1": (0, -20.32, 0, 20.32, None),
    "J3": (0, -25.4, 0, 25.4, None),
    "U2": (0, -6.35, 0, 5.08, None),
    "D1": (0, -2.8, 0, 2.8, None), "D2": (0, -2.8, 0, 2.8, None),
    "Q1": (7.62, -2.54, 7.62, 0, "left"),
    "LED1": (10.16, -3.81, 10.16, 5.08, "left"),
    "JP1": (0, -6.35, 0, 5.08, None),
    "SW1": (0, -4.2, 0, 2.8, None), "SW2": (0, -4.2, 0, 2.8, None), "SW3": (0, -4.2, 0, 2.8, None),
    "SW4": (0, -4.2, 0, 2.8, None), "SW5": (0, -4.2, 0, 2.8, None),
}
SCH_PWR_FLAGS = {"LED_VDD": (287.02, 121.92), "VBUS": (322.58, 33.02)}
SCH_NOTES = [
    "BC250 Front Controller - ESP32-S3 PCBA (fully assembled at JLCPCB)",
    "PSU ATX 24-pin plug -> J1.  5VSB feeds the 5V rail and U2 (3V3) at all times; VBUS only through D1.",
    "Q1 pulls PS_ON low (PSU ON) while GPIO4 is HIGH or floating (R1 pull-up) -> PSU stays on when the ESP32 is dead.",
    "GPIO4 LOW -> PSU off.  Same polarity as the relay-module wiring: keep  relay_inverted: \"true\"  in the yaml.",
    "PWR_OK 5V -> R2/R3 -> GPIO5.  T1 on GPIO7 (R4 pull-up); T2 on GPIO7 via JP1 1-2 (default) or GPIO2 via JP1 2-3 (R5).",
    "Both temp inputs work as DS18B20 (1-wire) or as 10k NTC (ADC, 4.7k reference) - see README.",
    "J2: ST7789 module on pins 1-8, or SSD1306 OLED on pins 1-4 (GND VCC SCL SDA).  J7 = external WS2812 in parallel with LED1.",
    "Hand-soldered by the user (not in the JLCPCB BOM): U1 module, J2 socket, LED1.  Everything else is Economic-assembly eligible.",
]

# only these C-numbers are also in the 'extra places' lists JLCPCB treats as basic - informational
