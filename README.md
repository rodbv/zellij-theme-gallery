# Zellij Theme Gallery

Screenshots of all 41 [zellij](https://zellij.dev) built-in themes, generated
fully headless — no desktop, no window flashing.

**Browse the gallery: <https://rodbv.github.io/zellij-theme-gallery/>**

Each theme page shows a full screenshot plus copy-paste commands to set the
theme permanently (`config.kdl`) or try it in a new session.

## How it works

- [`theme_gallery.py`](theme_gallery.py) runs zellij inside an isolated tmux
  server per theme, captures the ANSI screen with `tmux capture-pane -e`, and
  renders it to PNG with Pillow (JetBrainsMono Nerd Font). Panes run sample
  scripts via a 3-pane layout so the theme's chrome (frames, tab bar, status
  bar) is visible.
- [`build.py`](build.py) generates WebP thumbnails and the static HTML site
  from `images/*.png`.

## Regenerate

Requires: `zellij`, `tmux`, `uv`, ImageMagick, a Nerd Font.

```bash
./theme_gallery.py --out images   # screenshot all themes (~4 min)
./build.py                        # rebuild thumbs + HTML
```
