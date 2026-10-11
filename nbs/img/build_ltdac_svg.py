r"""Generate ltdac_diagram.svg.

A professional, journal-style schematic of low-temperature DAC (LT-DAC) via
solid-sorbent temperature/vacuum-swing adsorption (TVSA) - the same
technology class as Climeworks' commercial plants - laid out as a narrow,
tall (portrait) figure sized for a single column of a two-column manuscript
(e.g. Elsevier's elsarticle two-column layout), matching the companion
E-DAC figure (nbs/img/build_edac_svg.py).

Process: a fan draws ambient air through a bed of solid amine sorbent,
which binds CO2 at ambient temperature (adsorption). The bed is then sealed
and heated to a low regeneration temperature (~80-120C - low enough to be
driven by waste heat rather than dedicated fuel, unlike liquid-solvent DAC's
500-900C), releasing the CO2 and regenerating the sorbent (desorption).
Steam co-released during desorption is condensed out, separating it from
the CO2 gas product; the cooled, regenerated sorbent is recycled back to
the contactor for another adsorption cycle. See the TVSA/low-grade-heat DAC
review literature (e.g. "Temperature-vacuum swing adsorption for direct air
capture by using low-grade heat") and Climeworks' published DAC+S
methodology for the >95% CO2 purity figure. This repo does not cite a
specific sorbent-chemistry paper for LT-DAC (its numbers are an internal
waste-heat energy-balance assumption tied to co-located gas-CCS generation
- see nbs/ltdac_diagram.ipynb for those model-specific details); this
figure grounds only the physical process, as was done for E-DAC's BPMED.

Plain hand-authored SVG: thin black strokes, no fills beyond white, minimal
colour used to distinguish the regeneration/recycle streams and energy-use
corner badges - a journal figure, not a coloured infographic. Boxes are
stacked vertically so the whole schematic fits a single narrow column,
matching build_edac_svg.py's conventions so the two figures read as a pair.

To edit the figure: change a coordinate/label below, then run:
    python nbs/img/build_ltdac_svg.py
from the repo root (or anywhere - this script has no path dependencies), and
re-execute the notebook so its embedded copy picks up the change:
    jupyter nbconvert --to notebook --execute --inplace nbs/ltdac_diagram.ipynb \
        --ExecutePreprocessor.kernel_name=uk-energy-current

To sanity-check layout while iterating, render the SVG to PNG with a headless
browser and inspect it, e.g. (Windows/Edge):
    msedge --headless --disable-gpu --screenshot=preview.png --window-size=420,530 ltdac_diagram.svg
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "ltdac_diagram.svg"

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
    'aria-label="Schematic of low-temperature DAC (LT-DAC) via solid-sorbent temperature/vacuum-swing '
    "adsorption. Ambient air is drawn through a solid amine sorbent bed, which binds CO2 at ambient "
    "temperature. The sorbent is then regenerated by sealing the bed under vacuum and heating it to a "
    "low temperature, releasing CO2 and steam. The steam is condensed out, separating it from the CO2 "
    "gas product, while the cooled, regenerated sorbent is recycled back to the contactor. Energy is "
    "used by fans in the air contactor, sorbent heating during regeneration, and drying and compression "
    'after CO2 separation.">'
)
parts.append("<title>Low-temperature DAC (LT-DAC) via solid-sorbent TVSA</title>")
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

# ---- Air contactor (adsorption) ----
parts.append(
    box(
        BOX_X,
        BOX1_Y,
        BOX_W,
        BOX_H,
        "Air contactor (adsorption)",
        "CO&#8322;(g) + sorbent &#8652; sorbent&#183;CO&#8322;",
        "solid amine sorbent, ambient",
        "Fans",
    )
)
BOX1_MID = BOX1_Y + BOX_H / 2
parts.append(f'<path d="M10,{BOX1_MID} L{BOX_X - 5},{BOX1_MID}" fill="none" stroke="{INK}" stroke-width="1.2" marker-end="url(#arrow)"/>')
parts.append(f'<text x="10" y="{BOX1_MID - 8}" font-size="10.3" fill="{INK}">air</text>')

# ---- CO2-laden sorbent: contactor -> desorption ----
parts.append(f'<path d="M{CX},{BOX1_Y + BOX_H} L{CX},{BOX2_Y - 5}" fill="none" stroke="{INK}" stroke-width="1.2" marker-end="url(#arrow)"/>')
parts.append(f'<text x="{CX + 10}" y="{BOX1_Y + BOX_H + 22}" font-size="9.3" fill="{GREY}">CO&#8322;-laden</text>')
parts.append(f'<text x="{CX + 10}" y="{BOX1_Y + BOX_H + 34}" font-size="9.3" fill="{GREY}">sorbent</text>')

# ---- Desorption (regeneration) ----
parts.append(
    box(
        BOX_X,
        BOX2_Y,
        BOX_W,
        BOX_H,
        "Desorption (regeneration)",
        "sorbent&#183;CO&#8322; &#8594; sorbent + CO&#8322;(g)",
        "vacuum + low-grade heat, ~80-120&#176;C",
        ("Sorbent", "heating"),
    )
)

# ---- regenerated sorbent recycled back to contactor (loop over the top) ----
LOOP_Y = 32
parts.append(
    f'<path d="M{BOX_X + 40},{BOX2_Y} L{BOX_X + 40},{LOOP_Y} L{CX},{LOOP_Y} L{CX},{BOX1_Y - 5}" '
    f'fill="none" stroke="{BASE}" stroke-width="1.3" stroke-dasharray="5 3" marker-end="url(#arrowBase)"/>'
)
parts.append(f'<rect x="{BOX_X + 40 - 8}" y="{LOOP_Y - 9}" width="190" height="13" fill="#FFFFFF"/>')
parts.append(f'<text x="{BOX_X + 45}" y="{LOOP_Y + 2}" font-size="8.8" fill="{BASE}">sorbent regenerated, recycled</text>')

# ---- CO2 + steam: desorption -> separation ----
parts.append(f'<path d="M{CX},{BOX2_Y + BOX_H} L{CX},{BOX3_Y - 5}" fill="none" stroke="{ACID}" stroke-width="1.3" marker-end="url(#arrowAcid)"/>')
parts.append(f'<text x="{CX + 10}" y="{BOX2_Y + BOX_H + 22}" font-size="9.3" fill="{ACID}">CO&#8322; + steam,</text>')
parts.append(f'<text x="{CX + 10}" y="{BOX2_Y + BOX_H + 34}" font-size="9.3" fill="{ACID}">released</text>')

# ---- CO2 separation ----
parts.append(
    box(
        BOX_X,
        BOX3_Y,
        BOX_W,
        BOX_H,
        "CO&#8322; separation",
        "CO&#8322;(g) + H&#8322;O(g) &#8594; CO&#8322;(g) + H&#8322;O(l)",
        "steam condensed; &gt;95% CO&#8322; purity",
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
