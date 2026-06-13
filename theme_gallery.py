#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Headless screenshot gallery of zellij built-in themes.

For each theme: start zellij inside an isolated tmux server, split panes,
inject sample content, capture the ANSI screen, render it to PNG with the
ptyxis font, then build a montage contact sheet with ImageMagick.

Usage:
  theme_gallery.py                       # all themes
  theme_gallery.py --themes dracula,nord # subset
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

THEMES = [
    "ansi", "ao", "atelier", "ayu-dark", "ayu-light", "ayu-mirage",
    "blade-runner", "catppuccin-frappe", "catppuccin-latte",
    "catppuccin-macchiato", "catppuccin-mocha", "cyber-noir", "dayfox",
    "dracula", "everforest-dark", "everforest-light", "flexoki-dark",
    "gruber-darker", "gruvbox-dark", "gruvbox-light", "iceberg-dark",
    "iceberg-light", "kanagawa", "lucario", "menace", "molokai-dark",
    "night-owl", "nightfox", "nord", "one-half-dark", "onedark",
    "pencil-light", "retro-wave", "solarized-dark", "solarized-light",
    "terafox", "tokyo-night-dark", "tokyo-night-light",
    "tokyo-night-storm", "tokyo-night", "vesper",
]

TMUX_SOCKET = "zjgallery"
COLS, ROWS = 100, 30
FONT_NAME = "JetBrainsMono Nerd Font"
FONT_SIZE = 16
READY_TIMEOUT = 10.0

# ptyxis default (GNOME) 16-color palette — pane content colors.
PALETTE16 = [
    (0x17, 0x14, 0x21), (0xC0, 0x1C, 0x28), (0x26, 0xA2, 0x69), (0xA2, 0x73, 0x4C),
    (0x12, 0x48, 0x8B), (0xA3, 0x47, 0xBA), (0x2A, 0xA1, 0xB3), (0xD0, 0xCF, 0xCC),
    (0x5E, 0x5C, 0x64), (0xF6, 0x61, 0x51), (0x33, 0xDA, 0x7A), (0xE9, 0xAD, 0x0C),
    (0x2A, 0x7B, 0xDE), (0xC0, 0x61, 0xCB), (0x33, 0xC7, 0xDE), (0xFF, 0xFF, 0xFF),
]
DEFAULT_FG = (0xD0, 0xCF, 0xCC)
DEFAULT_BG = (0x17, 0x14, 0x21)

# 3-pane layout mirroring the user's real session. Each pane runs a sample
# script directly — no typing into interactive shells (atuin/ble.sh interfere).
LAYOUT_KDL = """\
layout {{
    tab name="Tab #1" focus=true hide_floating_panes=true {{
        pane size=1 borderless=true {{
            plugin location="zellij:tab-bar"
        }}
        pane split_direction="vertical" {{
            pane name="src" focus=true size="50%" command="bash" {{
                args "{left}"
            }}
            pane size="50%" {{
                pane name="palette" size="50%" command="bash" {{
                    args "{right}"
                }}
                pane name="git log" size="50%" command="bash" {{
                    args "{bottom}"
                }}
            }}
        }}
        pane size=1 borderless=true {{
            plugin location="zellij:status-bar"
        }}
    }}
}}
"""

LEFT_SH = r"""
printf '\n  \033[1;34msrc/\033[0m\n  \033[1;34mdocs/\033[0m\n'
printf '  \033[32mREADME.md\033[0m\n  \033[33mpyproject.toml\033[0m\n\n'
printf '  \033[1mThe quick brown fox jumps over the lazy dog\033[0m\n'
printf '  0123456789 {}[]()<> != == ->\n\n'
printf '  \033[2m~/code/project\033[0m \033[35m❯\033[0m\n'
sleep 1000
"""
RIGHT_SH = r"""
printf '\n  ANSI palette\n\n  '
for i in 0 1 2 3 4 5 6 7; do printf '\033[48;5;%sm    \033[0m' "$i"; done
printf '\n  '
for i in 8 9 10 11 12 13 14 15; do printf '\033[48;5;%sm    \033[0m' "$i"; done
printf '\n\n  '
for i in 1 2 3 4 5 6; do printf '\033[3%sm text \033[0m' "$i"; done
printf '\n'
sleep 1000
"""
BOTTOM_SH = r"""
printf '\n  \033[33mabc1234\033[0m (\033[36mHEAD -> main\033[0m) feat: add theme gallery\n'
printf '  \033[33mdef5678\033[0m fix: parse SGR colors\n'
printf '  \033[33m9abcdef\033[0m docs: update readme\n'
sleep 1000
"""


def clean_env() -> dict:
    env = os.environ.copy()
    for var in ("TMUX", "TMUX_PANE", "ZELLIJ", "ZELLIJ_SESSION_NAME", "ZELLIJ_PANE_ID"):
        env.pop(var, None)
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    return env


ENV = clean_env()


def tmux(*args, check=False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["tmux", "-L", TMUX_SOCKET, *args],
        env=ENV, capture_output=True, text=True, check=check,
    )


def capture() -> str:
    return tmux("capture-pane", "-e", "-p", "-t", "cap").stdout


def wait_ready(timeout: float = READY_TIMEOUT) -> bool:
    """Wait until zellij has drawn its UI (enough non-blank rows)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        plain = re.sub(r"\x1b\[[0-9;:]*m", "", capture())
        if sum(1 for line in plain.splitlines() if line.strip()) >= 10:
            return True
        time.sleep(0.3)
    return False


def wait_screen(predicate, timeout: float = READY_TIMEOUT) -> bool:
    """Poll the captured screen (plain text) until predicate matches."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        plain = re.sub(r"\x1b\[[0-9;:]*m", "", capture())
        if predicate(plain):
            return True
        time.sleep(0.3)
    return False


def shoot_theme(theme: str, tmux_conf: str, layout: str) -> str | None:
    """Run zellij with `theme` inside tmux, return captured ANSI screen."""
    session = f"zjgal-{theme}"
    try:
        tmux(
            "-f", tmux_conf, "new-session", "-d", "-s", "cap",
            "-x", str(COLS), "-y", str(ROWS),
            "zellij", "--session", session,
            "options", "--theme", theme, "--default-layout", layout,
        )
        if not wait_ready():
            return None
        # Sample output rendered in all panes.
        wait_screen(lambda s: "ANSI palette" in s and "abc1234" in s)
        time.sleep(0.5)

        return capture()
    finally:
        subprocess.run(["zellij", "kill-session", session], env=ENV, capture_output=True)
        time.sleep(0.3)
        subprocess.run(
            ["zellij", "delete-session", "--force", session], env=ENV, capture_output=True
        )
        tmux("kill-server")
        time.sleep(0.2)


# ---------------------------------------------------------------- rendering

def xterm256(n: int) -> tuple[int, int, int]:
    if n < 16:
        return PALETTE16[n]
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return (steps[n // 36], steps[(n // 6) % 6], steps[n % 6])
    v = 8 + (n - 232) * 10
    return (v, v, v)


class Attrs:
    __slots__ = ("fg", "bg", "bold", "dim", "underline", "reverse")

    def __init__(self):
        self.reset()

    def reset(self):
        self.fg = None  # None = default
        self.bg = None
        self.bold = self.dim = self.underline = self.reverse = False

    def copy(self) -> "Attrs":
        a = Attrs.__new__(Attrs)
        for s in Attrs.__slots__:
            setattr(a, s, getattr(self, s))
        return a


def apply_sgr(attrs: Attrs, params: str):
    # Normalize colon sub-params ("38:2::r:g:b") into flat token list.
    tokens: list[int] = []
    for part in params.split(";"):
        if ":" in part:
            sub = [int(x) if x else 0 for x in part.split(":")]
            if len(sub) >= 2 and sub[0] in (38, 48) and sub[1] == 2 and len(sub) >= 6:
                sub = [sub[0], 2, *sub[-3:]]  # drop colorspace field
            tokens.extend(sub)
        else:
            tokens.append(int(part) if part else 0)

    i = 0
    while i < len(tokens):
        p = tokens[i]
        if p == 0:
            attrs.reset()
        elif p == 1:
            attrs.bold = True
        elif p == 2:
            attrs.dim = True
        elif p == 4:
            attrs.underline = True
        elif p == 7:
            attrs.reverse = True
        elif p == 22:
            attrs.bold = attrs.dim = False
        elif p == 24:
            attrs.underline = False
        elif p == 27:
            attrs.reverse = False
        elif 30 <= p <= 37:
            attrs.fg = PALETTE16[p - 30]
        elif p == 39:
            attrs.fg = None
        elif 40 <= p <= 47:
            attrs.bg = PALETTE16[p - 40]
        elif p == 49:
            attrs.bg = None
        elif 90 <= p <= 97:
            attrs.fg = PALETTE16[p - 90 + 8]
        elif 100 <= p <= 107:
            attrs.bg = PALETTE16[p - 100 + 8]
        elif p in (38, 48) and i + 1 < len(tokens):
            target = "fg" if p == 38 else "bg"
            mode = tokens[i + 1]
            if mode == 5 and i + 2 < len(tokens):
                setattr(attrs, target, xterm256(tokens[i + 2]))
                i += 2
            elif mode == 2 and i + 4 < len(tokens):
                setattr(attrs, target, tuple(tokens[i + 2 : i + 5]))
                i += 4
        i += 1


SGR_RE = re.compile(r"\x1b\[([0-9;:]*)m")
OTHER_ESC_RE = re.compile(r"\x1b\[[0-9;?]*[A-LN-Za-ln-z]|\x1b[^[]")


def parse_screen(ansi: str) -> list[list[tuple[str, Attrs]]]:
    grid = []
    attrs = Attrs()
    for raw in ansi.splitlines()[:ROWS]:
        raw = OTHER_ESC_RE.sub("", raw)
        row: list[tuple[str, Attrs]] = []
        pos = 0
        for m in SGR_RE.finditer(raw):
            for ch in raw[pos : m.start()]:
                row.append((ch, attrs.copy()))
            apply_sgr(attrs, m.group(1))
            pos = m.end()
        for ch in raw[pos:]:
            row.append((ch, attrs.copy()))
        row = row[:COLS] + [(" ", attrs.copy())] * (COLS - len(row))
        grid.append(row)
    pad = Attrs()
    while len(grid) < ROWS:
        grid.append([(" ", pad)] * COLS)
    return grid


def find_font(style: str) -> ImageFont.FreeTypeFont:
    path = subprocess.run(
        ["fc-match", "-f", "%{file}", f"{FONT_NAME}:style={style}"],
        capture_output=True, text=True,
    ).stdout.strip()
    return ImageFont.truetype(path, FONT_SIZE)


def render_png(ansi: str, out_path: Path, fonts: dict):
    grid = parse_screen(ansi)
    regular, bold = fonts["regular"], fonts["bold"]
    cw = round(regular.getlength("M"))
    ascent, descent = regular.getmetrics()
    ch_h = ascent + descent

    img = Image.new("RGB", (COLS * cw, ROWS * ch_h), DEFAULT_BG)
    draw = ImageDraw.Draw(img)

    for y, row in enumerate(grid):
        for x, (ch, a) in enumerate(row):
            fg = a.fg or DEFAULT_FG
            bg = a.bg or DEFAULT_BG
            if a.reverse:
                fg, bg = bg, fg
            if a.dim:
                fg = tuple((f + b) // 2 for f, b in zip(fg, bg))
            x0, y0 = x * cw, y * ch_h
            if bg != DEFAULT_BG:
                draw.rectangle([x0, y0, x0 + cw - 1, y0 + ch_h - 1], fill=bg)
            if ch not in (" ", " "):
                draw.text((x0, y0), ch, font=bold if a.bold else regular, fill=fg)
            if a.underline:
                draw.line([x0, y0 + ascent + 1, x0 + cw - 1, y0 + ascent + 1], fill=fg)

    img.save(out_path)


def build_montage(out_dir: Path, themes: list[str]):
    args = ["magick", "montage", "-background", "#101010", "-fill", "#cccccc"]
    for t in themes:
        args += ["-label", t, str(out_dir / f"{t}.png")]
    args += ["-geometry", "800x+10+10", "-tile", "3x", str(out_dir / "gallery.png")]
    subprocess.run(args, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--themes", help="comma-separated subset (default: all)")
    ap.add_argument("--out", default="~/Pictures/zellij-themes", help="output dir")
    args = ap.parse_args()

    themes = args.themes.split(",") if args.themes else THEMES
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    fonts = {"regular": find_font("Regular"), "bold": find_font("Bold")}

    done, failed = [], []
    with tempfile.TemporaryDirectory(prefix="zjgallery-") as tmp:
        tmp = Path(tmp)
        (tmp / "tmux.conf").write_text(
            'set -g status off\n'
            'set -g default-terminal "tmux-256color"\n'
            'set -ga terminal-overrides ",*:Tc"\n'
        )
        panes = {}
        for name, body in (("left", LEFT_SH), ("right", RIGHT_SH), ("bottom", BOTTOM_SH)):
            path = tmp / f"{name}.sh"
            path.write_text(body)
            panes[name] = str(path)
        (tmp / "layout.kdl").write_text(LAYOUT_KDL.format(**panes))

        try:
            for theme in themes:
                print(
                    f"[{len(done) + len(failed) + 1}/{len(themes)}] {theme} ... ",
                    end="", flush=True,
                )
                ansi = shoot_theme(theme, str(tmp / "tmux.conf"), str(tmp / "layout.kdl"))
                if ansi is None:
                    print("FAILED (zellij did not start)")
                    failed.append(theme)
                    continue
                render_png(ansi, out_dir / f"{theme}.png", fonts)
                print("ok")
                done.append(theme)
        finally:
            tmux("kill-server")

    if done:
        build_montage(out_dir, done)
        print(f"\n{len(done)} themes -> {out_dir}/gallery.png")
    if failed:
        print(f"failed: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
