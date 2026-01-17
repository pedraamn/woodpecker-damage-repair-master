#!/usr/bin/env python3
"""
Single-file static site generator (no JS) supporting 4 modes:

  1) regular   : /{city}-{st}/
  2) cost      : regular + /cost/{city}-{st}/ (city-specific cost pages)
  3) state     : /{st}/ then /{st}/{city}/
  4) subdomain : each city is its own subdomain (links/canonicals become absolute)

Usage:
  python3 generate.py
  python3 -m http.server 8000 --directory public

ENV (optional):
  SITE_ORIGIN="https://example.com"          # used for absolute canonicals
  SUBDOMAIN_BASE="example.com"               # used for subdomain links/canonicals
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import csv
import html
import os
import re
import shutil


# ============================================================
# US STATE NAMES (no dependency)
# ============================================================

US_STATE_NAMES: dict[str, str] = {
  "AL": "Alabama",
  "AK": "Alaska",
  "AZ": "Arizona",
  "AR": "Arkansas",
  "CA": "California",
  "CO": "Colorado",
  "CT": "Connecticut",
  "DE": "Delaware",
  "FL": "Florida",
  "GA": "Georgia",
  "HI": "Hawaii",
  "ID": "Idaho",
  "IL": "Illinois",
  "IN": "Indiana",
  "IA": "Iowa",
  "KS": "Kansas",
  "KY": "Kentucky",
  "LA": "Louisiana",
  "ME": "Maine",
  "MD": "Maryland",
  "MA": "Massachusetts",
  "MI": "Michigan",
  "MN": "Minnesota",
  "MS": "Mississippi",
  "MO": "Missouri",
  "MT": "Montana",
  "NE": "Nebraska",
  "NV": "Nevada",
  "NH": "New Hampshire",
  "NJ": "New Jersey",
  "NM": "New Mexico",
  "NY": "New York",
  "NC": "North Carolina",
  "ND": "North Dakota",
  "OH": "Ohio",
  "OK": "Oklahoma",
  "OR": "Oregon",
  "PA": "Pennsylvania",
  "RI": "Rhode Island",
  "SC": "South Carolina",
  "SD": "South Dakota",
  "TN": "Tennessee",
  "TX": "Texas",
  "UT": "Utah",
  "VT": "Vermont",
  "VA": "Virginia",
  "WA": "Washington",
  "WV": "West Virginia",
  "WI": "Wisconsin",
  "WY": "Wyoming",
  "DC": "District of Columbia",
}


# ============================================================
# CONFIG
# ============================================================

@dataclass(frozen=True)
class SiteConfig:
  # Data
  cities_csv: Path = Path("cities.csv")

  # Build / assets
  output_dir: Path = Path("public")
  image_filename: str = "picture.png"  # sits next to generate.py

  # Identity
  base_name: str = "Woodpecker Damage Repair"
  brand_name: str = "Woodpecker Damage Repair Company"

  # CTA
  cta_text: str = "Get Free Estimate"
  cta_href: str = "/contact/"

  # Pricing base
  cost_low: int = 350
  cost_high: int = 1500

  # Core titles/subs
  h1_title: str = "Woodpecker Damage Repair/Woodpecker Hole Repair/Siding Repair Services"
  h1_short: str = "Woodpecker Damage Repair Services"
  h1_sub: str = "Weather-tight siding and trim repairs that seal holes, match finishes, and reduce repeat damage."

  cost_title: str = "Woodpecker Damage Repair Cost"
  cost_sub: str = "Typical pricing ranges, scope examples, and what drives the total for siding and trim repairs."

  howto_title: str = "How Woodpecker Damage Repair Works"
  howto_sub: str = "A practical, homeowner-friendly guide to how repairs are typically done and when DIY breaks down."

  # Content (minimal placeholders; keep your real text here)
  main_h2: tuple[str, ...] = (
    "What Is Woodpecker Damage Repair?",
    "Why Are Woodpeckers Pecking My House?",
    "When to Hire a Professional for Woodpecker Damage Repair",
  )
  main_p: tuple[str, ...] = (
    "Woodpecker damage repair seals and restores holes in siding and trim so the exterior is weather-tight again.",
    "Woodpeckers peck to search for insects, create nesting cavities, or drum to mark territory.",
    "Hire a pro when damage is widespread, ladder work is required, or finish matching matters.",
  )

  howto_h2: tuple[str, ...] = (
    "Quick Answer",
    "How Repairs Are Typically Done",
    "When DIY Often Fails",
  )
  howto_p: tuple[str, ...] = (
    "Most repairs remove weak material, seal the opening, patch/replace sections, and restore the finish.",
    "Pros focus on moisture control and adhesion so the repair lasts.",
    "DIY often fails when underlying wood is soft or the repair is not fully sealed.",
  )

  cost_h2: tuple[str, ...] = (
    "Quick Answer",
    "What Affects Pricing?",
    "Key Takeaways",
  )
  cost_p: tuple[str, ...] = (
    "Woodpecker damage repair typically costs {cost_lo} to {cost_hi}, depending on scope and finish work.",
    "Big drivers are repair count, access height, substrate condition, and finish matching.",
    "Scattered damage and repainting/blending usually push totals higher.",
  )

  # Local cost snippet
  location_cost_h2: str = "How Much Does Woodpecker Damage Repair Cost in {City, State}?"
  location_cost_p: str = (
    "In {City, State}, most projects range from {cost_lo} to {cost_hi}, depending on scope and access. "
    "Prices vary with local labor rates and finish matching needs."
  )


CONFIG = SiteConfig()

CityWithCol = tuple[str, str, float]


# ============================================================
# LOAD CITIES
# ============================================================

def load_cities_from_csv(path: Path) -> tuple[CityWithCol, ...]:
  out: list[CityWithCol] = []
  with path.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    required = {"city", "state", "col"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
      raise ValueError(f"CSV must have headers: city,state,col (found: {reader.fieldnames})")

    for i, row in enumerate(reader, start=2):
      city = (row.get("city") or "").strip()
      state = (row.get("state") or "").strip().upper()
      col_raw = (row.get("col") or "").strip()
      if not city or not state or not col_raw:
        raise ValueError(f"Missing city/state/col at CSV line {i}: {row}")
      try:
        col = float(col_raw)
      except ValueError as e:
        raise ValueError(f"Invalid col at CSV line {i}: {col_raw!r}") from e
      out.append((city, state, col))
  return tuple(out)


CITIES: tuple[CityWithCol, ...] = load_cities_from_csv(CONFIG.cities_csv)


# ============================================================
# HELPERS
# ============================================================

def esc(s: str) -> str:
  return html.escape(s, quote=True)

def slugify(s: str) -> str:
  s = s.strip().lower()
  s = re.sub(r"&", " and ", s)
  s = re.sub(r"[^a-z0-9]+", "-", s)
  s = re.sub(r"-{2,}", "-", s).strip("-")
  return s

def clamp_title(title: str, max_chars: int = 70) -> str:
  if len(title) <= max_chars:
    return title
  return title[: max_chars - 1].rstrip() + "…"

def state_full(abbr: str) -> str:
  return US_STATE_NAMES.get(abbr.upper(), abbr.upper())

def write_text(path: Path, content: str) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(content, encoding="utf-8")

def reset_output_dir(p: Path) -> None:
  if p.exists():
    shutil.rmtree(p)
  p.mkdir(parents=True, exist_ok=True)

def copy_site_image(*, src_dir: Path, out_dir: Path, filename: str) -> None:
  src = src_dir / filename
  if not src.exists():
    raise FileNotFoundError(f"Missing image next to generate.py: {src}")
  shutil.copyfile(src, out_dir / filename)

def cities_by_state(cities: tuple[CityWithCol, ...]) -> dict[str, list[CityWithCol]]:
  m: dict[str, list[CityWithCol]] = {}
  for city, st, col in cities:
    m.setdefault(st, []).append((city, st, col))
  for st in m:
    m[st].sort(key=lambda t: t[0].lower())
  return m

def linkify_curly(text: str, *, home_href: str) -> str:
  """
  Replace {text} with a link to the home page.
  """
  parts: list[str] = []
  last = 0
  for m in re.finditer(r"\{([^}]+)\}", text):
    parts.append(esc(text[last:m.start()]))
    parts.append(f'<a href="{esc(home_href)}">{esc(m.group(1))}</a>')
    last = m.end()
  parts.append(esc(text[last:]))
  return "".join(parts)


# ============================================================
# MODE + URLS
# ============================================================

Mode = str  # "regular" | "cost" | "state" | "subdomain"

SITE_ORIGIN = (os.environ.get("SITE_ORIGIN") or "").rstrip("/")
SUBDOMAIN_BASE = (os.environ.get("SUBDOMAIN_BASE") or "").strip().lower().strip(".")

def rel_city_path_regular(city: str, st: str) -> str:
  return f"/{slugify(city)}-{slugify(st)}/"

def rel_city_path_state(city: str, st: str) -> str:
  return f"/{slugify(st)}/{slugify(city)}/"

def abs_city_origin_subdomain(city: str, st: str) -> str:
  # subdomain slug uses the same {city}-{st} slug
  slug = f"{slugify(city)}-{slugify(st)}"
  base = SUBDOMAIN_BASE or (SITE_ORIGIN.replace("https://", "").replace("http://", "").split("/")[0] if SITE_ORIGIN else "")
  if not base:
    # fallback: relative if user didn't set SUBDOMAIN_BASE/SITE_ORIGIN
    return f"/{slug}/"
  return f"https://{slug}.{base}/"

def href_home(mode: Mode) -> str:
  if mode == "subdomain":
    # root domain homepage
    return SITE_ORIGIN + "/" if SITE_ORIGIN else "/"
  return "/"

def href_city(mode: Mode, city: str, st: str) -> str:
  if mode == "state":
    return rel_city_path_state(city, st)
  if mode == "subdomain":
    return abs_city_origin_subdomain(city, st)
  return rel_city_path_regular(city, st)

def href_state(mode: Mode, st: str) -> str:
  # only relevant in state mode; others can ignore
  return f"/{slugify(st)}/"

def href_cost_index(mode: Mode) -> str:
  # cost index always lives on root domain paths
  return (SITE_ORIGIN + "/cost/") if (mode == "subdomain" and SITE_ORIGIN) else "/cost/"

def href_howto_index(mode: Mode) -> str:
  return (SITE_ORIGIN + "/how-to/") if (mode == "subdomain" and SITE_ORIGIN) else "/how-to/"

def href_contact(mode: Mode) -> str:
  return (SITE_ORIGIN + "/contact/") if (mode == "subdomain" and SITE_ORIGIN) else "/contact/"

def canonical_for(mode: Mode, path_or_abs: str) -> str:
  # If already absolute, keep it. Otherwise, upgrade to absolute when SITE_ORIGIN is available.
  if path_or_abs.startswith("http://") or path_or_abs.startswith("https://"):
    return path_or_abs
  if SITE_ORIGIN:
    return SITE_ORIGIN + path_or_abs
  return path_or_abs


# ============================================================
# THEME (small but complete)
# ============================================================

CSS = """
:root{
  --bg:#fafaf9; --surface:#fff; --ink:#111827; --muted:#4b5563; --line:#e7e5e4; --soft:#f5f5f4;
  --cta:#16a34a; --cta2:#15803d; --max:980px; --radius:16px;
  --shadow:0 10px 30px rgba(17,24,39,.06); --shadow2:0 10px 24px rgba(17,24,39,.08);
}
*{box-sizing:border-box}
body{margin:0;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;color:var(--ink);background:var(--bg);line-height:1.6}
a{color:inherit}
.topbar{position:sticky;top:0;z-index:50;background:rgba(250,250,249,.92);backdrop-filter:saturate(140%) blur(10px);border-bottom:1px solid var(--line)}
.topbar-inner{max-width:var(--max);margin:0 auto;padding:12px 18px;display:flex;align-items:center;justify-content:space-between;gap:14px}
.brand{font-weight:900;letter-spacing:-.02em;text-decoration:none}
.nav{display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-end}
.nav a{text-decoration:none;font-size:13px;color:var(--muted);padding:7px 10px;border-radius:12px;border:1px solid transparent}
.nav a:hover{background:var(--soft);border-color:var(--line)}
.nav a[aria-current="page"]{color:var(--ink);background:var(--soft);border:1px solid var(--line)}
.btn{display:inline-block;padding:9px 12px;background:var(--cta);color:#fff;border-radius:12px;text-decoration:none;font-weight:900;font-size:13px;border:1px solid rgba(0,0,0,.04);box-shadow:0 8px 18px rgba(22,163,74,.18)}
.btn:hover{background:var(--cta2)}
header{border-bottom:1px solid var(--line);background:radial-gradient(1200px 380px at 10% -20%, rgba(22,163,74,.08), transparent 55%),radial-gradient(900px 320px at 95% -25%, rgba(17,24,39,.06), transparent 50%),#fbfbfa}
.hero{max-width:var(--max);margin:0 auto;padding:34px 18px 24px;display:grid;gap:10px}
.hero h1{margin:0;font-size:30px;letter-spacing:-.03em;line-height:1.18}
.sub{margin:0;color:var(--muted);max-width:78ch;font-size:14px}
main{max-width:var(--max);margin:0 auto;padding:22px 18px 46px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px;box-shadow:var(--shadow)}
.img{margin-top:14px;border-radius:14px;overflow:hidden;border:1px solid var(--line);background:var(--soft);box-shadow:var(--shadow2);width:100%}
.img img{display:block;width:100%;height:auto}
@media (min-width:900px){.img{max-width:50%;margin-left:auto;margin-right:auto}}
h2{margin:18px 0 8px;font-size:16px;letter-spacing:-.01em}
p{margin:0 0 10px}
.muted{color:var(--muted);font-size:13px}
hr{border:0;border-top:1px solid var(--line);margin:18px 0}
.city-grid{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
.city-grid a{display:block;text-decoration:none;color:var(--ink);background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px;font-weight:800;font-size:14px;box-shadow:0 10px 24px rgba(17,24,39,.05)}
.city-grid a:hover{transform:translateY(-1px);box-shadow:0 14px 28px rgba(17,24,39,.08)}
footer{border-top:1px solid var(--line);background:#fbfbfa}
.footer-inner{max-width:var(--max);margin:0 auto;padding:28px 18px;display:grid;gap:10px}
.footer-links{display:flex;gap:12px;flex-wrap:wrap}
.footer-links a{color:var(--muted);text-decoration:none;font-size:13px}
.small{color:var(--muted);font-size:12px}
@media (max-width:640px){
  .topbar-inner{flex-direction:column;align-items:stretch;gap:10px}
  .nav{justify-content:center}
  .nav .btn{width:100%;text-align:center}
}
""".strip()


# ============================================================
# HTML PRIMITIVES
# ============================================================

def nav_html(
  *,
  mode: Mode,
  current: str,
  show_cost: bool = True,
  show_howto: bool = True,
  show_contact: bool = True,
) -> str:
  def item(href: str, label: str, key: str) -> str:
    cur = ' aria-current="page"' if current == key else ""
    return f'<a href="{esc(href)}"{cur}>{esc(label)}</a>'

  parts: list[str] = []
  parts.append(item(href_home(mode), "Home", "home"))

  if show_cost:
    parts.append(item(href_cost_index(mode), "Cost", "cost"))
  if show_howto:
    parts.append(item(href_howto_index(mode), "How-To", "howto"))

  if show_contact:
    parts.append(f'<a class="btn" href="{esc(href_contact(mode))}">{esc(CONFIG.cta_text)}</a>')

  return '<nav class="nav" aria-label="Primary navigation">' + "".join(parts) + "</nav>"


def base_html(
  *,
  mode: Mode,
  title: str,
  canonical: str,
  current_nav: str,
  body: str,
  nav_show_cost: bool = True,
  nav_show_howto: bool = True,
  nav_show_contact: bool = True,
) -> str:
  return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(title)}</title>
  <link rel="canonical" href="{esc(canonical_for(mode, canonical))}" />
  <style>
{CSS}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <a class="brand" href="{esc(href_home(mode))}">{esc(CONFIG.brand_name)}</a>
      {nav_html(mode=mode, current=current_nav, show_cost=nav_show_cost, show_howto=nav_show_howto, show_contact=nav_show_contact)}
    </div>
  </div>
{body}
</body>
</html>
"""


def header_block(*, h1: str, sub: str) -> str:
  return f"""
<header>
  <div class="hero">
    <h1>{esc(h1)}</h1>
    <p class="sub">{esc(sub)}</p>
  </div>
</header>
""".rstrip()

def footer_block(*, mode: Mode, show_cta: bool = True, show_cost: bool = True, show_howto: bool = True) -> str:
  cta_html = ""
  if show_cta:
    cta_html = f"""
    <h2>Next steps</h2>
    <p class="sub">Ready to move forward? Request a free quote.</p>
    <div>
      <a class="btn" href="{esc(href_contact(mode))}">{esc(CONFIG.cta_text)}</a>
    </div>
""".rstrip()

  links: list[str] = [f'<a href="{esc(href_home(mode))}">Home</a>']
  if show_cost:
    links.append(f'<a href="{esc(href_cost_index(mode))}">Cost</a>')
  if show_howto:
    links.append(f'<a href="{esc(href_howto_index(mode))}">How-To</a>')

  return f"""
<footer>
  <div class="footer-inner">
    {cta_html}
    <div class="footer-links">
      {''.join(links)}
    </div>
    <div class="small">© {esc(CONFIG.brand_name)}. All rights reserved.</div>
  </div>
</footer>
""".rstrip()


  return f"""
<footer>
  <div class="footer-inner">
    {cta_html}
    <div class="footer-links">
      <a href="{esc(href_home(mode))}">Home</a>
      <a href="{esc(href_cost_index(mode))}">Cost</a>
      <a href="{esc(href_howto_index(mode))}">How-To</a>
    </div>
    <div class="small">© {esc(CONFIG.brand_name)}. All rights reserved.</div>
  </div>
</footer>
""".rstrip()

def page_shell(
  *,
  h1: str,
  sub: str,
  inner_html: str,
  show_image: bool,
  show_footer_cta: bool,
  mode: Mode,
  footer_show_cost: bool = True,
  footer_show_howto: bool = True,
) -> str:
  img_html = ""
  if show_image:
    img_html = f"""
    <div class="img">
      <img src="/{esc(CONFIG.image_filename)}" alt="Service image" loading="lazy" />
    </div>
""".rstrip()

  return (
    header_block(h1=h1, sub=sub)
    + f"""
<main>
  <section class="card">
{img_html}
    {inner_html}
  </section>
</main>
"""
    + footer_block(mode=mode, show_cta=show_footer_cta, show_cost=footer_show_cost, show_howto=footer_show_howto)
  ).rstrip()

def make_page(
  *,
  mode: Mode,
  h1: str,
  canonical: str,
  nav_key: str,
  sub: str,
  inner: str,
  show_image: bool = True,
  show_footer_cta: bool = True,
  nav_show_cost: bool = True,
  nav_show_howto: bool = True,
  nav_show_contact: bool = True,
  footer_show_cost: bool = True,
  footer_show_howto: bool = True,
) -> str:
  h1 = clamp_title(h1, 70)
  title = h1  # enforce title == h1

  return base_html(
    mode=mode,
    title=title,
    canonical=canonical,
    current_nav=nav_key,
    nav_show_cost=nav_show_cost,
    nav_show_howto=nav_show_howto,
    nav_show_contact=nav_show_contact,
    body=page_shell(
      h1=h1,
      sub=sub,
      inner_html=inner,
      show_image=show_image,
      show_footer_cta=show_footer_cta,
      mode=mode,
      footer_show_cost=footer_show_cost,
      footer_show_howto=footer_show_howto,
    ),
  )

def make_section(*, headings: tuple[str, ...], paras: tuple[str, ...], home_href: str) -> str:
  parts: list[str] = []
  for h2, p in zip(headings, paras):
    parts.append(f"<h2>{esc(h2)}</h2>")
    parts.append(f"<p>{linkify_curly(p, home_href=home_href)}</p>")
  return "\n".join(parts)

def location_cost_section(city: str, st: str, col: float, home_href: str) -> str:
  cost_lo = f"<strong>${int(CONFIG.cost_low * col)}</strong>"
  cost_hi = f"<strong>${int(CONFIG.cost_high * col)}</strong>"

  h2 = CONFIG.location_cost_h2.replace("{City, State}", f"{city}, {st}")
  p = (
    CONFIG.location_cost_p
    .replace("{City, State}", f"{city}, {st}")
    .replace("{cost_lo}", cost_lo)
    .replace("{cost_hi}", cost_hi)
  )

  return f"<h2>{esc(h2)}</h2>\n<p>{linkify_curly(p, home_href=home_href)}</p>"


# ============================================================
# PAGE CONTENT FACTORIES
# ============================================================

def homepage_html(*, mode: Mode) -> str:
  links = "\n".join(
    f'<li><a href="{esc(href_city(mode, c, s))}">{esc(c)}, {esc(s)}</a></li>'
    for c, s, _ in CITIES
  )

  inner = (
    make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p, home_href=href_home(mode))
    + """
<hr />
<h2>Choose your city</h2>
<p class="muted">We provide services nationwide, including in the following cities:</p>
<ul class="city-grid">
"""
    + links
    + """
</ul>
"""
    + f"""
<hr />
<p class="muted">
  Also available: <a href="{esc(href_cost_index(mode))}">{esc(CONFIG.cost_title)}</a>
  and <a href="{esc(href_howto_index(mode))}">{esc(CONFIG.howto_title)}</a>.
</p>
"""
  )

  return make_page(
    mode=mode,
    h1=CONFIG.h1_title,
    canonical="/",
    nav_key="home",
    sub=CONFIG.h1_sub,
    inner=inner,
  )

def contact_page_html(*, mode: Mode) -> str:
  h1 = "Get Your Free Estimate"
  sub = "Fill out the form below and we’ll connect you with a qualified local professional."

  # Keep your embed here; minimal placeholder
  inner = """
<p class="muted">Embed your lead form here.</p>
"""

  return make_page(
    mode=mode,
    h1=h1,
    canonical="/contact/",
    nav_key="contact",
    sub=sub,
    inner=inner,
    show_image=False,
    show_footer_cta=False,
  )

def city_page_html(*, mode: Mode, city: str, st: str, col: float, canonical: str) -> str:
  inner = (
    location_cost_section(city, st, col, home_href=href_home(mode))
    + "<hr />\n"
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p, home_href=href_home(mode))
  )

  return make_page(
    mode=mode,
    h1=clamp_title(f"{CONFIG.h1_short} in {city}, {st}", 70),
    canonical=canonical,
    nav_key="home",
    sub=CONFIG.h1_sub,
    inner=inner,
  )

def cost_page_html(*, mode: Mode, include_city_index: bool) -> str:
  inner = make_section(
    headings=CONFIG.cost_h2,
    paras=tuple(
      p.replace("{cost_lo}", f"<strong>${CONFIG.cost_low}</strong>")
       .replace("{cost_hi}", f"<strong>${CONFIG.cost_high}</strong>")
      for p in CONFIG.cost_p
    ),
    home_href=href_home(mode),
  )

  if include_city_index:
    links = "\n".join(
      f'<li><a href="{esc(cost_city_href(mode, c, s))}">{esc(c)}, {esc(s)}</a></li>'
      for c, s, _ in CITIES
    )
    inner += (
      """
<hr />
<h2>Choose your city</h2>
<p class="muted">See local price ranges by city:</p>
<ul class="city-grid">
"""
      + links
      + """
</ul>
"""
    )

  return make_page(
    mode=mode,
    h1=CONFIG.cost_title,
    canonical="/cost/",
    nav_key="cost",
    sub=CONFIG.cost_sub,
    inner=inner,
  )

def cost_city_href(mode: Mode, city: str, st: str) -> str:
  # cost pages always on root domain paths
  if mode == "subdomain" and SITE_ORIGIN:
    return SITE_ORIGIN + f"/cost/{slugify(city)}-{slugify(st)}/"
  return f"/cost/{slugify(city)}-{slugify(st)}/"

def cost_city_page_html(*, mode: Mode, city: str, st: str, col: float) -> str:
  # canonical for the city cost page path
  canonical = f"/cost/{slugify(city)}-{slugify(st)}/"
  h1 = clamp_title(f"{CONFIG.cost_title} in {city}, {st}", 70)

  inner = (
    location_cost_section(city, st, col, home_href=href_home(mode))
    + "<hr />\n"
    + make_section(
      headings=CONFIG.cost_h2,
      paras=tuple(
        p.replace("{cost_lo}", f"<strong>${int(CONFIG.cost_low * col)}</strong>")
         .replace("{cost_hi}", f"<strong>${int(CONFIG.cost_high * col)}</strong>")
        for p in CONFIG.cost_p
      ),
      home_href=href_home(mode),
    )
    + f"""
<hr />
<p class="muted">
  Also available: <a href="{esc(href_city(mode, city, st))}">{esc(CONFIG.h1_short)} in {esc(city)}, {esc(st)}</a>
  and <a href="{esc(href_howto_index(mode))}">{esc(CONFIG.howto_title)}</a>.
</p>
"""
  )

  return make_page(
    mode=mode,
    h1=h1,
    canonical=canonical,
    nav_key="cost",
    sub=CONFIG.cost_sub,
    inner=inner,
  )

def howto_page_html(*, mode: Mode) -> str:
  inner = make_section(headings=CONFIG.howto_h2, paras=CONFIG.howto_p, home_href=href_home(mode))
  return make_page(
    mode=mode,
    h1=CONFIG.howto_title,
    canonical="/how-to/",
    nav_key="howto",
    sub=CONFIG.howto_sub,
    inner=inner,
  )

def state_homepage_html(*, mode: Mode) -> str:
  by_state = cities_by_state(CITIES)
  states = sorted(by_state.keys())

  links = "\n".join(
    f'<li><a href="{esc(href_state(mode, st))}">{esc(state_full(st))}</a></li>'
    for st in states
  )

  inner = (
    make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p, home_href=href_home(mode))
    + """
<hr />
<h2>Choose your state</h2>
<p class="muted">We provide services nationwide, including in the following states:</p>
<ul class="city-grid">
"""
    + links
    + """
</ul>
"""
  )

  return make_page(
    mode=mode,
    h1=CONFIG.h1_title,
    canonical="/",
    nav_key="home",
    sub=CONFIG.h1_sub,
    inner=inner,
  )

def state_page_html(*, mode: Mode, st: str, cities: list[CityWithCol]) -> str:
  links = "\n".join(
    f'<li><a href="{esc(href_city(mode, c, st))}">{esc(c)}, {esc(st)}</a></li>'
    for c, st, _ in cities
  )

  inner = f"""
<h2>Cities we serve in {esc(state_full(st))}</h2>
<p class="muted">Choose your city to see local details and typical pricing ranges.</p>
<ul class="city-grid">
{links}
</ul>
<hr />
<p class="muted">
  Also available: <a href="{esc(href_cost_index(mode))}">{esc(CONFIG.cost_title)}</a>
  and <a href="{esc(href_howto_index(mode))}">{esc(CONFIG.howto_title)}</a>.
</p>
""".strip()

  return make_page(
    mode=mode,
    h1=clamp_title(f"{CONFIG.h1_short} in {state_full(st)}", 70),
    canonical=f"/{slugify(st)}/",
    nav_key="home",
    sub=CONFIG.h1_sub,
    inner=inner,
  )


# ============================================================
# ROBOTS + SITEMAP + WRANGLER
# ============================================================

def robots_txt() -> str:
  return "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"

def sitemap_xml(urls: list[str]) -> str:
  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in urls)
    + "</urlset>\n"
  )

def wrangler_content() -> str:
  name = CONFIG.base_name.lower().replace(" ", "-")
  today = date.today().isoformat()
  return f"""{{
  "name": "{name}",
  "compatibility_date": "{today}",
  "assets": {{
    "directory": "./public"
  }}
}}
"""


# ============================================================
# BUILD MODES
# ============================================================

def build_common(*, out: Path, mode: Mode) -> list[str]:
  """
  Writes shared core pages for all modes.
  Returns list of sitemap URLs.
  """
  write_text(out / "cost" / "index.html", cost_page_html(mode=mode, include_city_index=(mode == "cost")))
  write_text(out / "how-to" / "index.html", howto_page_html(mode=mode))
  write_text(out / "contact" / "index.html", contact_page_html(mode=mode))

  urls = ["/", "/cost/", "/how-to/", "/contact/"]
  return urls

def build_regular(*, out: Path) -> None:
  mode: Mode = "regular"
  urls = build_common(out=out, mode=mode)
  write_text(out / "index.html", homepage_html(mode=mode))

  for city, st, col in CITIES:
    path = out / slugify(city) + "-" + slugify(st) / "index.html"  # incorrect type if not careful

def build_regular(*, out: Path) -> None:
  mode: Mode = "regular"
  urls = build_common(out=out, mode=mode)
  write_text(out / "index.html", homepage_html(mode=mode))

  for city, st, col in CITIES:
    slug = f"{slugify(city)}-{slugify(st)}"
    write_text(out / slug / "index.html", city_page_html(mode=mode, city=city, st=st, col=col, canonical=f"/{slug}/"))
    urls.append(f"/{slug}/")

  write_text(out / "robots.txt", robots_txt())
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ regular: Generated {len(urls)} pages into: {out.resolve()}")

def build_cost(*, out: Path) -> None:
  mode: Mode = "cost"
  urls = build_common(out=out, mode=mode)
  write_text(out / "index.html", homepage_html(mode=mode))

  # city pages
  for city, st, col in CITIES:
    slug = f"{slugify(city)}-{slugify(st)}"
    write_text(out / slug / "index.html", city_page_html(mode=mode, city=city, st=st, col=col, canonical=f"/{slug}/"))
    urls.append(f"/{slug}/")

  # city cost pages
  for city, st, col in CITIES:
    slug = f"{slugify(city)}-{slugify(st)}"
    write_text(out / "cost" / slug / "index.html", cost_city_page_html(mode=mode, city=city, st=st, col=col))
    urls.append(f"/cost/{slug}/")

  write_text(out / "robots.txt", robots_txt())
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ cost: Generated {len(urls)} pages into: {out.resolve()}")

def build_state(*, out: Path) -> None:
  mode: Mode = "state"
  urls = build_common(out=out, mode=mode)
  write_text(out / "index.html", state_homepage_html(mode=mode))

  by_state = cities_by_state(CITIES)
  for st, city_list in by_state.items():
    # /{st}/
    write_text(out / slugify(st) / "index.html", state_page_html(mode=mode, st=st, cities=city_list))
    urls.append(f"/{slugify(st)}/")

    # /{st}/{city}/
    for city, _, col in city_list:
      write_text(
        out / slugify(st) / slugify(city) / "index.html",
        city_page_html(mode=mode, city=city, st=st, col=col, canonical=f"/{slugify(st)}/{slugify(city)}/")
      )
      urls.append(f"/{slugify(st)}/{slugify(city)}/")

  write_text(out / "robots.txt", robots_txt())
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ state: Generated {len(urls)} pages into: {out.resolve()}")

def build_subdomain(*, out: Path) -> None:
  """
  We still output city pages into folders (for local preview / static host fallback),
  but in subdomain mode the links + canonicals for city pages are absolute:
    https://{city-st}.{SUBDOMAIN_BASE}/

  NOTE:
    - Home/Cost/How-To/Contact stay on the root domain.
    - City pages are meant to be served via host-based rewrites (Vercel/Cloudflare).
  """
  mode: Mode = "subdomain"
  urls = build_common(out=out, mode=mode)

  # root homepage lists city links as absolute subdomains
  write_text(out / "index.html", homepage_html(mode=mode))

  # city pages (rendered into folders for local preview),
  # but canonical is absolute subdomain origin
  for city, st, col in CITIES:
    slug = f"{slugify(city)}-{slugify(st)}"
    city_origin = abs_city_origin_subdomain(city, st)  # ends with /
    # write to /{slug}/index.html for preview
    write_text(
      out / slug / "index.html",
      city_page_html(mode=mode, city=city, st=st, col=col, canonical=city_origin)
    )
    # sitemap should include absolute city origins when possible
    urls.append(city_origin)

  write_text(out / "robots.txt", robots_txt())
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ subdomain: Generated {len(urls)} pages into: {out.resolve()}")

def build_regular_city_only(*, out: Path) -> None:
  """
  regular_city_only:
    - Generates / (homepage) + city pages /{city-st}/
    - Does NOT generate /cost/ or /how-to/
    - Navbar/Footer hide Cost + How-To
    - Keeps Contact CTA (you can disable it too if you want)
  """
  mode: Mode = "regular_city_only"
  urls: list[str] = ["/", "/contact/"]  # contact page still generated

  # Homepage (keep the city grid; hide Cost/How-To nav + footer links)
  write_text(
    out / "index.html",
    make_page(
      mode=mode,
      h1=CONFIG.h1_title,
      canonical="/",
      nav_key="home",
      sub=CONFIG.h1_sub,
      inner=(
        make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p, home_href=href_home(mode))
        + """
<hr />
<h2>Choose your city</h2>
<p class="muted">We provide services nationwide, including in the following cities:</p>
<ul class="city-grid">
"""
        + "\n".join(
          f'<li><a href="{esc(href_city(mode, c, s))}">{esc(c)}, {esc(s)}</a></li>'
          for c, s, _ in CITIES
        )
        + """
</ul>
"""
      ),
      nav_show_cost=False,
      nav_show_howto=False,
      footer_show_cost=False,
      footer_show_howto=False,
      show_footer_cta=True,   # keep CTA section
      nav_show_contact=True,  # keep CTA button
    ),
  )

  # Contact page (still useful since CTA exists)
  write_text(
    out / "contact" / "index.html",
    contact_page_html(mode=mode),
  )

  # City pages (exact same content as your existing city_page_html; only nav/footer differ)
  for city, st, col in CITIES:
    slug = f"{slugify(city)}-{slugify(st)}"
    write_text(
      out / slug / "index.html",
      make_page(
        mode=mode,
        h1=f"{CONFIG.h1_short} in {city}, {st}",
        canonical=f"/{slug}/",
        nav_key="home",
        sub=CONFIG.h1_sub,
        inner=(
          location_cost_section(city, st, col, home_href=href_home(mode))
          + "<hr />\n"
          + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p, home_href=href_home(mode))
        ),
        nav_show_cost=False,
        nav_show_howto=False,
        footer_show_cost=False,
        footer_show_howto=False,
        show_footer_cta=True,
        nav_show_contact=True,
      ),
    )
    urls.append(f"/{slug}/")

  write_text(out / "robots.txt", robots_txt())
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ regular_city_only: Generated {len(urls)} pages into: {out.resolve()}")


# ============================================================
# ENTRYPOINT
# ============================================================

SITE_MODE: Mode = "regular_city_only"
# "regular" | "cost" | "state" | "subdomain" | "regular_city_only"

def main() -> None:
  here = Path(__file__).resolve().parent
  out = here / CONFIG.output_dir

  reset_output_dir(out)
  copy_site_image(src_dir=here, out_dir=out, filename=CONFIG.image_filename)

  if SITE_MODE == "regular":
    build_regular(out=out)
  elif SITE_MODE == "cost":
    build_cost(out=out)
  elif SITE_MODE == "state":
    build_state(out=out)
  elif SITE_MODE == "subdomain":
    build_subdomain(out=out)
  elif SITE_MODE == "regular_city_only":
    build_regular_city_only(out=out)
  else:
    raise ValueError(f"Unknown SITE_MODE: {SITE_MODE!r}")

if __name__ == "__main__":
  main()

