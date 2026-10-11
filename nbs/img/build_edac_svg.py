r"""Generate edac_diagram.svg.

A professional, journal-style schematic of electrochemical direct air
capture (E-DAC) via bipolar-membrane electrodialysis (BPMED), laid out as a
narrow, tall (portrait) figure sized for a single column of a two-column
manuscript (e.g. Elsevier's elsarticle two-column layout - see
nbs/img/README or the paper source for \\includegraphics{...} usage).

Process: air is absorbed into an alkaline solution in a contactor; the
loaded solution is regenerated in a BPMED stack, where an applied voltage
splits water into H+ and OH- across a bipolar membrane; the acid (H+) stream
reacts with the loaded solution to release CO2 as a gas, while the base
(OH-) stream regenerates the alkaline solution and is recycled back to the
contactor. This matches Sabatino et al. (2020) Ind. Eng. Chem. Res. 59(15)
and, for the energy-demand range this model uses (43-162 kJ/mol), Liu, Yang
& Darton (2024) ACS Sustainable Chem. Eng. 12(10).

Plain hand-authored SVG: thin black strokes, no fills beyond white, minimal
colour used to distinguish the acid/base streams and the energy-use corner
badges - a journal figure, not a coloured infographic. Boxes are stacked
vertically (rather than the wider L-shaped layout used for a full-width
figure) so the whole schematic fits a single narrow column.

To edit the figure: change a coordinate/label below, then run:
    python nbs/img/build_edac_svg.py
from the repo root (or anywhere - this script has no path dependencies), and
re-execute the notebook so its embedded copy picks up the change:
    jupyter nbconvert --to notebook --execute --inplace nbs/edac_diagram.ipynb \
        --ExecutePreprocessor.kernel_name=uk-energy-current

To sanity-check layout while iterating, render the SVG to PNG with a headless
browser and inspect it, e.g. (Windows/Edge):
    msedge --headless --disable-gpu --screenshot=preview.png --window-size=420,530 edac_diagram.svg
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "edac_diagram.svg"

INK = "#1A1A1A"
GREY = "#4D4D4D"
ACID = "#8B2E22"
BASE = "#2C4B7C"
BADGE_FILL = "#E79087"
BADGE_STROKE = "#9B2D22"
BADGE_TEXT = "#111111"


def energy_badge(
    x: float,
    y: float,
    w: float,
    h: float,
    lines: str | tuple[str, ...],
) -> str:
    """Build an energy-use badge anchored to a box's bottom-right corner.

    Returns:
        SVG markup for the badge.
    """
    if isinstance(lines, str):
        lines = (lines,)

    right = x + w
    bottom = y + h
    left = right - 92
    top = bottom - 52
    font_size = 8.8 if len(lines) == 1 else 8.6
    baselines = (bottom - 10,) if len(lines) == 1 else (bottom - 21, bottom - 7)

    badge = [
        f'<path d="M{left},{bottom} L{right},{top} L{right},{bottom} Z" '
        f'fill="{BADGE_FILL}" fill-opacity="0.55" stroke="{BADGE_STROKE}" stroke-width="1.2"/>'
    ]
    badge.extend(
        f'<text x="{right - 8}" y="{baseline}" font-size="{font_size}" font-weight="600" fill="{BADGE_TEXT}" text-anchor="end">{line}</text>'
        for baseline, line in zip(baselines, lines, strict=False)
    )
    return "\n".join(badge)


def box(  # noqa: PLR0913, PLR0917
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    eq: str,
    note: str,
    energy_use: str | tuple[str, ...],
) -> str:
    """Build a process box with its text and energy-use badge.

    Returns:
        SVG markup for the process box.
    """
    return "\n".join([
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="#FFFFFF" stroke="{INK}" stroke-width="1.3"/>',
        f'<text x="{x + w / 2}" y="{y + 22}" font-size="12.5" font-weight="700" fill="{INK}" text-anchor="middle">{title}</text>',
        f'<text x="{x + w / 2}" y="{y + 46}" font-size="10.6" fill="{GREY}" text-anchor="middle">{eq}</text>',
        f'<text x="{x + w / 2 - 20}" y="{y + 66}" font-size="9.3" fill="{GREY}" text-anchor="middle" font-style="italic">{note}</text>',
        energy_badge(x, y, w, h, energy_use),
    ])


parts = []
VIEWBOX_W = 380
VIEWBOX_H = 490

parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEWBOX_W} {VIEWBOX_H}" '
    'font-family="Helvetica, Arial, sans-serif" role="img" '
    'aria-label="Schematic of electrochemical DAC (E-DAC) via bipolar-membrane electrodialysis. '
    "Air is absorbed into an alkaline solution in a contactor. The loaded solution is regenerated "
    "in a BPMED stack, where electricity splits water into H+ and OH- across a bipolar membrane. "
    "The acid stream reacts with the loaded solution to release CO2 gas, while the base stream "
    "regenerates the alkaline solution and is recycled back to the contactor. Energy is used by "
    "fans in the air contactor, electrolysis in the BPMED stack, and drying and compression after "
    'CO2 release.">'
)
parts.append("<title>Electrochemical DAC (E-DAC) via BPMED</title>")
parts.append(
    f"""<defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="{INK}"/>
    </marker>
    <marker id="arrowAcid" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="{ACID}"/>
    </marker>
    <marker id="arrowBase" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="{BASE}"/>
    </marker>
  </defs>"""
)
parts.append(f'<rect x="0" y="0" width="{VIEWBOX_W}" height="{VIEWBOX_H}" fill="#FFFFFF"/>')

BOX_X, BOX_W = 60, 260
CX = BOX_X + BOX_W / 2  # 190, shared vertical centreline

BOX1_Y, BOX_H = 60, 85
BOX2_Y = BOX1_Y + BOX_H + 40  # 185
BOX3_Y = BOX2_Y + BOX_H + 40  # 310

# ---- Air contactor ----
parts.append(
    box(
        BOX_X,
        BOX1_Y,
        BOX_W,
        BOX_H,
        "Air contactor",
        "CO&#8322; + 2OH&#8315; &#8594; CO&#8323;&#178;&#8315; + H&#8322;O",
        "aqueous KOH, packed bed",
        "Fans",
    )
)
BOX1_MID = BOX1_Y + BOX_H / 2
parts.append(f'<path d="M10,{BOX1_MID} L{BOX_X - 5},{BOX1_MID}" fill="none" stroke="{INK}" stroke-width="1.2" marker-end="url(#arrow)"/>')
parts.append(f'<text x="10" y="{BOX1_MID - 8}" font-size="10.3" fill="{INK}">air</text>')

# ---- loaded solution: contactor -> BPMED ----
parts.append(f'<path d="M{CX},{BOX1_Y + BOX_H} L{CX},{BOX2_Y - 5}" fill="none" stroke="{INK}" stroke-width="1.2" marker-end="url(#arrow)"/>')
parts.append(f'<text x="{CX + 10}" y="{BOX1_Y + BOX_H + 22}" font-size="9.3" fill="{GREY}">loaded solution</text>')
parts.append(f'<text x="{CX + 10}" y="{BOX1_Y + BOX_H + 34}" font-size="9.3" fill="{GREY}">(CO&#8323;&#178;&#8315;/HCO&#8323;&#8315;)</text>')

# ---- BPMED stack ----
parts.append(
    box(BOX_X, BOX2_Y, BOX_W, BOX_H, "BPMED stack", "H&#8322;O &#8594; H&#8314; + OH&#8315; (electricity)", "bipolar membrane", "Electrolysis")
)

# ---- base stream recycled back to contactor (loop over the top) ----
LOOP_Y = 32
parts.append(
    f'<path d="M{BOX_X + 40},{BOX2_Y} L{BOX_X + 40},{LOOP_Y} L{CX},{LOOP_Y} L{CX},{BOX1_Y - 5}" '
    f'fill="none" stroke="{BASE}" stroke-width="1.3" stroke-dasharray="5 3" marker-end="url(#arrowBase)"/>'
)
parts.append(f'<rect x="{BOX_X + 40 - 8}" y="{LOOP_Y - 9}" width="170" height="13" fill="#FFFFFF"/>')
parts.append(f'<text x="{BOX_X + 45}" y="{LOOP_Y + 2}" font-size="8.8" fill="{BASE}">base stream (OH&#8315;) recycled</text>')

# ---- acid stream: BPMED -> CO2 release ----
parts.append(f'<path d="M{CX},{BOX2_Y + BOX_H} L{CX},{BOX3_Y - 5}" fill="none" stroke="{ACID}" stroke-width="1.3" marker-end="url(#arrowAcid)"/>')
parts.append(f'<text x="{CX + 10}" y="{BOX2_Y + BOX_H + 22}" font-size="9.3" fill="{ACID}">acid stream (H&#8314;),</text>')
parts.append(f'<text x="{CX + 10}" y="{BOX2_Y + BOX_H + 34}" font-size="9.3" fill="{ACID}">lowers pH</text>')

# ---- CO2 release ----
parts.append(
    box(
        BOX_X,
        BOX3_Y,
        BOX_W,
        BOX_H,
        "CO&#8322; release",
        "CO&#8323;&#178;&#8315; + 2H&#8314; &#8594; CO&#8322;(g) + H&#8322;O",
        "strips CO&#8322; out of solution",
        ("Drying &amp;", "compression"),
    )
)

# ---- output ----
OUT_Y = BOX3_Y + BOX_H
parts.append(f'<path d="M{CX},{OUT_Y} L{CX},{OUT_Y + 35}" fill="none" stroke="{INK}" stroke-width="1.4" marker-end="url(#arrow)"/>')
parts.append(f'<text x="{CX}" y="{OUT_Y + 55}" font-size="12" font-weight="700" fill="{INK}" text-anchor="middle">CO&#8322;(g)</text>')
parts.append(
    f'<text x="{CX}" y="{OUT_Y + 70}" font-size="9.3" fill="{GREY}" text-anchor="middle" font-style="italic">to storage / utilisation</text>'
)

parts.append("</svg>")

svg = "\n".join(parts)
OUT_PATH.write_text(svg, encoding="utf-8")
print("wrote", OUT_PATH, len(svg), "bytes")
