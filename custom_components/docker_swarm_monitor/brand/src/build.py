"""Build Home Assistant brand assets for the Docker Swarm Monitor integration."""
import os
import cairosvg
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from PIL import Image

FONT_DIR = "/tmp/claude-0/-home-claude/7bc69931-2ae0-51da-8cf8-e79e5290e014/scratchpad/package/files"
OUT = "/home/claude/brand"
SRC = os.path.join(OUT, "src")
os.makedirs(SRC, exist_ok=True)

THEMES = {
    "light": dict(node_top="#2B88D8", node_bot="#0063B1", link="#6AA8DE",
                  text1="#1B1B1F", text2="#0063B1"),
    "dark":  dict(node_top="#4AA3E8", node_bot="#1674C8", link="#9CC7EE",
                  text1="#FFFFFF", text2="#7CC0F5"),
}

# Icon content bounding box (tight, square): x 40..472, y 56..488
VB_X, VB_Y, VB = 40, 56, 432


def icon_body(t, prefix):
    """SVG elements for the icon, in original 512 coordinates."""
    node = lambda cx, cy: f'''
    <g transform="translate({cx} {cy})">
      <rect x="-86" y="-74" width="172" height="148" rx="26" fill="url(#{prefix}node)"/>
      <g fill="#FFFFFF" opacity="0.94">
        <rect x="-56" y="-44" width="30" height="88" rx="7"/>
        <rect x="-15" y="-44" width="30" height="88" rx="7"/>
        <rect x="26" y="-44" width="30" height="88" rx="7"/>
      </g>
    </g>'''
    return f'''
  <defs>
    <linearGradient id="{prefix}node" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{t['node_top']}"/>
      <stop offset="1" stop-color="{t['node_bot']}"/>
    </linearGradient>
    <linearGradient id="{prefix}badge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#1DBF74"/>
      <stop offset="1" stop-color="#0E8A52"/>
    </linearGradient>
    <mask id="{prefix}cut" maskUnits="userSpaceOnUse" x="0" y="0" width="512" height="512">
      <rect width="512" height="512" fill="#fff"/>
      <circle cx="400" cy="420" r="84" fill="#000"/>
    </mask>
  </defs>
  <g mask="url(#{prefix}cut)">
    <g stroke="{t['link']}" stroke-width="18" stroke-linecap="round">
      <line x1="256" y1="130" x2="130" y2="330"/>
      <line x1="256" y1="130" x2="382" y2="330"/>
      <line x1="130" y1="330" x2="382" y2="330"/>
    </g>
    {node(256, 130)}{node(130, 330)}{node(382, 330)}
  </g>
  <g transform="translate(400 420)">
    <circle r="68" fill="url(#{prefix}badge)"/>
    <polyline points="-44,4 -20,4 -8,-26 8,30 20,-8 28,4 44,4" fill="none"
      stroke="#FFFFFF" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
  </g>'''


def text_path(text, font_file, size, x, baseline):
    """Convert text to an SVG path 'd' string; returns (d, advance_width)."""
    f = TTFont(os.path.join(FONT_DIR, font_file))
    upem = f["head"].unitsPerEm
    cmap, gs, hmtx = f.getBestCmap(), f.getGlyphSet(), f["hmtx"]
    s = size / upem
    pen = SVGPathPen(gs)
    cx = 0
    for ch in text:
        g = cmap[ord(ch)]
        tp = TransformPen(pen, (s, 0, 0, -s, x + cx * s, baseline))
        gs[g].draw(tp)
        cx += hmtx[g][0]
    return pen.getCommands(), cx * s


def icon_svg(theme):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VB_X} {VB_Y} {VB} {VB}">'
            f'{icon_body(THEMES[theme], "i")}</svg>')


def logo_svg(theme):
    t = THEMES[theme]
    size = 176
    gap = 70
    tx = VB_X + VB + gap
    # Two lines, vertically centred on the icon (cap height ~0.727em for Inter)
    cap = 0.727 * size
    line_gap = 0.42 * size
    block = cap * 2 + line_gap
    top = VB_Y + (VB - block) / 2
    d1, w1 = text_path("Docker Swarm", "inter-latin-600-normal.woff", size, tx, top + cap)
    d2, w2 = text_path("Monitor", "inter-latin-400-normal.woff", size, tx, top + 2 * cap + line_gap)
    width = (tx + max(w1, w2)) - VB_X + 8
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VB_X} {VB_Y} {width:.1f} {VB}">'
            f'{icon_body(t, "l")}'
            f'<path d="{d1}" fill="{t["text1"]}"/>'
            f'<path d="{d2}" fill="{t["text2"]}"/></svg>')


def render(svg, name, height):
    path = os.path.join(OUT, name)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=path, output_height=height)
    im = Image.open(path)
    bbox = im.getchannel("A").getbbox()
    if name.endswith("logo.png") or "logo@" in name:
        im = im.crop(bbox)  # logos: trim to content
        im.save(path)
    print(f"{name:20s} {im.size}  content bbox {bbox}")


for theme in THEMES:
    pre = "" if theme == "light" else "dark_"
    isvg, lsvg = icon_svg(theme), logo_svg(theme)
    open(os.path.join(SRC, f"{pre}icon.svg"), "w").write(isvg)
    open(os.path.join(SRC, f"{pre}logo.svg"), "w").write(lsvg)
    render(isvg, f"{pre}icon.png", 256)
    render(isvg, f"{pre}icon@2x.png", 512)
    render(lsvg, f"{pre}logo.png", 256)
    render(lsvg, f"{pre}logo@2x.png", 512)
