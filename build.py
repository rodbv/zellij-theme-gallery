#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Generate the static gallery site from images/*.png.

Outputs: thumbs/*.webp, index.html, themes/<name>.html, style.css
"""

import hashlib
from pathlib import Path

from PIL import Image, ImageStat

ROOT = Path(__file__).parent
SITE_URL = "https://rodbv.github.io/zellij-theme-gallery"
THUMB_WIDTH = 600

CSS = """\
:root {
  --bg: #14141c;
  --card: #1d1d28;
  --fg: #d8d8e0;
  --muted: #8a8a99;
  --accent: #7aa2f7;
  --border: #2c2c3a;
}
@view-transition { navigation: auto; }
::view-transition-group(*) { animation-duration: 220ms; }
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 16px/1.5 system-ui, sans-serif;
}
header {
  padding: 2rem 1.5rem 1rem;
  max-width: 1400px;
  margin: 0 auto;
}
header h1 { margin: 0 0 0.3rem; font-size: 1.6rem; }
header p { margin: 0; color: var(--muted); }
header a { color: var(--accent); text-decoration: none; }
main { max-width: 1400px; margin: 0 auto; padding: 0.5rem 1.5rem 3rem; }

.toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.8rem;
  padding: 0.8rem 0;
  margin-bottom: 0.8rem;
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(8px);
}
.search {
  flex: 1 1 200px;
  max-width: 360px;
  padding: 0.5rem 0.9rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--fg);
  font: inherit;
}
.search:focus { outline: none; border-color: var(--accent); }
.chips { display: flex; gap: 0.4rem; }
.chip {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  padding: 0.3rem 0.9rem;
  font: inherit;
  font-size: 0.85rem;
  cursor: pointer;
}
.chip:hover { border-color: var(--accent); color: var(--fg); }
.chip.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #10101a;
  font-weight: 600;
}
.count { color: var(--muted); font-size: 0.85rem; margin-left: auto; }
kbd {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 0.35em;
  font-size: 0.8em;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.5rem;
}
.card {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  text-decoration: none;
  color: var(--fg);
  transition: border-color 0.12s;
}
.card:hover { border-color: var(--accent); }
.card:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.card.hidden { display: none; }
.card .thumb-wrap { width: 130px; flex-shrink: 0; overflow: hidden; }
.card img {
  display: block;
  width: 100%;
  height: auto;
  transition: transform 0.15s ease-out;
}
.card:hover img { transform: scale(1.06); }
.card .name {
  font-family: monospace;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.no-results { color: var(--muted); display: none; }

.detail-img-link { display: block; }
.detail-img {
  width: 100%;
  height: auto;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.full-hint { color: var(--muted); font-size: 0.8rem; margin: 0.3rem 0 0; }
.cmd-block { margin: 1.2rem 0; }
.cmd-block h2 { font-size: 1rem; color: var(--muted); margin: 0 0 0.4rem; }
.cmd {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.7rem 1rem;
}
.cmd code { flex: 1; font-size: 0.95rem; overflow-x: auto; white-space: nowrap; }
.cmd button {
  background: var(--accent);
  color: #10101a;
  border: none;
  border-radius: 6px;
  padding: 0.4rem 0.9rem;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
}
.cmd button:active { transform: scale(0.96); }
.cmd button:focus-visible { outline: 2px solid var(--fg); }
nav.pager {
  display: flex;
  justify-content: space-between;
  margin: 0 0 0.8rem;
  font-family: monospace;
}
nav.pager a { color: var(--accent); text-decoration: none; }
nav.pager a:hover { text-decoration: underline; }
.back { color: var(--muted); text-decoration: none; display: inline-block; margin-bottom: 1rem; }
.back:hover { color: var(--accent); }
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.cta {
  background: var(--accent);
  color: #10101a;
  border-radius: 999px;
  padding: 0.55rem 1.3rem;
  font-weight: 600;
  text-decoration: none;
  flex-shrink: 0;
}
.cta:hover { filter: brightness(1.1); }
.cta:focus-visible { outline: 2px solid var(--fg); outline-offset: 2px; }
#use { scroll-margin-top: 1rem; }
html { scroll-behavior: smooth; }
footer {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1.5rem 2rem;
  color: var(--muted);
  font-size: 0.85rem;
}
footer a { color: var(--accent); text-decoration: none; }
"""

INDEX_JS = """\
const cards = [...document.querySelectorAll('.card')];
const search = document.querySelector('.search');
const countEl = document.querySelector('.count');
const noResults = document.querySelector('.no-results');
const chips = [...document.querySelectorAll('.chip')];
let mode = 'all';

function apply() {
  const q = search.value.trim().toLowerCase();
  let visible = 0;
  for (const card of cards) {
    const hit = card.dataset.name.includes(q) &&
      (mode === 'all' || card.dataset.variant === mode);
    card.classList.toggle('hidden', !hit);
    if (hit) visible++;
  }
  noResults.style.display = visible ? 'none' : 'block';
  countEl.textContent = visible === cards.length
    ? `${cards.length} themes` : `${visible} / ${cards.length}`;
}

search.addEventListener('input', apply);
for (const chip of chips) {
  chip.addEventListener('click', () => {
    mode = chip.dataset.mode;
    chips.forEach(c => c.classList.toggle('active', c === chip));
    apply();
  });
}
document.addEventListener('keydown', e => {
  if (e.key === '/' && document.activeElement !== search) {
    e.preventDefault();
    search.focus();
  } else if (e.key === 'Escape' && document.activeElement === search) {
    search.value = '';
    apply();
  } else if (e.key === 'Enter' && document.activeElement === search) {
    const first = cards.find(c => !c.classList.contains('hidden'));
    if (first) location.href = first.href;
  }
});
apply();
"""

COPY_JS = """\
function copyCmd(btn) {
  const code = btn.parentElement.querySelector('code').textContent;
  navigator.clipboard.writeText(code).then(() => {
    const old = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = old; }, 1200);
  });
}
"""

DETAIL_JS = """\
document.addEventListener('keydown', e => {
  if (e.target.closest('input, textarea')) return;
  if (e.key === 'ArrowLeft' && PREV) location.href = PREV;
  else if (e.key === 'ArrowRight' && NEXT) location.href = NEXT;
  else if (e.key === 'Escape') location.href = '../index.html';
});
"""

FOOTER = """\
<footer>
  Screenshots generated headlessly with
  <a href="https://github.com/rodbv/zellij-theme-gallery">theme_gallery.py</a>
  &middot; <a href="https://zellij.dev/documentation/themes">zellij themes docs</a>
</footer>
"""

INDEX_TMPL = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zellij Theme Gallery</title>
<meta property="og:title" content="Zellij Theme Gallery">
<meta property="og:description" content="Screenshots of all {count} zellij built-in themes">
<meta property="og:image" content="{site}/images/dracula.png">
<link rel="stylesheet" href="style.css?v={css_hash}">
</head>
<body>
<header>
  <h1>Zellij Theme Gallery</h1>
  <p>{count} built-in themes of <a href="https://zellij.dev">zellij</a>,
     screenshotted automatically. Click a theme for the full image and setup command.
     Press <kbd>/</kbd> to search, <kbd>Enter</kbd> to open the first match.</p>
</header>
<main>
  <div class="toolbar">
    <input class="search" type="search" placeholder="Filter themes&hellip;"
           aria-label="Filter themes" autofocus>
    <div class="chips" role="group" aria-label="Filter by variant">
      <button class="chip active" data-mode="all">All</button>
      <button class="chip" data-mode="dark">Dark</button>
      <button class="chip" data-mode="light">Light</button>
    </div>
    <span class="count"></span>
  </div>
  <div class="grid">
{cards}
  </div>
  <p class="no-results">No themes match.</p>
</main>
{footer}
<script>
{index_js}
</script>
</body>
</html>
"""

CARD_TMPL = """\
    <a class="card" data-name="{name}" data-variant="{variant}" href="themes/{name}.html">
      <span class="thumb-wrap">
        <img src="thumbs/{name}.webp?v={img_hash}" alt="zellij {name} theme"
             width="{tw}" height="{th}" loading="lazy"
             style="view-transition-name: theme-{name}">
      </span>
      <span class="name">{name}</span>
    </a>
"""

DETAIL_TMPL = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — Zellij Theme Gallery</title>
<meta property="og:title" content="zellij theme: {name}">
<meta property="og:description" content="Screenshot and setup command for the {name} zellij theme">
<meta property="og:image" content="{site}/images/{name}.png">
<link rel="stylesheet" href="../style.css?v={css_hash}">
{prefetch}
<script>{copy_js}</script>
</head>
<body>
<header class="detail-header">
  <div>
    <a class="back" href="../index.html">&larr; all themes</a>
    <h1><code>{name}</code></h1>
  </div>
  <a class="cta" href="#use">Use this theme</a>
</header>
<main>
  <nav class="pager">
    <span>{prev_link}</span>
    <span>{next_link}</span>
  </nav>
  <a class="detail-img-link" href="../images/{name}.png?v={img_hash}" target="_blank" rel="noopener">
    <img class="detail-img" src="../images/{name}.png?v={img_hash}" alt="zellij {name} theme"
         width="{iw}" height="{ih}" style="view-transition-name: theme-{name}">
  </a>
  <p class="full-hint">Click image for full resolution</p>

  <section id="use">
    <div class="cmd-block">
      <h2>Set permanently — add to <code>~/.config/zellij/config.kdl</code></h2>
      <div class="cmd">
        <code>theme "{name}"</code>
        <button onclick="copyCmd(this)">Copy</button>
      </div>
    </div>

    <div class="cmd-block">
      <h2>Try it — start a new session with this theme</h2>
      <div class="cmd">
        <code>zellij options --theme {name}</code>
        <button onclick="copyCmd(this)">Copy</button>
      </div>
    </div>
  </section>
</main>
{footer}
<script>
const PREV = {prev_js};
const NEXT = {next_js};
{detail_js}
</script>
</body>
</html>
"""


def is_light(img: Image.Image) -> bool:
    """Classify by tab-bar luminance (top strip of the screenshot)."""
    strip = img.convert("RGB").crop((0, 0, img.width, 30))
    r, g, b = ImageStat.Stat(strip).mean
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 127


CROP_HEIGHT = 200  # px — tab-bar + top content rows


def main():
    images = sorted(p for p in (ROOT / "images").glob("*.png") if p.stem != "gallery")
    names = [p.stem for p in images]

    thumbs = ROOT / "thumbs"
    thumbs.mkdir(exist_ok=True)
    meta = {}  # name -> (variant, thumb_w, thumb_h, img_w, img_h, img_hash)
    for img_path in images:
        img = Image.open(img_path)
        crop = img.crop((0, 0, img.width, CROP_HEIGHT))
        ratio = THUMB_WIDTH / crop.width
        th = round(crop.height * ratio)
        variant = "light" if is_light(img) else "dark"
        img_hash = hashlib.md5(img_path.read_bytes()).hexdigest()[:8]
        meta[img_path.stem] = (variant, THUMB_WIDTH, th, img.width, img.height, img_hash)

        out = thumbs / f"{img_path.stem}.webp"
        if not (out.exists() and out.stat().st_mtime >= img_path.stat().st_mtime):
            crop.resize((THUMB_WIDTH, th), Image.LANCZOS).save(out, "WEBP", quality=80)

    cards = "".join(
        CARD_TMPL.format(
            name=n, variant=meta[n][0], tw=meta[n][1], th=meta[n][2],
            img_hash=meta[n][5],
        )
        for n in names
    )
    css_hash = hashlib.md5(CSS.encode()).hexdigest()[:8]
    (ROOT / "index.html").write_text(
        INDEX_TMPL.format(
            count=len(names), cards=cards, footer=FOOTER,
            index_js=INDEX_JS, site=SITE_URL, css_hash=css_hash,
        )
    )

    detail_dir = ROOT / "themes"
    detail_dir.mkdir(exist_ok=True)
    for i, name in enumerate(names):
        prev = names[i - 1]  # wraps: first → last
        nxt = names[(i + 1) % len(names)]  # wraps: last → first
        prefetch = "".join(
            f'<link rel="prefetch" href="../images/{n}.png">\n'
            for n in (prev, nxt)
        )
        (detail_dir / f"{name}.html").write_text(
            DETAIL_TMPL.format(
                name=name, site=SITE_URL, copy_js=COPY_JS, detail_js=DETAIL_JS,
                footer=FOOTER, css_hash=css_hash,
                iw=meta[name][3], ih=meta[name][4], img_hash=meta[name][5], prefetch=prefetch,
                prev_link=f'<a href="{prev}.html">&larr; Prev: {prev}</a>',
                next_link=f'<a href="{nxt}.html">Next: {nxt} &rarr;</a>',
                prev_js=f'"{prev}.html"',
                next_js=f'"{nxt}.html"',
            )
        )

    (ROOT / "style.css").write_text(CSS)
    (ROOT / ".nojekyll").touch()
    light = [n for n in names if meta[n][0] == "light"]
    print(f"built: index + {len(names)} detail pages + thumbs")
    print(f"light themes ({len(light)}): {', '.join(light)}")


if __name__ == "__main__":
    main()
