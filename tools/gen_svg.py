"""Generate dark_mode.svg / light_mode.svg for the profile README.

    python tools/gen_svg.py .          # writes both cards to the given directory

The cards are generated, not hand-edited: to change a row's text, edit rows() below and
re-run. Values are written with placeholders that today.py replaces with live stats on the
next run, so run `python today.py` after regenerating or the cards ship dummy numbers.

Edit the portrait with tools/make_art.py, not here -- this only lays out art.txt.

Layout contract shared with today.py's justify_format():

    ". " + key + ":" + dots + value

justify_format sets dots to " " + "."*(length - len(value)) + " ", so a row's rendered
width is 5 + len(key) + length -- independent of the value. Reserving `length` per
dynamic field is what keeps the right edge from twitching as the numbers grow.

That identity only holds while (length - len(value)) > 2; below that justify_format
collapses the dots to ''/' '/'. ' and the row shrinks. Keep the reserves generous.

Any reserve changed here must be changed identically in today.py's RESERVE, or the row
will be laid out to one width and rewritten to another. test_today.py catches that.
"""
import os
import sys

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art.txt")


def art(path=ART):
    """The ASCII portrait, built separately by make_art.py."""
    with open(path) as f:
        return [l.rstrip("\n") for l in f if l.strip()]


W = 66  # content columns in the right-hand panel
CHAR_W = 9.6  # px advance of one cell at 16px Consolas w/ size-adjust 109%
ART_X = 15
GUTTER = 20  # gap between the art and the panel
ROW_H = 20
TOP = 30

# Derived from art.txt so the portrait can change size without hand-editing the layout.
_ART = art()
ART_COLS = max(len(l) for l in _ART)
PANEL_X = ART_X + round(ART_COLS * CHAR_W) + GUTTER
# The panel is centred against the art when the art is taller, so a tall portrait does not
# leave the right-hand column hanging with dead space beneath it.
PANEL_TOP = TOP

THEMES = {
    "dark_mode.svg": dict(bg="#161b22", fg="#c9d1d9", key="#ffa657", value="#a5d6ff",
                          add="#3fb950", dele="#f85149", cc="#616e7f"),
    "light_mode.svg": dict(bg="#f6f8fa", fg="#24292f", key="#953800", value="#0a3069",
                           add="#1a7f37", dele="#cf222e", cc="#c2cfde"),
}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dots(n):
    """Render n columns of leader dots exactly the way justify_format would."""
    return " " + "." * n + " " if n > 2 else {0: "", 1: " ", 2: ". "}[n]


def k(name):
    """Key tspan, splitting Foo.Bar so both halves get the key colour like neofetch."""
    sep = '<tspan class="cc">.</tspan>'
    return sep.join(f'<tspan class="key">{p}</tspan>' for p in name.split("."))


def static_row(y, key, value):
    n = W - 5 - len(key) - len(value)
    assert n >= 0, f"row too wide: {key}: {value}"
    return (f'<tspan x="{PANEL_X}" y="{y}" class="cc">. </tspan>{k(key)}<tspan class="cc">:</tspan>'
            f'<tspan class="cc">{dots(n)}</tspan><tspan class="value">{esc(value)}</tspan>')


def reserve(key, suffix=""):
    """The `length` svg_overwrite must pass for a row, so it renders exactly W columns.

    Must equal today.py's RESERVE for the same id. test_today.py fails if they drift.
    """
    return W - 5 - len(key) - len(suffix)


def dyn_row(y, key, eid, value, cls="value", suffix=""):
    """A row today.py rewrites, sized so its right edge never moves."""
    length = reserve(key, suffix)
    n = length - len(value)
    assert n > 2, f"reserve too tight for {eid}: {value!r} in {length}"
    tail = f'<tspan class="{cls}">{suffix}</tspan>' if suffix else ""
    return (f'<tspan x="{PANEL_X}" y="{y}" class="cc">. </tspan>{k(key)}<tspan class="cc">:</tspan>'
            f'<tspan class="cc" id="{eid}_dots">{dots(n)}</tspan>'
            f'<tspan class="{cls}" id="{eid}">{esc(value)}</tspan>{tail}')


def rule(y, label):
    """Section rule: label plus dashes out to the panel width."""
    text = f"- {label} " if label else ""
    return (f'<tspan x="{PANEL_X}" y="{y}" class="fg">{esc(text)}</tspan>'
            f'<tspan class="cc">{"-" * (W - len(text))}</tspan>')


def blank(y):
    return f'<tspan x="{PANEL_X}" y="{y}" class="cc">. </tspan>'


def header(y, who):
    return (f'<tspan x="{PANEL_X}" y="{y}" class="value">{esc(who)}</tspan>'
            f'<tspan class="cc"> {"-" * (W - len(who) - 1)}</tspan>')


# --- panel content -----------------------------------------------------------------
# Only facts Gajendra gave or that GitHub reports. No invented rows.
#
# Every stat gets its own row rather than sharing one. Sharing forced the reserves narrow
# enough that leader dots collapsed and the right edge moved -- the bug upstream still has.
# One value per row makes each reserve = W - 5 - len(key), which is wide enough by
# construction, and fills the panel to the portrait's height.
def rows(top=TOP):
    y = top
    out = []

    def add(fn, *a, **kw):
        nonlocal y
        out.append(fn(y, *a, **kw))
        y += ROW_H

    add(header, "gajendra@nishad")
    add(blank)
    add(rule, "System")
    add(static_row, "OS", "Linux")
    add(dyn_row, "Uptime", "age_data", "5 years, 7 months, 7 days")
    add(static_row, "Host", "BWH")
    add(static_row, "Kernel", "Engineer")
    add(static_row, "IDE", "Neovim")
    add(static_row, "Timezone", "Asia/Kolkata (IST)")
    add(blank)
    add(rule, "Languages")
    add(static_row, "Languages.Programming", "Python, JavaScript")
    add(static_row, "Languages.Frameworks", "Frappe, Django, Flask")
    add(static_row, "Languages.Databases", "MariaDB, MySQL")
    add(static_row, "Languages.Computer", "HTML, CSS, SCSS, JSON")
    add(blank)
    add(rule, "Interests")
    add(static_row, "Hobbies", "Living in the terminal")
    add(blank)
    add(rule, "Contact")
    add(static_row, "Email.Personal", "gajendranishad.dev@gmail.com")
    add(static_row, "GitHub", "gajjug004")
    add(static_row, "LinkedIn", "gajju004")
    add(static_row, "Website", "bwh.tech")
    add(static_row, "Location", "Jagdalpur, India")
    add(blank)
    add(rule, "GitHub Stats")
    add(dyn_row, "Repos", "repo_data", "38")
    add(dyn_row, "Contributed", "contrib_data", "92")
    add(dyn_row, "Organizations", "org_data", "frappe, bwhtech")
    add(dyn_row, "Stars", "star_data", "1")
    add(dyn_row, "Followers", "follower_data", "5")
    add(dyn_row, "Commits", "commit_data", "494")
    add(dyn_row, "Pull Requests", "pr_data", "96")
    add(dyn_row, "Issues", "issue_data", "9")
    add(blank)
    add(dyn_row, "Lines of Code on GitHub", "loc_data", "222,778")
    add(dyn_row, "LOC.Added", "loc_add", "299,038", cls="addColor", suffix="++")
    add(dyn_row, "LOC.Deleted", "loc_del", "76,260", cls="delColor", suffix="--")
    return out, y - ROW_H


# What today.py's RESERVE must contain. Printed by --reserves so the two stay in step.
RESERVES = {
    "age_data": reserve("Uptime"),
    "repo_data": reserve("Repos"),
    "contrib_data": reserve("Contributed"),
    "org_data": reserve("Organizations"),
    "star_data": reserve("Stars"),
    "follower_data": reserve("Followers"),
    "commit_data": reserve("Commits"),
    "pr_data": reserve("Pull Requests"),
    "issue_data": reserve("Issues"),
    "loc_data": reserve("Lines of Code on GitHub"),
    "loc_add": reserve("LOC.Added", "++"),
    "loc_del": reserve("LOC.Deleted", "--"),
}


def build(theme, lines, art_lines, height, width, panel_top):
    t = THEMES[theme]
    art_tspans = "\n".join(
        f'<tspan x="{ART_X}" y="{TOP + i * ROW_H}">{esc(l)}</tspan>' for i, l in enumerate(art_lines))
    return f'''<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="{width}px" height="{height}px" font-size="16px">
<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {t["key"]};}}
.value {{fill: {t["value"]};}}
.addColor {{fill: {t["add"]};}}
.delColor {{fill: {t["dele"]};}}
.cc {{fill: {t["cc"]};}}
.fg {{fill: {t["fg"]};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="{width}px" height="{height}px" fill="{t["bg"]}" rx="15"/>
<text x="{ART_X}" y="{TOP}" fill="{t["fg"]}" class="ascii">
{art_tspans}
</text>
<text x="{PANEL_X}" y="{panel_top}" fill="{t["fg"]}">
{chr(10).join(lines)}
</text>
</svg>
'''


if __name__ == "__main__":
    if "--reserves" in sys.argv:
        print("Paste into today.py's RESERVE:")
        print("RESERVE = " + repr(RESERVES))
        sys.exit()

    out_dir = sys.argv[1]
    art_lines = art()
    art_rows = len(art_lines)

    # Centre the panel against the art when the art is the taller of the two.
    n_panel_rows = len(rows()[0])
    panel_top = TOP + max(0, (art_rows - n_panel_rows) // 2) * ROW_H
    lines, last_y = rows(panel_top)

    height = max(last_y, TOP + (art_rows - 1) * ROW_H) + ROW_H
    width = PANEL_X + round(W * CHAR_W) + 15
    print(f"art {ART_COLS}x{art_rows} | panel {W}x{n_panel_rows} at y={panel_top} | canvas {width}x{height}")
    for name in THEMES:
        with open(f"{out_dir}/{name}", "w") as f:
            f.write(build(name, lines, art_lines, height, width, panel_top))
        print("wrote", name)
