#!/bin/bash
# Requirements: KiCad 10 (kicad-cli + bundled python with pcbnew), Java 21+ for Freerouting, python3.
# Rebuild the whole hardware project: PCB -> schematic -> PCB (with NC nets) -> autoroute -> checks -> outputs
set -e
cd "$(dirname "$0")"
KICAD_APP="${KICAD_APP:-$HOME/Applications/KiCad/KiCad.app}"
KC="$KICAD_APP/Contents/MacOS/kicad-cli"
KPY=$(ls -d "$KICAD_APP"/Contents/Frameworks/Python.framework/Versions/*/bin/python3 | head -1)
JAVA="${JAVA:-/Volumes/apps/homebrew/opt/openjdk/bin/java}"
JAR="${JAR:-$PWD/freerouting-2.3.0.jar}"
if [ ! -f "$JAR" ]; then
  echo "downloading Freerouting 2.3.0 ..."
  curl -sL -o "$JAR" https://github.com/freerouting/freerouting/releases/download/v2.3.0/freerouting-2.3.0.jar
fi
DESIGN="${1:-carrier}"            # carrier | pcba | mini  (designs/<name>.py)
if [ "$DESIGN" = "carrier" ]; then PROJECT=bc250-front-carrier; DARG=""; UU=uuids.json;
else PROJECT=$(python3 -c "import sys; sys.path.insert(0,'designs'); print(__import__('$DESIGN').PROJECT)"); DARG="--design $DESIGN"; UU="uuids-$DESIGN.json"; fi
OUT=build/$DESIGN
DEST=../$PROJECT
rm -rf "$OUT"; mkdir -p "$OUT"
python3 gen_pcb.py --out-dir "$OUT" --uuids "$UU" $DARG
python3 gen_sch.py --out-dir "$OUT" --uuids "$UU" $DARG
"$KPY" route.py --pcb "$OUT/$PROJECT.kicad_pcb" --out "$OUT/routed/$PROJECT.kicad_pcb" \
    --jar "$JAR" --java "$JAVA" --passes 150 --threads 6 --nc-nets "$OUT/nc_nets.json" 2>&1 | grep -E "DSN export|SES import|assigned|saved|ERROR"
# final project dir = routed board + schematic + project + libs
P="$OUT/project"; mkdir -p "$P"
cp "$OUT/routed/$PROJECT.kicad_pcb" "$P/"
cp "$OUT/$PROJECT.kicad_sch" "$OUT/$PROJECT.kicad_pro" "$OUT/$PROJECT.kicad_sym" "$OUT/fp-lib-table" "$OUT/sym-lib-table" "$P/"
cp -R "$OUT/$PROJECT.pretty" "$P/"
echo "=== ERC ==="
"$KC" sch erc --severity-all -o "$OUT/erc.txt" "$P/$PROJECT.kicad_sch" 2>&1 | grep -vE "assert|Fontconfig" | tail -1
echo "=== DRC + schematic parity ==="
"$KC" pcb drc --schematic-parity --refill-zones --save-board --severity-all --units mm -o "$OUT/drc.txt" "$P/$PROJECT.kicad_pcb" 2>&1 | grep -v assert | tail -2
echo "=== Gerbers ==="
G="$OUT/gerbers"; rm -rf "$G"; mkdir -p "$G"
"$KC" pcb export gerbers --layers "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" --subtract-soldermask --no-x2 --no-netlist --check-zones -o "$G/" "$P/$PROJECT.kicad_pcb" 2>&1 | grep -v assert | tail -1
"$KC" pcb export drill --format excellon --excellon-zeros-format decimal --excellon-units mm --drill-origin absolute --generate-map --map-format gerberx2 -o "$G/" "$P/$PROJECT.kicad_pcb" 2>&1 | grep -v assert | tail -1
(cd "$G" && rm -f ../$PROJECT-v1.0-gerbers.zip && zip -q ../$PROJECT-v1.0-gerbers.zip *)
echo "=== Renders / docs ==="
"$KC" pcb render --side top --quality high --width 1800 --height 1200 --zoom 1.15 --background opaque --floor -o "$OUT/render-top.png" "$P/$PROJECT.kicad_pcb" 2>&1 | grep -v assert | tail -1
"$KC" pcb render --side bottom --quality high --width 1800 --height 1200 --zoom 1.15 --background opaque -o "$OUT/render-bottom.png" "$P/$PROJECT.kicad_pcb" 2>&1 | grep -v assert | tail -1
"$KC" pcb render --quality high --width 1800 --height 1200 --zoom 1.0 --background opaque --perspective --rotate "-35,0,25" --floor -o "$OUT/render-iso.png" "$P/$PROJECT.kicad_pcb" 2>&1 | grep -v assert | tail -1
"$KC" sch export pdf -o "$OUT/$PROJECT-schematic.pdf" "$P/$PROJECT.kicad_sch" 2>&1 | grep -vE "assert|Fontconfig" | tail -1
"$KC" sch export svg --exclude-drawing-sheet -o "$OUT/sch_svg" "$P/$PROJECT.kicad_sch" 2>&1 | grep -vE "assert|Fontconfig" | tail -1
"$KC" pcb export svg --layers "F.Cu,B.Cu,F.SilkS,Edge.Cuts" --page-size-mode 2 --exclude-drawing-sheet -o "$OUT/board-layout.svg" "$P/$PROJECT.kicad_pcb" 2>&1 | grep -v assert | tail -1
"$KC" pcb export pos --format csv --units mm --side both -o "$OUT/$PROJECT-pos.csv" "$P/$PROJECT.kicad_pcb" 2>&1 | grep -v assert | tail -1
echo "=== install into $DEST ==="
mkdir -p "$DEST/images" "$DEST/gerbers"
cp "$P"/$PROJECT.kicad_pcb "$P"/$PROJECT.kicad_sch "$P"/$PROJECT.kicad_pro "$P"/$PROJECT.kicad_sym "$P"/fp-lib-table "$P"/sym-lib-table "$DEST/"
rm -rf "$DEST/$PROJECT.pretty"; cp -R "$P/$PROJECT.pretty" "$DEST/"
rm -f "$DEST"/gerbers/*; cp "$G"/* "$OUT"/$PROJECT-v1.0-gerbers.zip "$DEST/gerbers/"
cp "$OUT/$PROJECT-schematic.pdf" "$OUT/$PROJECT-pos.csv" "$DEST/"
cp "$OUT/render-top.png" "$DEST/images/board-top.png"; cp "$OUT/render-bottom.png" "$DEST/images/board-bottom.png"
cp "$OUT/render-iso.png" "$DEST/images/board-iso.png"; cp "$OUT/board-layout.svg" "$DEST/images/board-layout.svg"
cp "$OUT/sch_svg/$PROJECT.svg" "$DEST/images/schematic.svg"
if [ "$DESIGN" != "carrier" ]; then
  echo "=== JLCPCB BOM / CPL ==="
  "$KC" pcb export pos --format csv --units mm --side both --exclude-dnp -o "$OUT/pos-all.csv" "$P/$PROJECT.kicad_pcb" 2>&1 | grep -v assert | tail -1
  python3 jlc_export.py --design "$DESIGN" --pos "$OUT/pos-all.csv" --out-dir "$OUT"
  python3 jlc_export.py --design "$DESIGN" --pos "$OUT/pos-all.csv" --out-dir "$OUT" --full --suffix=-full
  cp "$OUT/jlcpcb-bom.csv" "$OUT/jlcpcb-cpl.csv" "$OUT/jlcpcb-bom-full.csv" "$OUT/jlcpcb-cpl-full.csv" "$DEST/"
fi
echo "BUILD OK"
