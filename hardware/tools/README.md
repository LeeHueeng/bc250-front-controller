# hardware/tools — board generators

All boards are generated from Python tables, autorouted and checked by scripts; edit the tables, not the `.kicad_pcb`.

| File | Role |
|---|---|
| `gen_pcb.py` | placement / nets / silkscreen tables → `.kicad_pcb`, `.kicad_pro`, project footprint library. Built-in tables = DevKit carrier; `--design pcba` / `--design mini` load `designs/<name>.py` |
| `gen_sch.py` | schematic from the same tables (global labels, power symbols, no-connects, custom symbols) |
| `route.py` | Freerouting autoroute (headless) + no-connect nets + zone fill (runs under KiCad's bundled python) |
| `jlc_export.py` | JLCPCB BOM + CPL from the design's `LCSC` map and the position file (rotation corrections verified against EasyEDA footprints) |
| `build.sh [carrier\|pcba\|mini]` | everything: generate → route → ERC → DRC + schematic parity → Gerbers/drill zip → renders/PDF → install into `../<project>/` |
| `designs/pcba.py` | tables for the assembled board |
| `designs/mini.py` | tables for the 66×50 mm DevKit mini board (SMD parts under the DevKit, ATX header on board) |
| `uuids*.json` | stable symbol/footprint UUIDs so rebuilds keep the schematic ↔ PCB link |

Requirements: KiCad 10 (`KICAD_APP` env, default `~/Applications/KiCad/KiCad.app`), Java 21+ (`JAVA` env), python3. Freerouting 2.3.0 is downloaded automatically.
