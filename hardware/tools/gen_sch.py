#!/usr/bin/env python3
"""
Generate the KiCad schematic for the BC250 carrier board from the same component /
net tables used for the PCB (gen_pcb.py), so both always agree.

Style: every pin gets either a global label (signal nets), a power symbol
(GND/+5V/+3V3/+12V in the discrete section) or a no-connect flag.
"""
import os, sys, math, json, argparse, copy, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, dump, Sym, find, find_all, num
import gen_pcb as P

SYMDIR = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")
PROJECT = P.PROJECT
POWER = {"GND", "+5V", "+3V3", "+12V"}

def uid():
    return str(uuid.uuid4())

# ----------------------------------------------------------------------------
# library symbols
# ----------------------------------------------------------------------------
_libcache = {}
def lib_symbol(lib, name):
    """Return a deep copy of symbol `name` from KiCad library `lib`, renamed 'lib:name'."""
    if lib not in _libcache:
        _libcache[lib] = parse(open(os.path.join(SYMDIR, lib + ".kicad_sym")).read())[0]
    for s in find_all(_libcache[lib], "symbol"):
        if s[1] == name:
            s = copy.deepcopy(s)
            ext = find(s, "extends")
            if ext is not None:
                # flatten: parent body + child properties, unit sub-symbols renamed to the child
                parent = lib_symbol(lib, ext[1])
                pname = ext[1]
                child_props = {p[1]: p for p in find_all(s, "property")}
                flat = [e for e in parent if not (isinstance(e, list) and e and e[0] == "property")]
                for p in find_all(parent, "property"):
                    flat.insert(len([e for e in flat if not isinstance(e, list) or e[0] != "symbol"]) if False else 2,
                                child_props.get(p[1], p))
                # rename units
                for sub in find_all(flat, "symbol"):
                    if isinstance(sub[1], str) and sub[1].startswith(pname + "_"):
                        sub[1] = name + sub[1][len(pname):]
                s = flat
            s[1] = lib + ":" + name
            return s
    raise KeyError(lib + ":" + name)

def pin(number, name, etype, x, y, angle, length=5.08, hide_name=False):
    e = [Sym("pin"), Sym(etype), Sym("line"), [Sym("at"), x, y, angle], [Sym("length"), length],
         [Sym("name"), name, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]],
         [Sym("number"), number, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]]]
    return e

def prop(key, val, x=0, y=0, rot=0, hide=False, size=1.27, justify=None):
    eff = [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]
    if justify:
        eff.append([Sym("justify"), Sym(justify)])
    if hide:
        eff.append([Sym("hide"), Sym("yes")])
    return [Sym("property"), key, val, [Sym("at"), x, y, rot], eff]

def custom_symbol(fullname, ref_prefix, descr, w, h, pins_left, pins_right, fp=""):
    """Rectangle body w x h (centered), pins_left/right = list of (number, name, etype)
    top->bottom at 2.54 pitch."""
    hw, hh = w / 2, h / 2
    s = [Sym("symbol"), fullname, [Sym("pin_names"), [Sym("offset"), 1.016]],
         [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
         prop("Reference", ref_prefix, -hw, hh + 1.27, 0, justify="left"),
         prop("Value", fullname.split(":")[1], hw, -hh - 1.27, 0, justify="right"),
         prop("Footprint", fp, 0, 0, 0, hide=True),
         prop("Datasheet", "", 0, 0, 0, hide=True),
         prop("Description", descr, 0, 0, 0, hide=True)]
    base = fullname.split(":")[1]
    body = [Sym("symbol"), base + "_0_1",
            [Sym("rectangle"), [Sym("start"), -hw, hh], [Sym("end"), hw, -hh],
             [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
             [Sym("fill"), [Sym("type"), Sym("background")]]]]
    unit = [Sym("symbol"), base + "_1_1"]
    n = max(len(pins_left), len(pins_right))
    y0 = (n - 1) * 2.54 / 2
    for i, (number, name, et) in enumerate(pins_left):
        unit.append(pin(number, name, et, -hw - 5.08, y0 - i * 2.54, 0))
    for i, (number, name, et) in enumerate(pins_right):
        unit.append(pin(number, name, et, hw + 5.08, y0 - i * 2.54, 180))
    s += [body, unit, [Sym("embedded_fonts"), Sym("no")]]
    return s

def devkit_symbol():
    left, right = [], []
    for n in range(1, 23):
        nm = P.DEVKIT_PINS[n]
        et = "power_out" if n == 1 else "passive" if n == 2 else "power_in" if nm in ("5V",) else "passive" if nm == "GND" else "bidirectional"
        left.append((str(n), nm, et))
    for n in range(44, 22, -1):
        nm = P.DEVKIT_PINS[n]
        et = "passive" if nm == "GND" else "bidirectional"
        right.append((str(n), nm, et))
    return custom_symbol(P.FP_LIB + ":ESP32-S3-DevKitC-1", "U", "ESP32-S3-DevKitC-1 dev board (2x22 header)",
                         35.56, 60.96, left, right, P.FP_LIB + ":ESP32-S3-DevKitC-1_Socket")

ATX_PINS = {1: "+3.3V", 2: "+3.3V", 3: "GND", 4: "+5V", 5: "GND", 6: "+5V", 7: "GND", 8: "PWR_OK",
            9: "+5VSB", 10: "+12V", 11: "+12V", 12: "+3.3V", 13: "+3.3V", 14: "-12V", 15: "GND",
            16: "PS_ON", 17: "GND", 18: "GND", 19: "GND", 20: "NC", 21: "+5V", 22: "+5V", 23: "+5V", 24: "GND"}
def atx_symbol():
    def et(n):
        nm = ATX_PINS[n]
        if n in (9, 10, 17):          # one power_out driver per net, rest passive (ERC)
            return "power_out"
        if nm == "PS_ON":
            return "input"
        if nm == "PWR_OK":
            return "output"
        return "passive"
    left = [(str(n), ATX_PINS[n], et(n)) for n in range(1, 13)]
    right = [(str(n), ATX_PINS[n], et(n)) for n in range(13, 25)]
    return custom_symbol(P.FP_LIB + ":ATX24", "J", "ATX 24-pin power connector (Molex Mini-Fit Jr 5566-24)",
                         25.4, 35.56, left, right, P.FP_LIB + ":Molex_Mini-Fit_Jr_5566-24A_2x12_P4.20mm_Vertical")

CUSTOM_SYMBOLS = {"ESP32-S3-DevKitC-1": devkit_symbol, "ATX24": atx_symbol}
NOTES = [
    "BC250 Front Controller - ESP32-S3 DevKitC-1 carrier board",
    "ATX 24-pin plug from the PSU goes straight onto J1.  5VSB powers the ESP32 + relay at all times.",
    "K1: COM=PS_ON, NC=GND -> PSU is ON while the relay is idle; ESP32 drives Q1 (GPIO4 HIGH) to cut power.",
    "PWR_OK (5V) -> R3/R4 divider -> GPIO5.   DS18B20 bus on GPIO7 with R5 pull-up to 3V3.",
    "Firmware: set  relay_inverted: \"false\"  in the ESPHome yaml when using this board.",
]
PAPER = "A4"
NOTES_Y = 182.88
PWR_FLAGS = {}          # net -> (x, y): place a PWR_FLAG on nets that have no power-output driver

# ----------------------------------------------------------------------------
# which library symbol each component uses, and where it goes on the sheet
# ref -> (lib, name, x, y, rot)
# ----------------------------------------------------------------------------
PLACE = {
    "U1": ("custom", "ESP32-S3-DevKitC-1", 55.88, 96.52, 0),
    "J1": ("custom", "ATX24", 137.16, 45.72, 0),
    "K1": ("Relay", "SANYOU_SRD_Form_C", 205.74, 40.64, 0),
    "Q1": ("Transistor_BJT", "Q_NPN_EBC", 198.12, 78.74, 0),
    "D1": ("Device", "D", 218.44, 60.96, 0),
    "R1": ("Device", "R", 170.18, 78.74, 90),
    "R2": ("Device", "R", 187.96, 93.98, 0),
    "R3": ("Device", "R", 109.22, 121.92, 0),
    "R4": ("Device", "R", 124.46, 121.92, 0),
    "R5": ("Device", "R", 139.7, 132.08, 180),
    "C1": ("Device", "C_Polarized", 236.22, 80.01, 0),
    "C2": ("Device", "C", 223.52, 80.01, 0),
    "J2": ("Connector_Generic", "Conn_01x08", 264.16, 30.48, 0),
    "J3": ("Connector_Generic", "Conn_01x04", 264.16, 55.88, 0),
    "J4": ("Connector_Generic", "Conn_01x04", 264.16, 76.2, 0),
    "J5": ("Connector_Generic", "Conn_01x03", 264.16, 95.25, 0),
    "J6": ("Connector_Generic", "Conn_01x03", 264.16, 110.49, 0),
    "J7": ("Connector_Generic", "Conn_01x03", 264.16, 125.73, 0),
    "J8": ("Connector_Generic", "Conn_01x06", 264.16, 147.32, 0),
    "SW1": ("Switch", "SW_Push", 203.2, 116.84, 0),
    "SW2": ("Switch", "SW_Push", 203.2, 129.54, 0),
    "SW3": ("Switch", "SW_Push", 203.2, 142.24, 0),
    "H1": ("Mechanical", "MountingHole", 38.1, 165.1, 0),
    "H2": ("Mechanical", "MountingHole", 53.34, 165.1, 0),
    "H3": ("Mechanical", "MountingHole", 68.58, 165.1, 0),
    "H4": ("Mechanical", "MountingHole", 83.82, 165.1, 0),
}
# components whose power pins get a power *symbol* (others get a global label)
USE_POWER_SYMBOL = {"K1", "Q1", "D1", "R2", "R4", "R5", "C1", "C2", "SW1", "SW2", "SW3"}
# reference / value text placement relative to the symbol origin
TEXT_SCH = {
    "U1": (0, -33.02, 0, 33.02, None),
    "J1": (0, -20.32, 0, 20.32, None),
    "K1": (12.7, -1.27, 12.7, 1.27, "left"),
    "D1": (0, -2.8, 0, 2.8, None),
    "R1": (0, -2.8, 0, 2.8, None),
    "SW1": (0, -4.2, 0, 2.8, None), "SW2": (0, -4.2, 0, 2.8, None), "SW3": (0, -4.2, 0, 2.8, None),
}

# ----------------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------------
def rot_vec(x, y, deg):
    r = math.radians(deg)
    c, s = round(math.cos(r), 9), round(math.sin(r), 9)
    return (x * c - y * s, x * s + y * c)

def symbol_pins(sym):
    """[(number, x, y, angle, name)] in symbol coords (y up) for all units."""
    out = []
    for sub in find_all(sym, "symbol"):
        for p in find_all(sub, "pin"):
            at = find(p, "at")
            out.append((find(p, "number")[1], num(at[1]), num(at[2]), num(at[3]) if len(at) > 3 else 0, find(p, "name")[1]))
    return out

def sym_flag(sym, key, default):
    e = find(sym, key)
    return e[1] if e else default

def pin_sheet_pos(sx, sy, rot, px, py, pangle):
    """connection point on the sheet and outward unit vector (sheet coords, y down)."""
    rx, ry = rot_vec(px, py, rot)
    ox, oy = {0: (-1, 0), 90: (0, -1), 180: (1, 0), 270: (0, 1)}[int(pangle) % 360]
    ox, oy = rot_vec(ox, oy, rot)
    return (round(sx + rx, 4), round(sy - ry, 4)), (round(ox), round(-oy))

# ----------------------------------------------------------------------------
# schematic items
# ----------------------------------------------------------------------------
def wire(x1, y1, x2, y2):
    return [Sym("wire"), [Sym("pts"), [Sym("xy"), x1, y1], [Sym("xy"), x2, y2]],
            [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]], [Sym("uuid"), uid()]]

def no_connect(x, y):
    return [Sym("no_connect"), [Sym("at"), x, y], [Sym("uuid"), uid()]]

def global_label(text, x, y, out):
    ang = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[out]
    just = "right" if ang in (180, 270) else "left"     # KiCad: 180/270 labels are right-justified
    return [Sym("global_label"), text, [Sym("shape"), Sym("passive")], [Sym("at"), x, y, ang],
            [Sym("fields_autoplaced"), Sym("yes")],
            [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("justify"), Sym(just)]],
            [Sym("uuid"), uid()],
            prop("Intersheetrefs", "${INTERSHEET_REFS}", x, y, 0, hide=True)]

def text(t, x, y, size=1.5):
    return [Sym("text"), t, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), x, y, 0],
            [Sym("effects"), [Sym("font"), [Sym("size"), size, size]], [Sym("justify"), Sym("left"), Sym("bottom")]],
            [Sym("uuid"), uid()]]

def symbol_instance(lib_id, ref, value, footprint, descr, x, y, rot, pins, sym_uuid, root_uuid, hide_value=False, in_bom="yes"):
    rdx, rdy, vdx, vdy, just = TEXT_SCH.get(ref, (2.54, -2.54, 2.54, 0, "left"))
    dnp = ref in getattr(P, "DNP", set())
    if dnp:
        in_bom = "no"
    s = [Sym("symbol"), [Sym("lib_id"), lib_id], [Sym("at"), x, y, rot], [Sym("unit"), 1],
         [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym(in_bom)], [Sym("on_board"), Sym("yes")],
         [Sym("dnp"), Sym("yes" if dnp else "no")], [Sym("uuid"), sym_uuid],
         prop("Reference", ref, x + rdx, y + rdy, 0, justify=just),
         prop("Value", value, x + vdx, y + vdy, 0, justify=just, hide=hide_value),
         prop("Footprint", footprint, x, y, 0, hide=True),
         prop("Datasheet", "~", x, y, 0, hide=True),
         prop("Description", descr, x, y, 0, hide=True)]
    for pn in pins:
        s.append([Sym("pin"), pn, [Sym("uuid"), uid()]])
    s.append([Sym("instances"), [Sym("project"), PROJECT, [Sym("path"), "/" + root_uuid, [Sym("reference"), ref], [Sym("unit"), 1]]]])
    return s

def power_symbol(net, x, y, root_uuid, counter):
    counter[0] += 1
    ref = "#PWR%03d" % counter[0]
    s = [Sym("symbol"), [Sym("lib_id"), "power:" + net], [Sym("at"), x, y, 0], [Sym("unit"), 1],
         [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
         [Sym("dnp"), Sym("no")], [Sym("uuid"), uid()],
         prop("Reference", ref, x, y, 0, hide=True),
         prop("Value", net, x, y + (2.54 if net == "GND" else -2.54), 0),
         prop("Footprint", "", x, y, 0, hide=True),
         prop("Datasheet", "", x, y, 0, hide=True),
         prop("Description", "Power symbol", x, y, 0, hide=True),
         [Sym("pin"), "1", [Sym("uuid"), uid()]],
         [Sym("instances"), [Sym("project"), PROJECT, [Sym("path"), "/" + root_uuid, [Sym("reference"), ref], [Sym("unit"), 1]]]]]
    return s

# ----------------------------------------------------------------------------
def build(sch_uuids, root_uuid):
    libs = {}
    items = []
    pwr_counter = [0]
    used_power = set()
    nc_nets = {}          # ref -> {pad: "unconnected-(...)"}  (KiCad's naming for no-connect pins)
    custom = {}
    for comp in P.COMPONENTS:
        ref, fpname, value, _x, _y, _r, pad_nets, descr = comp
        lib, name, sx, sy, rot = PLACE[ref]
        if lib == "custom":
            sym = CUSTOM_SYMBOLS[name]()
            lib_id = P.FP_LIB + ":" + name
            custom[name] = sym
        else:
            sym = lib_symbol(lib, name)
            lib_id = lib + ":" + name
        libs.setdefault(lib_id, sym)
        pins = symbol_pins(sym)
        footprint = P.FP_LIB + ":" + fpname
        items.append(symbol_instance(lib_id, ref, value, footprint, descr, sx, sy, rot,
                                     [pn for pn, *_ in pins], sch_uuids[ref], root_uuid,
                                     in_bom=str(sym_flag(sym, "in_bom", "yes"))))
        for pn, px, py, pa, pname in pins:
            (cx, cy), out = pin_sheet_pos(sx, sy, rot, px, py, pa)
            net = pad_nets.get(pn) or (pad_nets.get(int(pn)) if pn.isdigit() else None)
            if not net:
                items.append(no_connect(cx, cy))
                tag = ("%s-%s-Pad%s" % (ref, pname, pn)) if pname and pname != "~" else ("%s-Pad%s" % (ref, pn))
                nc_nets.setdefault(ref, {})[pn] = "unconnected-(%s)" % tag
                continue
            ex, ey = cx + out[0] * 2.54, cy + out[1] * 2.54
            upside_down = (net == "GND" and out == (0, -1)) or (net != "GND" and out == (0, 1))
            if net in POWER and ref in USE_POWER_SYMBOL and not upside_down:
                # stub outward, then vertical stub, then power symbol
                items.append(wire(cx, cy, ex, ey))
                vy = 2.54 if net == "GND" else -2.54
                if out[1] == 0:
                    items.append(wire(ex, ey, ex, ey + vy))
                    ey = ey + vy
                items.append(power_symbol(net, ex, ey, root_uuid, pwr_counter))
                used_power.add(net)
            else:
                items.append(wire(cx, cy, ex, ey))
                items.append(global_label(net, ex, ey, out))
    for net in used_power:
        libs["power:" + net] = lib_symbol("power", net)
    for net, (x, y) in PWR_FLAGS.items():
        pwr_counter[0] += 1
        ref = "#FLG%03d" % pwr_counter[0]
        items.append([Sym("symbol"), [Sym("lib_id"), "power:PWR_FLAG"], [Sym("at"), x, y, 0], [Sym("unit"), 1],
                      [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
                      [Sym("dnp"), Sym("no")], [Sym("uuid"), uid()],
                      prop("Reference", ref, x, y, 0, hide=True), prop("Value", "PWR_FLAG", x, y - 3.0, 0),
                      prop("Footprint", "", x, y, 0, hide=True), prop("Datasheet", "", x, y, 0, hide=True),
                      prop("Description", "", x, y, 0, hide=True), [Sym("pin"), "1", [Sym("uuid"), uid()]],
                      [Sym("instances"), [Sym("project"), PROJECT, [Sym("path"), "/" + root_uuid, [Sym("reference"), ref], [Sym("unit"), 1]]]]])
        items.append(wire(x, y, x, y + 2.54))
        items.append(global_label(net, x, y + 2.54, (0, 1)))
        libs["power:PWR_FLAG"] = lib_symbol("power", "PWR_FLAG")
    return libs, items, nc_nets, custom

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--uuids", required=True)
    ap.add_argument("--design", help="design module name (designs/<name>.py); overrides PLACE / TEXT_SCH / etc.")
    a = ap.parse_args()
    if a.design:
        mod = P.apply_design(a.design)
        globals()["PROJECT"] = P.PROJECT
        for k in ("PLACE", "TEXT_SCH", "USE_POWER_SYMBOL", "NOTES", "PAPER", "PWR_FLAGS", "NOTES_Y"):
            if hasattr(mod, "SCH_" + k):
                globals()[k] = getattr(mod, "SCH_" + k)
        for name, builder in getattr(mod, "CUSTOM_SYMBOLS", {}).items():
            CUSTOM_SYMBOLS[name] = builder
    sch_uuids = json.load(open(a.uuids))
    root_uuid = sch_uuids.get("__root__")
    if not root_uuid:
        root_uuid = sch_uuids["__root__"] = uid()
        json.dump(sch_uuids, open(a.uuids, "w"), indent=1)
    libs, items, nc_nets, custom = build(sch_uuids, root_uuid)
    json.dump(nc_nets, open(os.path.join(a.out_dir, "nc_nets.json"), "w"), indent=1)
    # project symbol library with the two custom symbols (so the project is self-contained)
    lib = [Sym("kicad_symbol_lib"), [Sym("version"), 20241209], [Sym("generator"), "gen_sch.py"], [Sym("generator_version"), "1.0"]]
    for name, sym in custom.items():
        sym = copy.deepcopy(sym)
        sym[1] = name
        lib.append(sym)
    with open(os.path.join(a.out_dir, PROJECT + ".kicad_sym"), "w") as f:
        f.write(dump(lib) + "\n")
    with open(os.path.join(a.out_dir, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "project symbols"))\n)\n' % (P.FP_LIB, PROJECT))
    sch = [Sym("kicad_sch"), [Sym("version"), 20250114], [Sym("generator"), "eeschema"], [Sym("generator_version"), "9.0"],
           [Sym("uuid"), root_uuid], [Sym("paper"), PAPER],
           [Sym("title_block"), [Sym("title"), P.TITLE], [Sym("date"), P.DATE], [Sym("rev"), P.REV],
            [Sym("company"), "github.com/LeeHueeng/bc250-front-controller"]],
           [Sym("lib_symbols")] + [libs[k] for k in sorted(libs)]]
    sch += items
    notes = NOTES
    for i, t in enumerate(notes):
        sch.append(text(t, 12.7, NOTES_Y + i * 3.2, 1.6 if i == 0 else 1.3))
    sch.append([Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]])
    sch.append([Sym("embedded_fonts"), Sym("no")])
    out = os.path.join(a.out_dir, PROJECT + ".kicad_sch")
    with open(out, "w") as f:
        f.write(dump(sch) + "\n")
    print("wrote", out, "items", len(items))

if __name__ == "__main__":
    main()
