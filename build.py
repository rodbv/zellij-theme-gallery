#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Generate the static gallery site from images/*.png.

Outputs: thumbs/*.webp, index.html, themes/<name>.html, style.css
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
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
main { max-width: 1400px; margin: 0 auto; padding: 1rem 1.5rem 3rem; }
.search {
  width: 100%;
  max-width: 420px;
  margin: 0 0 1.2rem;
  padding: 0.55rem 0.9rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--fg);
  font: inherit;
}
.search:focus { outline: none; border-color: var(--accent); }
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
.card.hidden { display: none; }
.card img {
  display: block;
  width: 130px;
  height: auto;
  flex-shrink: 0;
}
.card .name {
  font-family: monospace;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.no-results { color: var(--muted); display: none; }
.detail-img {
  width: 100%;
  height: auto;
  border: 1px solid var(--border);
  border-radius: 10px;
}
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
nav.pager {
  display: flex;
  justify-content: space-between;
  margin: 1.5rem 0;
  font-family: monospace;
}
nav.pager a { color: var(--accent); text-decoration: none; }
.back { color: var(--muted); text-decoration: none; display: inline-block; margin-bottom: 1rem; }
.back:hover { color: var(--accent); }
footer {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1.5rem 2rem;
  color: var(--muted);
  font-size: 0.85rem;
}
footer a { color: var(--accent); text-decoration: none; }
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
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
  <h1>Zellij Theme Gallery</h1>
  <p>{count} built-in themes of <a href="https://zellij.dev">zellij</a>,
     screenshotted automatically. Click a theme for the full image and setup command.</p>
</header>
<main>
  <input class="search" type="search" placeholder="Filter themes&hellip;" autofocus
         oninput="filterThemes(this.value)">
  <div class="grid">
{cards}
  </div>
  <p class="no-results">No themes match.</p>
</main>
{footer}
<script>
function filterThemes(q) {{
  q = q.trim().toLowerCase();
  let visible = 0;
  document.querySelectorAll('.card').forEach(card => {{
    const hit = card.dataset.name.includes(q);
    card.classList.toggle('hidden', !hit);
    if (hit) visible++;
  }});
  document.querySelector('.no-results').style.display = visible ? 'none' : 'block';
}}
</script>
</body>
</html>
"""

CARD_TMPL = """\
    <a class="card" data-name="{name}" href="themes/{name}.html">
      <img src="thumbs/{name}.webp" alt="zellij {name} theme" loading="lazy">
      <div class="name">{name}</div>
    </a>
"""

DETAIL_TMPL = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — Zellij Theme Gallery</title>
<link rel="stylesheet" href="../style.css">
<script>{copy_js}</script>
</head>
<body>
<header>
  <a class="back" href="../index.html">&larr; all themes</a>
  <h1><code>{name}</code></h1>
</header>
<main>
  <img class="detail-img" src="../images/{name}.png" alt="zellij {name} theme">

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

  <nav class="pager">
    <span>{prev_link}</span>
    <span>{next_link}</span>
  </nav>
</main>
{footer}
</body>
</html>
"""


def main():
    images = sorted((ROOT / "images").glob("*.png"))
    names = [p.stem for p in images]

    thumbs = ROOT / "thumbs"
    thumbs.mkdir(exist_ok=True)
    for img_path in images:
        out = thumbs / f"{img_path.stem}.webp"
        if out.exists() and out.stat().st_mtime >= img_path.stat().st_mtime:
            continue
        img = Image.open(img_path)
        ratio = THUMB_WIDTH / img.width
        img.resize((THUMB_WIDTH, round(img.height * ratio)), Image.LANCZOS).save(
            out, "WEBP", quality=80
        )

    cards = "".join(CARD_TMPL.format(name=n) for n in names)
    (ROOT / "index.html").write_text(
        INDEX_TMPL.format(count=len(names), cards=cards, footer=FOOTER)
    )

    detail_dir = ROOT / "themes"
    detail_dir.mkdir(exist_ok=True)
    for i, name in enumerate(names):
        prev_link = (
            f'<a href="{names[i - 1]}.html">&larr; {names[i - 1]}</a>' if i > 0 else ""
        )
        next_link = (
            f'<a href="{names[i + 1]}.html">{names[i + 1]} &rarr;</a>'
            if i < len(names) - 1
            else ""
        )
        (detail_dir / f"{name}.html").write_text(
            DETAIL_TMPL.format(
                name=name, copy_js=COPY_JS, prev_link=prev_link,
                next_link=next_link, footer=FOOTER,
            )
        )

    (ROOT / "style.css").write_text(CSS)
    (ROOT / ".nojekyll").touch()
    print(f"built: index + {len(names)} detail pages + thumbs")


if __name__ == "__main__":
    main()
