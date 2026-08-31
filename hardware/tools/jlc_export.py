#!/usr/bin/env python3
"""
Write JLCPCB assembly files (BOM + CPL) from a design module and a kicad-cli position CSV.

  python3 jlc_export.py --design pcba --pos build/pcba/pos-all.csv --out-dir build/pcba

BOM columns : Comment, Designator, Footprint, LCSC Part #
CPL columns : Designator, Mid X, Mid Y, Layer, Rotation
Rotation corrections follow the community table used by JLCKicadTools / Fabrication Toolkit
(KiCad footprint orientation -> JLCPCB/EasyEDA orientation).
"""
import argparse, csv, importlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "designs"))

ROTATION_FIX = [
    # verified 2026-08-25 by comparing KiCad footprints with the JLCPCB/EasyEDA footprints of the
    # exact LCSC parts used (pad-1 position): SOT-23 / SOT-223 are drawn 180 deg apart, the
    # ESP32-S3-WROOM-1, HRO USB-C, WS2812B 5050, SOD-123 and Molex 5566 are drawn the same way.
    (r"^SOT-223", 180),
    (r"^SOT-23", 180),
    (r"^SOIC-", 270),
    (r"^SOP-", 270),
    (r"^TSSOP-", 270),
    (r"^LQFP-", 270),
    (r"^QFN-", 270),
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--pos", required=True, help="kicad-cli pcb export pos --format csv --units mm")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--full", action="store_true", help="include parts listed in design.ASSEMBLE_EXCLUDE (user-soldered)")
    ap.add_argument("--suffix", default="", help="output file name suffix, e.g. -full")
    a = ap.parse_args()
    design = importlib.import_module(a.design)
    lcsc = dict(design.LCSC)                # ref -> "Cxxxxx" ('' = not assembled)
    if not a.full:
        for ref in getattr(design, "ASSEMBLE_EXCLUDE", ()):
            lcsc[ref] = ""
    comps = {c[0]: c for c in design.COMPONENTS}

    rows = list(csv.DictReader(open(a.pos, newline="")))
    # kicad-cli csv header: Ref,Val,Package,PosX,PosY,Rot,Side
    bom = {}
    cpl = []
    skipped = []
    for r in rows:
        ref = r["Ref"]
        part = lcsc.get(ref, "")
        if not part:
            skipped.append(ref)
            continue
        fp = r["Package"].split(":")[-1]
        rot = float(r["Rot"])
        for pat, fix in ROTATION_FIX:
            if re.match(pat, fp):
                rot = (rot + fix) % 360
                break
        side = "Top" if r["Side"].lower().startswith("top") else "Bottom"
        # kicad-cli pos: y axis points up (negated); JLCPCB wants the same convention as KiCad's own
        # "Fabrication Toolkit" output, which uses the position file values directly.
        cpl.append((ref, "%.4f" % float(r["PosX"]), "%.4f" % float(r["PosY"]), side, "%.0f" % rot))
        key = (r["Val"], fp, part)
        bom.setdefault(key, []).append(ref)

    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "jlcpcb-bom%s.csv" % a.suffix), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (val, fp, part), refs in sorted(bom.items(), key=lambda kv: kv[1][0]):
            w.writerow([val, ",".join(refs), fp, part])
    with open(os.path.join(a.out_dir, "jlcpcb-cpl%s.csv" % a.suffix), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in sorted(cpl):
            w.writerow(row)
    n_ext = sum(1 for k in bom if k[2] and k[2] not in getattr(design, "BASIC_PARTS", set()))
    ext = sorted({k[2] for k in bom if k[2] and k[2] not in getattr(design, "BASIC_PARTS", set())})
    print("BOM lines:", len(bom), "placements:", len(cpl), "not assembled:", skipped, "| extended parts:", len(ext), ext)

if __name__ == "__main__":
    main()
