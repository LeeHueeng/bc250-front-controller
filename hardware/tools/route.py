#!/usr/bin/env python3
"""
Autoroute a KiCad board with Freerouting, then fill zones.
Run with KiCad's bundled python (has the SWIG pcbnew module):
  <KiCad.app>/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 route.py \
      --pcb build/x.kicad_pcb --jar freerouting.jar --java /path/java --out build/x-routed.kicad_pcb
"""
import argparse, os, subprocess, sys, shutil
import pcbnew

ap = argparse.ArgumentParser()
ap.add_argument("--pcb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--jar", required=True)
ap.add_argument("--java", default="java")
ap.add_argument("--passes", type=int, default=200)
ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--skip-route", action="store_true", help="only fill zones and save")
ap.add_argument("--nc-nets", help="json {ref: {pad: netname}} of no-connect nets to assign after routing")
a = ap.parse_args()

pcb = os.path.abspath(a.pcb)
out = os.path.abspath(a.out)
work = os.path.dirname(out)
os.makedirs(work, exist_ok=True)
dsn = os.path.join(work, "route.dsn")
ses = os.path.join(work, "route.ses")

board = pcbnew.LoadBoard(pcb)
print("loaded", pcb, "footprints", len(board.GetFootprints()), "tracks", len(board.GetTracks()))

if not a.skip_route:
    # start from a clean slate: drop any existing tracks/vias
    for t in list(board.GetTracks()):
        if not t.IsLocked():
            board.Remove(t)
    # Export without zones: Freerouting would otherwise treat the GND pour as a plane
    # (leaving GND pads unrouted / islanded) and the antenna keep-out as a no-route area.
    zones = list(board.Zones())
    for z in zones:
        board.Remove(z)
    ok = pcbnew.ExportSpecctraDSN(board, dsn)
    print("DSN export:", ok, dsn)
    for z in zones:
        board.Add(z)
    if os.path.exists(ses):
        os.remove(ses)
    cmd = [a.java, "-Djava.awt.headless=true", "-jar", a.jar, "-de", dsn, "-do", ses, "-mp", str(a.passes), "-mt", str(a.threads), "-l", "en"]
    print("running:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    tail = (r.stdout or "")[-3000:] + (r.stderr or "")[-3000:]
    print(tail)
    if not os.path.exists(ses):
        print("ERROR: no SES produced")
        sys.exit(2)
    ok = pcbnew.ImportSpecctraSES(board, ses)
    print("SES import:", ok, "tracks now", len(board.GetTracks()))

if a.nc_nets:
    # KiCad names no-connect pins "unconnected-(REF-PIN-PadN)"; give the pads those nets so the
    # schematic-parity DRC is clean.  Done after routing: Freerouting chokes on such net names.
    import json
    nc = json.load(open(a.nc_nets))
    n_assigned = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            name = nc.get(ref, {}).get(pad.GetNumber())
            if name:
                net = board.FindNet(name)
                if net is None:
                    net = pcbnew.NETINFO_ITEM(board, name)
                    board.Add(net)
                pad.SetNet(net)
                n_assigned += 1
    print("assigned", n_assigned, "no-connect nets")

# Freerouting sometimes leaves vias that are only connected on one layer (a track on the other
# side got merged away).  They are useless and fail the via_dangling DRC check -> drop them.
# GND vias are kept: their other side is connected by the GND pour.
def _via_layer_links(via):
    pos = via.GetPosition()
    links = {pcbnew.F_Cu: 0, pcbnew.B_Cu: 0}
    for t in board.GetTracks():
        if t.Type() != pcbnew.PCB_TRACE_T or t.GetNetCode() != via.GetNetCode():
            continue
        ly = t.GetLayer()
        if ly in links and ((t.GetStart() - pos).EuclideanNorm() < 20000 or (t.GetEnd() - pos).EuclideanNorm() < 20000):
            links[ly] += 1
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != via.GetNetCode():
                continue
            for ly in links:
                if pad.IsOnLayer(ly) and pad.HitTest(pos):
                    links[ly] += 1
    return links

n_dropped = 0
for t in list(board.GetTracks()):
    if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() != "GND" and not t.IsLocked():
        links = _via_layer_links(t)
        if min(links.values()) == 0:
            board.Remove(t)
            n_dropped += 1
print("dropped", n_dropped, "dangling vias")

filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
pcbnew.SaveBoard(out, board)
print("saved", out)
