#!/usr/bin/env python3
"""
Generate the BC250 front-controller carrier PCB (KiCad project) from a
parametric description.  Footprints come from the official KiCad library
(downloaded .kicad_mod files in ./fp) plus a generated ESP32-S3-DevKitC-1 socket.

Outputs (in --out-dir):
  bc250-front-carrier.kicad_pcb   unrouted board with nets
  bc250-front-carrier.kicad_pro   project (net classes, DRC rules)
  bc250-front-carrier.pretty/     project footprint library (self-contained)
  fp-lib-table                    points the project at that library
"""
import os, sys, uuid, math, copy, argparse, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, dump, Sym, find, find_all, num

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = "bc250-front-carrier"
FP_LIB = PROJECT                       # project-local footprint library nickname
# footprint sources: the project library (KiCad-library copies + generated footprints),
# then the KiCad application libraries (<Lib>.pretty/<Name>.kicad_mod)
FP_DIR = os.environ.get("FP_DIR") or os.path.join(HERE, "..", PROJECT, PROJECT + ".pretty")
KICAD_FP = os.environ.get("KICAD_FP") or os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
CUSTOM_FOOTPRINTS = {}      # name -> builder(); filled below / by design modules

# ----------------------------------------------------------------------------
# Board parameters
# ----------------------------------------------------------------------------
BOARD_W, BOARD_H = 96.0, 64.0
CORNER_R = 3.0
TITLE = "BC250 Front Controller - ESP32-S3 DevKitC-1 carrier"
REV = "1.0"
DATE = "2026-08-25"

# In KiCad board files pad / text angles are stored as *absolute* angles
# (footprint rotation + local angle) while positions stay local.
ABS_ANGLES = True

# Nets (index 0 must be the empty net)
NET_NAMES = [
    "", "GND", "+5V", "+3V3", "+12V", "PS_ON", "PWR_OK", "PWR_OK_SENSE",
    "RELAY_CTRL", "Q1_B", "RELAY_COIL", "BTN_PWR", "BTN_A", "BTN_B", "OW",
    "SDA_MOSI", "SCL_SCK", "LCD_DC", "LCD_RST", "LCD_CS", "LCD_BL",
    "FAN_PWM", "FAN_TACH", "LED_DIN",
]
NET_ID = {n: i for i, n in enumerate(NET_NAMES)}
POWER_NETS = ["GND", "+5V", "+12V", "PS_ON", "RELAY_COIL"]
FINE_NETS = []              # nets routed with the narrow "Fine" class (0.2 mm / 0.15 mm), e.g. USB-C pads

# ----------------------------------------------------------------------------
# ESP32-S3-DevKitC-1 pin map (socket pad number -> signal), Espressif numbering:
# pads 1..22 = left column top->bottom (antenna up), 23..44 = right column bottom->top
# ----------------------------------------------------------------------------
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
    16: "FAN_PWM", 17: "FAN_TACH", 18: "BTN_A", 19: "BTN_B", 29: "LED_DIN",
}

# ----------------------------------------------------------------------------
# Placement.  Coordinates in mm, origin = board top-left, y down.
# ----------------------------------------------------------------------------
DEVKIT_X0, DEVKIT_Y0 = 62.0, 18.0     # pad 1 (3V3); rot 270 -> USB end points left (x=0.66), antenna right
DEVKIT_ROW2_Y = DEVKIT_Y0 + 22.86
ATX_X1, ATX_Y1 = 57.5, 11.5           # pad 1; rot 180 -> latch ramp faces the top board edge
RELAY_X, RELAY_Y = 66.0, 9.5
BOT_Y = 54.0                          # bottom connector row (pin 1 x given per part, pins go +x)
SW_Y = 49.5
RES_X, RES_Y0, RES_PITCH = 66.0, 25.5, 5.0

# text overrides: ref -> {"Reference": (x, y, rot, layer) | "Value": ...}
TEXT_POS = {
    "J1": {"Reference": (23.1, 2.75, 0, None), "Value": (10.0, 2.75, 0, None)},
    "K1": {"Value": (8.1, 4.5, 0, None)},
    "Q1": {"Reference": (5.4, 0.0, 0, None)},
    "J2": {"Reference": (2.7, 8.89, 90, None)},
    "J3": {"Reference": (2.7, 3.81, 90, None)},
    "U1": {"Reference": (11.43, 30.0, 90, None), "Value": (14.5, 30.0, 90, "F.Fab")},
}
HIDE_REF = {"H1", "H2", "H3", "H4", "J4", "J5", "J6", "J7", "J8"}

COMPONENTS = [
    # ref, footprint, value, x, y, rot, {pad: net}, description
    ("U1", "ESP32-S3-DevKitC-1_Socket", "ESP32-S3-DevKitC-1", DEVKIT_X0, DEVKIT_Y0, 270,
     DEVKIT_NETS, "ESP32-S3-DevKitC-1 dev board on 2x 1x22 female headers"),
    ("J1", "Molex_Mini-Fit_Jr_5566-24A_2x12_P4.20mm_Vertical", "ATX 24-pin", ATX_X1, ATX_Y1, 180,
     {8: "PWR_OK", 9: "+5V", 10: "+12V", 11: "+12V", 16: "PS_ON",
      3: "GND", 5: "GND", 7: "GND", 15: "GND", 17: "GND", 18: "GND", 19: "GND", 24: "GND"},
     "ATX 24-pin motherboard header (Molex 5566-24A / 39-28-1243); the PSU plug goes here"),
    ("K1", "Relay_SPDT_SANYOU_SRD_Series_Form_C", "SRD-05VDC-SL-C", RELAY_X, RELAY_Y, 0,
     {1: "PS_ON", 4: "GND", 2: "+5V", 5: "RELAY_COIL"},
     "5V SPDT relay; COM=PS_ON, NC=GND (fail-safe: PSU stays on when ESP32 is dead)"),
    ("Q1", "TO-92_Inline", "S8050", 69.0, 20.4, 0,
     {1: "GND", 2: "Q1_B", 3: "RELAY_COIL"}, "NPN relay driver, pins E-B-C"),
    ("D1", "D_DO-35_SOD27_P7.62mm_Horizontal", "1N4148", 76.5, 21.0, 0,
     {1: "+5V", 2: "RELAY_COIL"}, "relay flyback diode (cathode band = pin 1 = +5V)"),
    ("R1", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", "1k", RES_X, RES_Y0 + 0 * RES_PITCH, 0,
     {1: "RELAY_CTRL", 2: "Q1_B"}, "base resistor"),
    ("R2", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", "10k", RES_X, RES_Y0 + 1 * RES_PITCH, 0,
     {1: "Q1_B", 2: "GND"}, "base pull-down (relay stays off while ESP32 boots)"),
    ("R3", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", "10k", RES_X, RES_Y0 + 2 * RES_PITCH, 0,
     {1: "PWR_OK", 2: "PWR_OK_SENSE"}, "PWR_OK divider top"),
    ("R4", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", "10k", RES_X, RES_Y0 + 3 * RES_PITCH, 0,
     {1: "PWR_OK_SENSE", 2: "GND"}, "PWR_OK divider bottom"),
    ("R5", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", "4.7k", RES_X, RES_Y0 + 4 * RES_PITCH, 0,
     {1: "OW", 2: "+3V3"}, "DS18B20 1-wire pull-up"),
    ("C1", "CP_Radial_D5.0mm_P2.00mm", "100uF", 79.0, 27.0, 0,
     {1: "+5V", 2: "GND"}, "5VSB bulk capacitor (relay coil)"),
    ("C2", "C_Disc_D5.0mm_W2.5mm_P2.50mm", "100nF", 78.0, 34.0, 0,
     {1: "+5V", 2: "GND"}, "5V decoupling"),
    ("J2", "PinSocket_1x08_P2.54mm_Vertical", "ST7789 LCD", 92.0, 19.5, 0,
     {1: "GND", 2: "+3V3", 3: "SCL_SCK", 4: "SDA_MOSI", 5: "LCD_RST", 6: "LCD_DC", 7: "LCD_CS", 8: "LCD_BL"},
     "ST7789V 2.4in SPI module: GND VCC SCL SDA RES DC CS BL"),
    ("J3", "PinSocket_1x04_P2.54mm_Vertical", "SSD1306 OLED", 92.0, 41.0, 0,
     {1: "GND", 2: "+3V3", 3: "SCL_SCK", 4: "SDA_MOSI"},
     "0.96in I2C OLED: GND VCC SCL SDA"),
    ("J4", "PinHeader_1x04_P2.54mm_Vertical", "FAN", 82.0, BOT_Y, 90,
     {1: "GND", 2: "+12V", 3: "FAN_TACH", 4: "FAN_PWM"}, "PC 4-pin PWM fan: GND 12V TACH PWM"),
    ("J5", "PinHeader_1x03_P2.54mm_Vertical", "T1 GPU", 64.0, BOT_Y, 90,
     {1: "GND", 2: "OW", 3: "+3V3"}, "DS18B20 #1 (GPU heatsink): GND DQ VDD"),
    ("J6", "PinHeader_1x03_P2.54mm_Vertical", "T2 CASE", 73.0, BOT_Y, 90,
     {1: "GND", 2: "OW", 3: "+3V3"}, "DS18B20 #2 (case): GND DQ VDD"),
    ("J7", "PinHeader_1x03_P2.54mm_Vertical", "WS2812", 55.0, BOT_Y, 90,
     {1: "+5V", 2: "LED_DIN", 3: "GND"}, "external WS2812 status LED: 5V DIN GND"),
    ("J8", "PinHeader_1x06_P2.54mm_Vertical", "PANEL", 9.0, BOT_Y, 90,
     {1: "BTN_PWR", 2: "GND", 3: "BTN_A", 4: "GND", 5: "BTN_B", 6: "GND"},
     "front-panel buttons: PWR GND A GND B GND"),
    ("SW1", "SW_PUSH_6mm", "PWR", 25.0, SW_Y, 0, {1: "BTN_PWR", 2: "GND"}, "power button"),
    ("SW2", "SW_PUSH_6mm", "MENU A", 35.0, SW_Y, 0, {1: "BTN_A", 2: "GND"}, "menu A (navigate)"),
    ("SW3", "SW_PUSH_6mm", "MENU B", 45.0, SW_Y, 0, {1: "BTN_B", 2: "GND"}, "menu B (select)"),
    ("H1", "MountingHole_3.2mm_M3", "M3", 4.5, 4.5, 0, {}, "mounting hole"),
    ("H2", "MountingHole_3.2mm_M3", "M3", 91.5, 4.5, 0, {}, "mounting hole"),
    ("H3", "MountingHole_3.2mm_M3", "M3", 4.5, 59.5, 0, {}, "mounting hole"),
    ("H4", "MountingHole_3.2mm_M3", "M3", 91.5, 59.5, 0, {}, "mounting hole"),
]

# ----------------------------------------------------------------------------
# Silkscreen labels: (text, x, y, rot, size, layer)
# ----------------------------------------------------------------------------
def row_labels(x0, y, names, dy=-3.3, size=0.8):
    """vertical labels above a horizontal 1xN header (pin1 at x0, pins going +x)."""
    return [(n, x0 + 2.54 * i, y + dy, 90, size, "F.SilkS") for i, n in enumerate(names)]

SILK_TEXT = []
SILK_TEXT += row_labels(82.0, BOT_Y, ["GND", "12V", "TAC", "PWM"])
SILK_TEXT += row_labels(64.0, BOT_Y, ["GND", "DQ", "3V3"])
SILK_TEXT += row_labels(73.0, BOT_Y, ["GND", "DQ", "3V3"])
SILK_TEXT += row_labels(55.0, BOT_Y, ["5V", "DIN", "GND"])
SILK_TEXT += row_labels(9.0, BOT_Y, ["PWR", "GND", "A", "GND", "B", "GND"])
SILK_TEXT += [
    ("FAN", 85.8, BOT_Y + 3.6, 0, 1.0, "F.SilkS"),
    ("T1 GPU", 66.54, BOT_Y + 3.6, 0, 1.0, "F.SilkS"),
    ("T2 CASE", 75.54, BOT_Y + 3.6, 0, 1.0, "F.SilkS"),
    ("LED", 57.54, BOT_Y + 3.6, 0, 1.0, "F.SilkS"),
    ("PANEL", 15.4, BOT_Y + 3.6, 0, 1.0, "F.SilkS"),
    ("PWR", 28.25, SW_Y - 4.1, 0, 1.0, "F.SilkS"),
    ("A", 38.25, SW_Y - 4.1, 0, 1.0, "F.SilkS"),
    ("B", 48.25, SW_Y - 4.1, 0, 1.0, "F.SilkS"),
    ("ST7789", 88.2, 17.5, 0, 0.8, "F.SilkS"),
    ("OLED", 87.9, 39.6, 0, 0.8, "F.SilkS"),
    ("COM", 66.0, 18.6, 0, 0.8, "F.SilkS"),
    ("NC", 86.3, 3.5, 0, 0.8, "F.SilkS"),
    ("NO", 86.3, 15.55, 0, 0.8, "F.SilkS"),
    ("ATX 24-pin  <- PSU plug", 34.0, 1.5, 0, 0.9, "F.SilkS"),
    ("USB", 3.2, 29.4, 90, 1.0, "F.SilkS"),
    ("BC250 Front Controller v1.0", 30.0, 43.5, 0, 1.0, "F.SilkS"),
    ("github.com/LeeHueeng/bc250-front-controller", 30.0, 29.0, 0, 1.0, "B.SilkS"),
    ("CHECK 5VSB=5V / 12V / PS_ON BEFORE FITTING ESP32", 30.0, 32.0, 0, 0.9, "B.SilkS"),
]
# LCD / OLED pin labels
for i, n in enumerate(["GND", "VCC", "SCL", "SDA", "RES", "DC", "CS", "BL"]):
    SILK_TEXT.append((n, 89.1, 19.5 + 2.54 * i, 0, 0.8, "F.SilkS"))
for i, n in enumerate(["GND", "VCC", "SCL", "SDA"]):
    SILK_TEXT.append((n, 89.1, 41.0 + 2.54 * i, 0, 0.8, "F.SilkS"))
# DevKit pin labels between the two socket rows (visible before the DevKit is fitted)
for n in range(1, 23):
    SILK_TEXT.append((DEVKIT_PINS[n].replace("IO", ""), DEVKIT_X0 - (n - 1) * 2.54, DEVKIT_Y0 + 3.0, 90, 0.8, "F.SilkS"))
for n in range(23, 45):
    SILK_TEXT.append((DEVKIT_PINS[n].replace("IO", ""), DEVKIT_X0 - (44 - n) * 2.54, DEVKIT_ROW2_Y - 3.0, 90, 0.8, "F.SilkS"))
# ATX pin labels used (between the rows, hidden by the plug but useful when probing)
for pin, name in {8: "PWROK", 9: "5VSB", 10: "12V", 11: "12V", 16: "PSON", 17: "GND"}.items():
    col = (pin - 1) % 12
    x = ATX_X1 - 4.2 * col
    SILK_TEXT.append((name, x, ATX_Y1 - 2.75, 90, 0.7, "F.Fab"))

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def uid():
    return str(uuid.uuid4())

def fp_path(name):
    """Locate a footprint file: project library first, then KiCad libs via FP_LIB_OF."""
    p = os.path.join(FP_DIR, name + ".kicad_mod")
    if os.path.exists(p):
        return p
    lib = FP_LIB_OF.get(name)
    if lib:
        p = os.path.join(KICAD_FP, lib + ".pretty", name + ".kicad_mod")
        if os.path.exists(p):
            return p
    raise FileNotFoundError("footprint not found: " + name)

def load_fp(name):
    if name in CUSTOM_FOOTPRINTS:
        return CUSTOM_FOOTPRINTS[name]()
    fp = parse(open(fp_path(name)).read())[0]
    assert fp[0] == "footprint", name
    return fp

def fp_text(kind, text, x, y, rot, layer, size=1.0, thick=0.15, hide=False):
    e = [Sym("fp_text"), Sym(kind), text, [Sym("at"), x, y, rot], [Sym("layer"), layer]]
    if hide:
        e.append([Sym("hide"), Sym("yes")])
    e += [[Sym("uuid"), uid()], [Sym("effects"), [Sym("font"), [Sym("size"), size, size], [Sym("thickness"), thick]]]]
    return e

def make_devkit_socket_fp():
    """Two 1x22 female headers, 22.86 mm apart, plus DevKit outline on F.Fab/F.SilkS.
    Local frame: pad 1 at (0,0), pads 1..22 go +y, pads 23..44 at x=22.86 going -y.
    Antenna end at y=-1.4 (top), USB end at y=61.34 (bottom)."""
    fp = [Sym("footprint"), "ESP32-S3-DevKitC-1_Socket",
          [Sym("layer"), "F.Cu"],
          [Sym("descr"), "Socket for ESP32-S3-DevKitC-1 (2x 1x22 2.54mm female headers, 22.86mm row spacing)"],
          [Sym("tags"), "ESP32-S3 DevKitC-1 socket"],
          [Sym("attr"), Sym("through_hole")]]
    def fprop(key, val, x, y, layer, hide=False):
        e = [Sym("property"), key, val, [Sym("at"), x, y, 0], [Sym("layer"), layer]]
        if hide:
            e.append([Sym("hide"), Sym("yes")])
        e += [[Sym("uuid"), uid()], [Sym("effects"), [Sym("font"), [Sym("size"), 1, 1], [Sym("thickness"), 0.15]]]]
        return e
    fp.append(fprop("Reference", "REF**", 11.43, -3.5, "F.SilkS"))
    fp.append(fprop("Value", "ESP32-S3-DevKitC-1_Socket", 11.43, 63.5, "F.Fab"))
    fp.append(fprop("Datasheet", "", 0, 0, "F.Fab", hide=True))
    fp.append(fprop("Description", "ESP32-S3-DevKitC-1 socket", 0, 0, "F.Fab", hide=True))
    for n in range(1, 45):
        if n <= 22:
            x, y = 0.0, (n - 1) * 2.54
        else:
            x, y = 22.86, (44 - n) * 2.54
        shape = "rect" if n == 1 else "oval"
        fp.append([Sym("pad"), str(n), Sym("thru_hole"), Sym(shape),
                   [Sym("at"), x, y], [Sym("size"), 1.7, 1.7],
                   [Sym("drill"), 1.0], [Sym("layers"), "*.Cu", "*.Mask"],
                   [Sym("remove_unused_layers"), Sym("no")],
                   [Sym("pinfunction"), DEVKIT_PINS[n]],
                   [Sym("uuid"), uid()]])
    def line(x1, y1, x2, y2, layer, w=0.1):
        return [Sym("fp_line"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
                [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]],
                [Sym("layer"), layer], [Sym("uuid"), uid()]]
    def rect(x1, y1, x2, y2, layer, w=0.1):
        return [Sym("fp_rect"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
                [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]],
                [Sym("fill"), Sym("no")], [Sym("layer"), layer], [Sym("uuid"), uid()]]
    x1, y1, x2, y2 = -1.27, -1.4, 24.13, 61.34
    fp.append(rect(x1, y1, x2, y2, "F.Fab"))
    fp.append(rect(x1 - 0.25, y1 - 0.25, x2 + 0.25, y2 + 0.25, "F.CrtYd", 0.05))
    fp.append(rect(x1, y1, x2, y2, "F.SilkS", 0.12))
    for sx in (0.0, 22.86):
        fp.append(rect(sx - 1.33, -1.33, sx + 1.33, 53.34 + 1.33, "F.SilkS", 0.12))
    fp.append(rect(2.4, -1.0, 20.4, 24.5, "F.Fab"))            # WROOM module 18x25.5
    fp.append(line(2.4, 5.0, 20.4, 5.0, "F.Fab"))              # antenna zone boundary
    fp.append(rect(1.0, 52.4, 9.9, 61.3, "F.Fab"))             # USB-C x2
    fp.append(rect(12.9, 52.4, 21.8, 61.3, "F.Fab"))
    fp.append(fp_text("user", "USB", 11.4, 57.0, 0, "F.Fab"))
    fp.append(fp_text("user", "ANT", 11.4, 1.5, 0, "F.Fab"))
    fp.append(fp_text("user", "${REFERENCE}", 11.4, 27.0, 90, "F.Fab"))
    fp.append(line(-1.9, -1.9, -1.9, 0.6, "F.SilkS", 0.15))    # pin 1 marker
    return fp

CUSTOM_FOOTPRINTS["ESP32-S3-DevKitC-1_Socket"] = make_devkit_socket_fp

def set_prop(fp, key, value=None, at=None, layer=None):
    for p in find_all(fp, "property"):
        if p[1] == key:
            if value is not None:
                p[2] = value
            if at is not None:
                a = find(p, "at")
                a[1], a[2] = at[0], at[1]
                if len(a) > 3:
                    a[3] = at[2]
                else:
                    a.append(at[2])
            if layer is not None:
                ly = find(p, "layer")
                ly[1] = layer
            return p
    return None

def rotate_angles(fp, rot):
    """Add footprint rotation to every pad / text angle (KiCad stores absolute angles)."""
    if not ABS_ANGLES or rot == 0:
        return
    def fix_at(node):
        at = find(node, "at")
        if at is None:
            return
        if len(at) >= 4:
            at[3] = (num(at[3]) + rot) % 360
        else:
            at.append(rot % 360)
    for pad in find_all(fp, "pad"):
        fix_at(pad)
    for p in find_all(fp, "property"):
        fix_at(p)
    for t in find_all(fp, "fp_text"):
        fix_at(t)

def strip_file_tokens(fp):
    return [e for e in fp if not (isinstance(e, list) and e and e[0] in ("version", "generator", "generator_version"))]

def instantiate(ref, fpname, value, x, y, rot, pad_nets, descr, sch_uuid):
    fp = load_fp(fpname)
    fp = strip_file_tokens(fp)
    libname = FP_LIB + ":" + fpname
    fp[1] = libname
    li = next(i for i, e in enumerate(fp) if isinstance(e, list) and e and e[0] == "layer")
    fp.insert(li + 1, [Sym("uuid"), uid()])
    fp.insert(li + 2, [Sym("at"), x, y, rot])
    set_prop(fp, "Reference", ref)
    set_prop(fp, "Value", value)
    if set_prop(fp, "Description", descr) is None:
        fp.append([Sym("property"), "Description", descr, [Sym("at"), 0, 0, 0], [Sym("unlocked"), Sym("yes")],
                   [Sym("layer"), "F.Fab"], [Sym("hide"), Sym("yes")], [Sym("uuid"), uid()],
                   [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27], [Sym("thickness"), 0.15]]]])
    fp.append([Sym("property"), "Footprint", libname, [Sym("at"), 0, 0, 0], [Sym("unlocked"), Sym("yes")],
               [Sym("layer"), "F.Fab"], [Sym("hide"), Sym("yes")], [Sym("uuid"), uid()],
               [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27], [Sym("thickness"), 0.15]]]])
    for key, (tx, ty, trot, tlayer) in TEXT_POS.get(ref, {}).items():
        set_prop(fp, key, at=(tx, ty, trot), layer=tlayer)
    if ref in HIDE_REF:
        p = set_prop(fp, "Reference")
        if find(p, "hide") is None:
            p.insert(4, [Sym("hide"), Sym("yes")])
    if ref in DNP:
        at = find(fp, "attr")
        if at is None:
            at = [Sym("attr")]
            fp.append(at)
        for flag in ("dnp", "exclude_from_bom", "exclude_from_pos_files"):
            if Sym(flag) not in at:
                at.append(Sym(flag))
    fp.append([Sym("path"), "/" + sch_uuid])
    fp.append([Sym("sheetname"), "Root"])
    fp.append([Sym("sheetfile"), PROJECT + ".kicad_sch"])
    for pad in find_all(fp, "pad"):
        pn = pad[1]
        net = pad_nets.get(pn) or (pad_nets.get(int(pn)) if pn.isdigit() else None)
        if net:
            idx = next((i for i, e in enumerate(pad) if isinstance(e, list) and e and e[0] == "uuid"), len(pad))
            pad.insert(idx, [Sym("net"), NET_ID[net], net])
    rotate_angles(fp, rot)
    return fp

# ----------------------------------------------------------------------------
# Board assembly
# ----------------------------------------------------------------------------
def edge_cuts():
    W, H, r = BOARD_W, BOARD_H, CORNER_R
    def gl(x1, y1, x2, y2):
        return [Sym("gr_line"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
                [Sym("stroke"), [Sym("width"), 0.05], [Sym("type"), Sym("default")]],
                [Sym("layer"), "Edge.Cuts"], [Sym("uuid"), uid()]]
    def ga(sx, sy, mx, my, ex, ey):
        return [Sym("gr_arc"), [Sym("start"), sx, sy], [Sym("mid"), mx, my], [Sym("end"), ex, ey],
                [Sym("stroke"), [Sym("width"), 0.05], [Sym("type"), Sym("default")]],
                [Sym("layer"), "Edge.Cuts"], [Sym("uuid"), uid()]]
    c = r * (1 - math.sqrt(0.5))
    return [
        gl(r, 0, W - r, 0), gl(W, r, W, H - r), gl(W - r, H, r, H), gl(0, H - r, 0, r),
        ga(W - r, 0, W - c, c, W, r),
        ga(W, H - r, W - c, H - c, W - r, H),
        ga(r, H, c, H - c, 0, H - r),
        ga(0, r, c, c, r, 0),
    ]

def gr_text(text, x, y, rot, size, layer="F.SilkS"):
    eff = [Sym("effects"), [Sym("font"), [Sym("size"), size, size], [Sym("thickness"), max(0.12, round(size * 0.15, 2))]]]
    if layer.startswith("B."):
        eff.append([Sym("justify"), Sym("mirror")])
    return [Sym("gr_text"), text, [Sym("at"), x, y, rot], [Sym("layer"), layer], [Sym("uuid"), uid()], eff]

def zone_gnd(layer):
    W, H = BOARD_W, BOARD_H
    return [Sym("zone"), [Sym("net"), NET_ID["GND"]], [Sym("net_name"), "GND"], [Sym("layer"), layer],
            [Sym("uuid"), uid()], [Sym("name"), "GND_" + layer], [Sym("hatch"), Sym("edge"), 0.5],
            [Sym("priority"), 0],
            [Sym("connect_pads"), [Sym("clearance"), 0.3]],
            [Sym("min_thickness"), 0.25], [Sym("filled_areas_thickness"), Sym("no")],
            [Sym("fill"), Sym("yes"), [Sym("thermal_gap"), 0.5], [Sym("thermal_bridge_width"), 0.5]],
            [Sym("polygon"), [Sym("pts"), [Sym("xy"), 0.5, 0.5], [Sym("xy"), W - 0.5, 0.5],
                                          [Sym("xy"), W - 0.5, H - 0.5], [Sym("xy"), 0.5, H - 0.5]]]]

KEEPOUTS = [("antenna_keepout", DEVKIT_X0 - 5.2, DEVKIT_Y0 - 1.7, DEVKIT_X0 + 1.9, DEVKIT_ROW2_Y + 1.7)]
DNP = set()                 # refs not populated (excluded from BOM / position files)
PREROUTES = []              # (net, layer, width, [(x, y), ...]) locked tracks placed before autorouting

def preroute_segments():
    out = []
    for net, layer, width, pts in PREROUTES:
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            out.append([Sym("segment"), [Sym("start"), x1, y1], [Sym("end"), x2, y2], [Sym("width"), width],
                        [Sym("locked"), Sym("yes")], [Sym("layer"), layer], [Sym("net"), NET_ID[net]], [Sym("uuid"), uid()]])
    return out

def zone_keepout(name, x1, y1, x2, y2):
    """Rule area: no copper pour (tracks/vias allowed) - used under WiFi antennas."""
    return [Sym("zone"), [Sym("net"), 0], [Sym("net_name"), ""], [Sym("layers"), "F&B.Cu"],
            [Sym("uuid"), uid()], [Sym("name"), name], [Sym("hatch"), Sym("edge"), 0.5],
            [Sym("connect_pads"), [Sym("clearance"), 0]], [Sym("min_thickness"), 0.25],
            [Sym("filled_areas_thickness"), Sym("no")],
            [Sym("keepout"), [Sym("tracks"), Sym("allowed")], [Sym("vias"), Sym("allowed")],
             [Sym("pads"), Sym("allowed")], [Sym("copperpour"), Sym("not_allowed")], [Sym("footprints"), Sym("allowed")]],
            [Sym("fill"), [Sym("thermal_gap"), 0.5], [Sym("thermal_bridge_width"), 0.5]],
            [Sym("polygon"), [Sym("pts"), [Sym("xy"), x1, y1], [Sym("xy"), x2, y1], [Sym("xy"), x2, y2], [Sym("xy"), x1, y2]]]]

def build_board(sch_uuids, with_zones=True):
    b = [Sym("kicad_pcb"), [Sym("version"), 20241229], [Sym("generator"), "pcbnew"], [Sym("generator_version"), "9.0"],
         [Sym("general"), [Sym("thickness"), 1.6], [Sym("legacy_teardrops"), Sym("no")]],
         [Sym("paper"), "A4"],
         [Sym("title_block"), [Sym("title"), TITLE], [Sym("date"), DATE], [Sym("rev"), REV],
          [Sym("company"), "github.com/LeeHueeng/bc250-front-controller"]],
         [Sym("layers"),
          [0, "F.Cu", Sym("signal")], [2, "B.Cu", Sym("signal")],
          [9, "F.Adhes", Sym("user"), "F.Adhesive"], [11, "B.Adhes", Sym("user"), "B.Adhesive"],
          [13, "F.Paste", Sym("user")], [15, "B.Paste", Sym("user")],
          [5, "F.SilkS", Sym("user"), "F.Silkscreen"], [7, "B.SilkS", Sym("user"), "B.Silkscreen"],
          [1, "F.Mask", Sym("user")], [3, "B.Mask", Sym("user")],
          [17, "Dwgs.User", Sym("user"), "User.Drawings"], [19, "Cmts.User", Sym("user"), "User.Comments"],
          [21, "Eco1.User", Sym("user"), "User.Eco1"], [23, "Eco2.User", Sym("user"), "User.Eco2"],
          [25, "Edge.Cuts", Sym("user")], [27, "Margin", Sym("user")],
          [31, "F.CrtYd", Sym("user"), "F.Courtyard"], [29, "B.CrtYd", Sym("user"), "B.Courtyard"],
          [35, "F.Fab", Sym("user")], [33, "B.Fab", Sym("user")]],
         [Sym("setup"),
          [Sym("pad_to_mask_clearance"), 0],
          [Sym("allow_soldermask_bridges_in_footprints"), Sym("no")],
          [Sym("tenting"), Sym("front"), Sym("back")],
          [Sym("pcbplotparams"),
           [Sym("layerselection"), Sym("0x00000000_00000000_55555555_5755f5ff")],
           [Sym("plot_on_all_layers_selection"), Sym("0x00000000_00000000_00000000_00000000")],
           [Sym("disableapertmacros"), Sym("no")], [Sym("usegerberextensions"), Sym("no")],
           [Sym("usegerberattributes"), Sym("yes")], [Sym("usegerberadvancedattributes"), Sym("yes")],
           [Sym("creategerberjobfile"), Sym("yes")], [Sym("dashed_line_dash_ratio"), 12.0],
           [Sym("dashed_line_gap_ratio"), 3.0], [Sym("svgprecision"), 4], [Sym("plotframeref"), Sym("no")],
           [Sym("mode"), 1], [Sym("useauxorigin"), Sym("no")], [Sym("hpglpennumber"), 1],
           [Sym("hpglpenspeed"), 20], [Sym("hpglpendiameter"), 15.0], [Sym("pdf_front_fp_property_popups"), Sym("yes")],
           [Sym("pdf_back_fp_property_popups"), Sym("yes")], [Sym("pdf_metadata"), Sym("yes")],
           [Sym("pdf_single_document"), Sym("no")], [Sym("dxfpolygonmode"), Sym("yes")],
           [Sym("dxfimperialunits"), Sym("yes")], [Sym("dxfusepcbnewfont"), Sym("yes")],
           [Sym("psnegative"), Sym("no")], [Sym("psa4output"), Sym("no")], [Sym("plot_black_and_white"), Sym("yes")],
           [Sym("sketchpadsonfab"), Sym("no")], [Sym("plotpadnumbers"), Sym("no")], [Sym("hidednponfab"), Sym("no")],
           [Sym("sketchdnponfab"), Sym("yes")], [Sym("crossoutdnponfab"), Sym("yes")], [Sym("subtractmaskfromsilk"), Sym("no")],
           [Sym("outputformat"), 1], [Sym("mirror"), Sym("no")], [Sym("drillshape"), 0], [Sym("scaleselection"), 1],
           [Sym("outputdirectory"), "gerbers/"]]],
         ]
    for i, n in enumerate(NET_NAMES):
        b.append([Sym("net"), i, n])
    for comp in COMPONENTS:
        ref, fpname, value, x, y, rot, pad_nets, descr = comp
        b.append(instantiate(ref, fpname, value, x, y, rot, pad_nets, descr, sch_uuids[ref]))
    b.extend(edge_cuts())
    b.extend(preroute_segments())
    for (t, x, y, rot, size, layer) in SILK_TEXT:
        b.append(gr_text(t, x, y, rot, size, layer))
    if with_zones:
        b.append(zone_gnd("B.Cu"))
        b.append(zone_gnd("F.Cu"))
        for ko in KEEPOUTS:
            b.append(zone_keepout(*ko))
    b.append([Sym("embedded_fonts"), Sym("no")])
    return b

# ----------------------------------------------------------------------------
# Project file (.kicad_pro): net classes + DRC rules (JLCPCB 2-layer capable values)
# ----------------------------------------------------------------------------
def netclass(name, width, clearance, via_d, via_drill, priority):
    return {"bus_width": 12, "clearance": clearance, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
            "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "name": name, "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": priority,
            "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": width,
            "via_diameter": via_d, "via_drill": via_drill, "wire_width": 6}

def project_json():
    return {
        "board": {
            "3dviewports": [],
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.05, "copper_line_width": 0.2, "copper_text_size_h": 1.5,
                    "copper_text_size_v": 1.5, "copper_text_thickness": 0.3, "other_line_width": 0.1,
                    "silk_line_width": 0.12, "silk_text_size_h": 1.0, "silk_text_size_v": 1.0,
                    "silk_text_thickness": 0.15,
                },
                "diff_pair_dimensions": [],
                "drc_exclusions": [],
                "meta": {"version": 2},
                "rule_severities": {"lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore"},
                "rules": {
                    "allow_blind_buried_vias": False, "allow_microvias": False, "max_error": 0.005,
                    "min_clearance": 0.15, "min_connection": 0.0, "min_copper_edge_clearance": 0.3,
                    "min_groove_width": 0.0, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
                    "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1, "min_resolved_spokes": 1,
                    "min_silk_clearance": 0.0, "min_text_height": 0.8, "min_text_thickness": 0.1,
                    "min_through_hole_diameter": 0.3, "min_track_width": 0.15, "min_via_annular_width": 0.13,
                    "min_via_diameter": 0.5, "solder_mask_clearance": 0.0, "solder_mask_min_width": 0.0,
                    "solder_mask_to_copper_clearance": 0.0, "solder_paste_clearance": 0.0,
                    "solder_paste_margin_ratio": -0.0, "use_height_for_length_calcs": True,
                },
                "track_widths": [0.0, 0.3, 0.5, 0.7, 1.0],
                "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.8, "drill": 0.4}],
                "zones_allow_external_fillets": False,
            },
            "layer_pairs": [], "layer_presets": [], "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": PROJECT + ".kicad_pro", "version": 3},
        "net_settings": {
            "classes": [
                netclass("Default", 0.3, 0.2, 0.8, 0.4, 2147483647),
                netclass("Power", 0.7, 0.2, 0.9, 0.5, 0),
            ] + ([netclass("Fine", 0.2, 0.15, 0.6, 0.3, 1)] if FINE_NETS else []),
            "meta": {"version": 4},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in POWER_NETS]
                                 + [{"netclass": "Fine", "pattern": n} for n in FINE_NETS],
        },
        "erc": {"erc_exclusions": [], "meta": {"version": 0},
                "rule_severities": {"lib_symbol_issues": "ignore", "lib_symbol_mismatch": "ignore"}},
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "", "plot": "gerbers/", "pos_files": "", "specctra_dsn": "", "step": "", "svg": "", "vrml": ""},
                   "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [],
        "text_variables": {},
    }

def write_footprint_lib(out_dir):
    lib_dir = os.path.join(out_dir, FP_LIB + ".pretty")
    os.makedirs(lib_dir, exist_ok=True)
    used = sorted({c[1] for c in COMPONENTS})
    for name in used:
        dst = os.path.join(lib_dir, name + ".kicad_mod")
        if name in CUSTOM_FOOTPRINTS:
            fp = CUSTOM_FOOTPRINTS[name]()
            fp.insert(2, [Sym("version"), 20241229])
            fp.insert(3, [Sym("generator"), "gen_pcb.py"])
            fp.insert(4, [Sym("generator_version"), "1.0"])
            open(dst, "w").write(dump(fp) + "\n")
        else:
            src = fp_path(name)
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copyfile(src, dst)
    with open(os.path.join(out_dir, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (version 7)\n  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")(descr "project footprints"))\n)\n' % (FP_LIB, FP_LIB))
    pass

def apply_design(name):
    """Import designs/<name>.py and copy its UPPERCASE attributes over this module's tables."""
    import importlib
    sys.path.insert(0, os.path.join(HERE, "designs"))
    mod = importlib.import_module(name)
    g = globals()
    for k in dir(mod):
        if k.isupper():
            g[k] = getattr(mod, k)
    g["NET_ID"] = {n: i for i, n in enumerate(g["NET_NAMES"])}
    for fname, builder in getattr(mod, "CUSTOM_FOOTPRINTS", {}).items():
        CUSTOM_FOOTPRINTS[fname] = builder
    if hasattr(mod, "PROJECT"):
        g["FP_LIB"] = mod.PROJECT
        g["FP_DIR"] = os.environ.get("FP_DIR") or os.path.join(HERE, "..", mod.PROJECT, mod.PROJECT + ".pretty")
    return mod

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--no-zones", action="store_true")
    ap.add_argument("--uuids", help="json file with ref->schematic symbol uuid map (created if missing)")
    ap.add_argument("--nc-nets", help="json from gen_sch.py: per-ref no-connect pad net names")
    ap.add_argument("--design", help="python module in designs/ that overrides the tables (default: built-in carrier)")
    a = ap.parse_args()
    if a.design:
        apply_design(a.design)
    if a.nc_nets and os.path.exists(a.nc_nets):
        nc = json.load(open(a.nc_nets))
        for i, comp in enumerate(COMPONENTS):
            ref = comp[0]
            if ref in nc:
                pad_nets = dict(comp[6])
                for pn, netname in nc[ref].items():
                    if netname not in NET_ID:
                        NET_ID[netname] = len(NET_NAMES)
                        NET_NAMES.append(netname)
                    pad_nets[int(pn) if pn.isdigit() else pn] = netname
                COMPONENTS[i] = comp[:6] + (pad_nets,) + comp[7:]
    os.makedirs(a.out_dir, exist_ok=True)
    if a.uuids and os.path.exists(a.uuids):
        sch_uuids = json.load(open(a.uuids))
    else:
        sch_uuids = {c[0]: uid() for c in COMPONENTS}
        if a.uuids:
            json.dump(sch_uuids, open(a.uuids, "w"), indent=1)
    board = build_board(sch_uuids, with_zones=not a.no_zones)
    pcb = os.path.join(a.out_dir, PROJECT + ".kicad_pcb")
    with open(pcb, "w") as f:
        f.write(dump(board) + "\n")
    with open(os.path.join(a.out_dir, PROJECT + ".kicad_pro"), "w") as f:
        json.dump(project_json(), f, indent=2)
    write_footprint_lib(a.out_dir)
    print("wrote", pcb)

if __name__ == "__main__":
    main()
