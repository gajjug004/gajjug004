"""Rebuild the ASCII portrait (art.txt) for the profile cards.

    python tools/make_art.py [image] [-W cols]

Thin wrapper over TheZoraiz/ascii-image-converter, which must be on PATH:
https://github.com/TheZoraiz/ascii-image-converter

Equivalent to `ascii-image-converter tools/portrait.jpeg -W 78`, saved to art.txt. The
wrapper exists only to pin the width and check the shape -- aic reads its default
dimensions from the terminal and panics when there isn't one (e.g. output piped to a file
or run from CI), so -W is always passed explicitly.

The default map inks bright pixels. That suits this portrait: it is backlit, so the blown-out
sky becomes the dense block and the shadowed subject reads as a silhouette against it. That
is the right way round on the dark card and a negative on the light one; one art serves both,
as upstream does. A photo lit the other way (dark hair, bright background behind a lit face)
wants `-m "@%#*+=-:. "` instead, or the subject drops out and the background becomes a slab.

Width drives the whole card: gen_svg.py sizes the canvas from art.txt, so a wider portrait
means a wider SVG and smaller text once GitHub scales it into its ~830px column. 78 columns
gives a 1433px card.

Regenerate the cards after this:
    python tools/gen_svg.py .    # then `python today.py` to refill live stats
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(HERE, "portrait.jpeg")
DEFAULT_WIDTH = 78


def build(src, width, out):
    aic = shutil.which("ascii-image-converter")
    if not aic:
        sys.exit("ascii-image-converter not found on PATH: "
                 "https://github.com/TheZoraiz/ascii-image-converter")
    run = subprocess.run([aic, src, "-W", str(width)], capture_output=True, text=True)
    if run.returncode != 0:
        sys.exit(f"aic failed: {run.stderr}")
    lines = [l for l in run.stdout.split("\n") if l.strip()]
    if not lines or any(len(l) != width for l in lines):
        sys.exit(f"expected rows of {width} chars, got {sorted({len(l) for l in lines})}")
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {out}: {width}x{len(lines)}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image", nargs="?", default=DEFAULT_SRC)
    p.add_argument("-W", "--width", type=int, default=DEFAULT_WIDTH)
    p.add_argument("--out", default=os.path.join(HERE, "art.txt"))
    a = p.parse_args()
    build(a.image, a.width, a.out)


if __name__ == "__main__":
    main()
