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
import sys
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
  image_filename: str = "woodpecker-damage-epoxy-repair.jpg"  # sits next to generate.py

  # Identity
  base_name: str = "Woodpecker Damage Repair"
  brand_name: str = "Woodpecker Damage Repair Experts"

  # CTA
  cta_text: str = "Get Free Estimate"
  cta_href: str = "/contact/"

  # Pricing base
  cost_low: int = 300
  cost_high: int = 800

  # Core titles/subs
  h1_title: str = "Woodpecker Damage/Hole Repair and Siding Repair Services"
  h1_short: str = "Woodpecker Damage Repair Services"
  h1_sub: str = "Weather-tight siding and trim repairs that seal holes, match finishes, and reduce repeat damage."

  cost_title: str = "Woodpecker Damage Repair Cost"
  cost_sub: str = "Typical pricing ranges, scope examples, and what drives the total for siding and trim repairs."

  howto_title: str = "How to Repair Woodpecker Damage"
  howto_sub: str = "A practical, homeowner-friendly guide to how repairs are typically done and when DIY breaks down."

  about_blurb: str = (
    "We provide professional woodpecker damage repair services{loc} for homeowners dealing with holes in siding, trim, and exterior wood. "
    "Our service repairs and seals woodpecker holes, restores damaged areas, and helps prevent moisture intrusion and repeat damage. "
    "Get a fast quote and professional service from a trusted local woodpecker damage repair expert."
  )



  # Content (minimal placeholders; keep your real text here)
  main_h2: tuple[str, ...] = (
    "What Kind of Damage Do Woodpeckers Cause to a House?",
    "Why Are Woodpeckers Pecking My House?",
    "What Do Woodpecker Holes Look Like in Siding or Trim?",
    "What Happens If Woodpecker Damage Is Left Unrepaired?",
    "Does Woodpecker Activity on a House Mean Termites?",
    "Is Woodpecker Damage Covered by Homeowners Insurance?",
    "How Do You Keep Woodpeckers Off Your House After Repairs?",
  )

  main_p: tuple[str,...] = (
    "Woodpeckers commonly damage homes by boring holes into siding, trim, fascia, and corner boards, which can expose exterior surfaces to moisture and pests. Even minor holes can weaken exterior wood and cause paint or material breakdown when water repeatedly enters.",
    "Woodpeckers typically peck houses to look for insects, form a nesting cavity, or drum against the surface to mark territory. Homes with exterior wood, shaded conditions, or existing damage are more likely to experience repeat activity if the cause isn’t addressed.",
    "Woodpecker holes usually show up as round openings, tight clusters of small holes, or deeper cavities created by repeated pecking. The size and grouping often reveal whether the bird was briefly probing or engaging in ongoing nesting or feeding.",
    "When woodpecker damage is left unrepaired, moisture can pass through the holes and slowly deteriorate nearby materials. Over time, this can lead to rot, peeling paint, and broader exterior damage that requires more extensive repairs.",
    "Woodpecker activity doesn’t always indicate termites, but it can point to insects living in or near the wood. Since birds may be targeting ants or larvae, evaluating the wood before sealing holes helps avoid trapping a hidden issue.",
    "Whether woodpecker damage is covered depends on how a homeowners insurance policy handles animal-related exterior damage. Some policies may cover sudden events, while others treat gradual damage as maintenance.",
    "Preventing woodpeckers from returning after repairs usually means removing what attracted them and limiting future access. Treating insect problems, reinforcing repaired sections, and protecting exposed exterior wood can reduce repeat damage.",
  )


  howto_h2: tuple[str, ...] = (
    "How Woodpecker Damage Is Typically Identified on a House",
    "How Professionals Determine Whether Damage Is Surface-Level or Structural",
    "How Different Repair Methods Are Used for Woodpecker Holes",
    "How Woodpecker Damage Is Sealed to Prevent Moisture Intrusion",
    "How Finish Matching Affects the Durability and Appearance of Repairs",
    "When Woodpecker Damage Repair Is Not a DIY-Friendly Project",
  )

  

  # Local cost snippet
  location_cost_h2: str = "How Much Does Woodpecker Damage Repair Cost{loc}?"
  location_cost_p: str = (
      "Woodpecker damage repair costs {loc} typically range between {cost_lo} and {cost_hi}, depending on how many holes need repair and how accessible the damaged areas are. "
      "Local labor rates and finish matching requirements can also influence the final price."
    )


COST_INNER = """
<section>
  <h2>Woodpecker Damage Repair Cost Ranges (Most Common Repairs)</h2>
  <div class="table-scroll">
    <table>
      <thead>
        <tr>
          <th>Repair Scenario</th>
          <th>Typical Cost Range</th>
          <th>What You’re Paying For</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Small hole repair (up to ~2")</td>
          <td>$150–$350</td>
          <td>Clean-out, epoxy patch/plug, seal, spot finish</td>
        </tr>
        <tr>
          <td>Medium hole repair (~2–6")</td>
          <td>$300–$800</td>
          <td>Deeper patch/plug, sealing, finish blending</td>
        </tr>
        <tr>
          <td>Large hole repair (over ~6")</td>
          <td>$600–$1,500</td>
          <td>Section rebuild or partial replacement, sealing, finish</td>
        </tr>
        <tr>
          <td>Replace a damaged siding board / small area</td>
          <td>$500–$2,500</td>
          <td>Remove/replace material, water management, finish match</td>
        </tr>
        <tr>
          <td>Structural repair (sheathing/stud/insulation affected)</td>
          <td>$1,000–$3,500+</td>
          <td>Open-up, replace damaged wood, restore weather barrier</td>
        </tr>
        <tr>
          <td>Interior wall repair (if penetrated)</td>
          <td>$250–$900</td>
          <td>Drywall patch, texture match, paint</td>
        </tr>
        <tr>
          <td>Paint/stain blending (separate line item)</td>
          <td>$150–$600</td>
          <td>Prime + blend to hide repair</td>
        </tr>
        <tr>
          <td>High access work (2nd story / steep roofline)</td>
          <td>+15% to +50%</td>
          <td>Setup time, safety, ladders or lift</td>
        </tr>
      </tbody>
    </table>
  </div>

  <p>
    <strong>Typical total:</strong> $300–$2,500.
    <strong>When hidden damage is present:</strong> $5,000+ is possible.
  </p>

  <hr />

  <h2>Cost by Severity (Fast Self-Assessment)</h2>

  <h3>Minor</h3>
  <ul>
    <li><strong>What it looks like:</strong> 1–2 small holes, shallow pecks, solid wood</li>
    <li><strong>Expected cost:</strong> $150–$500</li>
    <li><strong>Common repair:</strong> epoxy patch/plug + seal + spot finish</li>
  </ul>

  <h3>Moderate</h3>
  <ul>
    <li><strong>What it looks like:</strong> multiple holes in one zone, repeated pecking on the same board</li>
    <li><strong>Expected cost:</strong> $500–$2,500</li>
    <li><strong>Common repair:</strong> multi-hole patching or board/panel replacement + finish blending</li>
  </ul>

  <h3>Severe</h3>
  <ul>
    <li><strong>What it looks like:</strong> cavity access, soft/rotted wood, water staining, nesting attempts</li>
    <li><strong>Expected cost:</strong> $2,500–$5,000+</li>
    <li><strong>Common repair:</strong> open-up + structural repair + insulation/water barrier restoration</li>
  </ul>

  <hr />

  <h2>Repair Cost by Siding Material</h2>
  
  <div class="table-scroll">
    <table>
      <thead>
        <tr>
          <th>Siding Material</th>
          <th>Typical Repair Range</th>
          <th>Why It Costs More (or Less)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Wood lap siding</td>
          <td>$300–$3,000</td>
          <td>Finish matching + moisture protection are labor-heavy</td>
        </tr>
        <tr>
          <td>Cedar shake</td>
          <td>$500–$4,000</td>
          <td>Individual shake replacement + blend pattern/aging</td>
        </tr>
        <tr>
          <td>Vinyl siding</td>
          <td>$250–$2,000</td>
          <td>Often panel replacement; color matching varies by age</td>
        </tr>
        <tr>
          <td>Fiber cement</td>
          <td>$500–$3,500</td>
          <td>Cutting/fastening + repainting required</td>
        </tr>
        <tr>
          <td>Stucco</td>
          <td>$800–$4,500</td>
          <td>Multi-step patch + texture matching</td>
        </tr>
      </tbody>
    </table>
  </div>

  <hr />

  <h2>What Increases Woodpecker Repair Costs</h2>

  <ul>
    <li><strong>Hidden moisture:</strong> swelling, rot, or stained sheathing behind siding</li>
    <li><strong>Hole depth:</strong> penetration into cavity or insulation triggers bigger scope</li>
    <li><strong>Repeat targeting:</strong> multiple boards or corners need repair + protection</li>
    <li><strong>Access:</strong> second story, roofline, chimney, steep grade</li>
    <li><strong>Finish matching:</strong> older paint/stain requires blending, not just patching</li>
  </ul>

  <hr />

  <h2>When Patching Is Enough vs When Replacement Is Required</h2>

  <h3>Patching is usually enough if:</h3>
  <ul>
    <li>The wood is hard when probed</li>
    <li>Holes are shallow and limited to the surface</li>
    <li>No water staining, softness, or swelling is present</li>
  </ul>

  <h3>Replacement is usually required if:</h3>
  <ul>
    <li>The wood feels soft or spongy</li>
    <li>Holes are large, deep, or connected internally</li>
    <li>There is rot, cracking, swelling, or delamination</li>
    <li>The same board has been hit repeatedly</li>
  </ul>

  <p>
    <strong>Rule:</strong> If a screwdriver sinks in easily, replacement is more reliable than patching.
  </p>

  <hr />

  <h2>Prevention Costs (Avoid Paying Twice)</h2>

  <p>
    Repairs alone often get hit again. Physical exclusion is what consistently stops repeat damage.
  </p>

  <div class="table-scroll">
    <table>
      <thead>
        <tr>
          <th>Prevention Method</th>
          <th>Typical Cost</th>
          <th>Best Use</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Bird netting over the target area</td>
          <td>$150–$800</td>
          <td>Repeat pecking zones on siding walls</td>
        </tr>
        <tr>
          <td>Hardware cloth / barrier panels</td>
          <td>$150–$900</td>
          <td>Corners, fascia, trim boards that get repeatedly hit</td>
        </tr>
        <tr>
          <td>Metal flashing / corner protection</td>
          <td>$200–$1,000</td>
          <td>High-impact edges and roofline zones</td>
        </tr>
        <tr>
          <td>Professional wildlife exclusion / control</td>
          <td>$300–$1,500</td>
          <td>Persistent activity or nesting attempts</td>
        </tr>
        <tr>
          <td>Visual deterrents (tape/decoys)</td>
          <td>$20–$150</td>
          <td>Short-term support only (not a primary fix)</td>
        </tr>
      </tbody>
    </table>
  </div>

  <hr />

  <h2>What a Siding Repair Quote Should Include</h2>

  <ul>
    <li>Hole count and largest hole diameter</li>
    <li>Patch vs board/panel replacement scope</li>
    <li>Waterproofing plan (sealant, flashing, weather barrier restoration)</li>
    <li>Finish plan (prime + paint blend or stain match)</li>
    <li>Access plan (ladder vs lift and how it impacts price)</li>
    <li>Prevention plan (netting/barriers) to reduce repeat damage</li>
  </ul>

  <hr />

  <h2>Woodpecker Damage Insurance Coverage (Common Reality)</h2>

  <p>
    Home insurance may cover woodpecker damage depending on the policy and exclusions. Coverage is more likely when
    damage is sudden and not tied to neglect. Document the damage immediately and ask whether animal-related exterior
    damage is covered.
  </p>
</section>
"""
HOWTO_INNER = """
<section>
  <h2>Step 1: Inspect the Damage (Repair vs Replace)</h2>

  <p>Before filling holes, determine how deep the damage goes.</p>

  <h3>You can usually repair if:</h3>
  <ul>
    <li>The wood is solid when probed</li>
    <li>The hole is shallow or clean-edged</li>
    <li>No moisture staining or softness is present</li>
  </ul>

  <h3>You should replace siding or trim if:</h3>
  <ul>
    <li>The wood feels soft or spongy</li>
    <li>Holes penetrate deeply or connect internally</li>
    <li>There is visible rot, swelling, or cracking</li>
    <li>Damage has occurred repeatedly in the same board</li>
  </ul>

  <p>
    If you can push a screwdriver into the wood easily, replacement is safer than patching.
  </p>

  <hr />

  <h2>Step 2: Choose the Right Repair Method</h2>

  <h3>Method 1: Patch Small Holes and Divots</h3>
  <p><strong>Best for:</strong> Shallow pecks, cosmetic damage, minor holes</p>

  <ol>
    <li>Remove loose fibers and debris</li>
    <li>Let the area dry completely</li>
    <li>Fill with two-part epoxy wood filler</li>
    <li>Slightly overfill and sand smooth after curing</li>
    <li>Prime bare wood</li>
    <li>Paint or stain to match</li>
  </ol>

  <p>
    Epoxy fillers outperform standard caulk or lightweight putties in exterior conditions.
  </p>

  <h3>Method 2: Plug Clean Round Woodpecker Holes</h3>
  <p><strong>Best for:</strong> Cedar siding and trim with round holes</p>

  <ol>
    <li>Drill the hole clean using a hole saw</li>
    <li>Cut a matching wood plug when possible</li>
    <li>Bond the plug with exterior epoxy or adhesive</li>
    <li>Sand flush once cured</li>
    <li>Prime and paint or stain</li>
  </ol>

  <p>
    This method restores strength and blends better than surface fillers alone.
  </p>

  <h3>Method 3: Replace Damaged Boards or Sections</h3>
  <p><strong>Best for:</strong> Large holes, repeated attacks, moisture damage</p>

  <ol>
    <li>Remove the damaged board carefully</li>
    <li>Inspect underlying sheathing or framing</li>
    <li>Repair moisture issues if present</li>
    <li>Install a matching replacement board</li>
    <li>Seal, prime, and finish all exposed surfaces</li>
  </ol>

  <hr />

  <h2>Step 3: Seal and Finish Correctly</h2>

  <ul>
    <li>Prime all exposed wood before painting</li>
    <li>Pay special attention to end grain</li>
    <li>Use paintable exterior caulk only at seams</li>
    <li>Match existing paint or stain to protect repairs</li>
  </ul>

  <hr />

  <h2>How to Prevent Woodpeckers From Returning</h2>

  <p>
    Repairing holes alone often leads to repeat damage, sometimes within days.
  </p>

  <h3>Install Bird Netting</h3>

  <ul>
    <li>Use 3/4-inch mesh netting</li>
    <li>Maintain at least 3 inches of space from siding</li>
    <li>Cover the entire affected wall section</li>
  </ul>

  <p>
    If netting is installed too narrowly, woodpeckers will simply move to the edge and continue pecking.
  </p>

  <h3>Use Physical Barriers Where Needed</h3>

  <ul>
    <li>Hardware cloth</li>
    <li>Sheet metal or PVC panels</li>
    <li>Protective flashing on corners and fascia</li>
  </ul>

  <h3>Visual Deterrents</h3>

  <p>
    Reflective tape or streamers may help temporarily but are best used as a supplement, not a primary solution.
  </p>
"""


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

def generate_state_to_col_map():
  total_state_cols = {}
  for _, st, col in CITIES:
    if st in total_state_cols:
      total_state_cols[st].append(col)
    else:
      total_state_cols[st] = [col]
  
  state_col_map = {}
  for st, cols in total_state_cols.items():
    state_col_map[st] = sum(cols) / len(cols)
  
  return state_col_map

STATE_TO_COL_MAP = generate_state_to_col_map()



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

def filename_to_alt(filename: str) -> str:
  if not filename:
    return ""
  alt = filename.lower()
  alt = re.sub(r"\.[a-z0-9]+$", "", alt)
  alt = re.sub(r"[-_]+", " ", alt)
  alt = re.sub(r"\b\d+\b", "", alt)
  alt = re.sub(r"\s+", " ", alt).strip()
  return alt.capitalize()

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

Mode = str  # "regular" | "cost" | "state" | "subdomain" | "regular_city_only"

SITE_ORIGIN = (os.environ.get("SITE_ORIGIN") or "").rstrip("/")
SUBDOMAIN_BASE = (os.environ.get("SUBDOMAIN_BASE") or "").strip().lower().strip(".")


# ============================================================
# FEATURE FLAGS PER MODE
# ============================================================

MODE_FEATURES: dict[str, dict[str, bool]] = {
  "regular": {"cost": True, "howto": True, "contact": True},
  "cost": {"cost": True, "howto": False, "contact": True},
  "state": {"cost": False, "howto": False, "contact": True},
  "subdomain": {"cost": False, "howto": False, "contact": True},
  "regular_city_only": {"cost": False, "howto": False, "contact": True},
}

def feature(mode: Mode, key: str) -> bool:
  return MODE_FEATURES.get(mode, MODE_FEATURES["regular"]).get(key, False)


# ============================================================
# COPY VARIANTS (1..5) selected by mode (override with env)
# (kept for compatibility; not used in this file)
# ============================================================

COPY_VARIANT_BY_MODE: dict[str, int] = {
  "regular": 1,
  "cost": 2,
  "state": 3,
  "subdomain": 4,
  "regular_city_only": 5,
}

def resolve_copy_idx(mode: str) -> int:
  """
  Returns idx 0..4 for picking the copy variant.
  Env override: COPY_VARIANT=1..5
  Otherwise uses COPY_VARIANT_BY_MODE[mode].
  """
  raw = (os.environ.get("COPY_VARIANT") or "").strip()
  if raw.isdigit():
    v = int(raw)
  else:
    v = COPY_VARIANT_BY_MODE.get(mode, 1)

  v = max(1, min(5, v))  # clamp 1..5
  return v - 1           # idx 0..4


def rel_city_path_regular(city: str, st: str) -> str:
  return f"/{slugify(city)}-{slugify(st)}/"

def rel_city_path_state(city: str, st: str) -> str:
  return f"/{slugify(st)}/{slugify(city)}/"

def abs_city_origin_subdomain(city: str, st: str) -> str:
  slug = f"{slugify(city)}-{slugify(st)}"
  base = SUBDOMAIN_BASE or (
    SITE_ORIGIN.replace("https://", "").replace("http://", "").split("/")[0]
    if SITE_ORIGIN else ""
  )
  if not base:
    return f"/{slug}/"
  return f"https://{slug}.{base}/"

def href_home(mode: Mode) -> str:
  if mode == "subdomain":
    return SITE_ORIGIN + "/" if SITE_ORIGIN else "/"
  return "/"

def href_city(mode: Mode, city: str, st: str) -> str:
  if mode == "state":
    return rel_city_path_state(city, st)
  if mode == "subdomain":
    return abs_city_origin_subdomain(city, st)
  return rel_city_path_regular(city, st)

def href_state(mode: Mode, st: str) -> str:
  return f"/{slugify(st)}/"

def href_cost_index(mode: Mode) -> str:
  return (SITE_ORIGIN + "/cost/") if (mode == "subdomain" and SITE_ORIGIN) else "/cost/"

def href_howto_index(mode: Mode) -> str:
  return (SITE_ORIGIN + "/how-to/") if (mode == "subdomain" and SITE_ORIGIN) else "/how-to/"

def href_contact(mode: Mode) -> str:
  return (SITE_ORIGIN + "/contact/") if (mode == "subdomain" and SITE_ORIGIN) else "/contact/"

def canonical_for(mode: Mode, path_or_abs: str) -> str:
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
html,body{max-width:100%;overflow-x:clip;}
body{margin:0;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;color:var(--ink);background:var(--bg);line-height:1.6}
a{color:inherit}
.topbar{position:sticky;top:0;z-index:50;background:rgba(250,250,249,.92);backdrop-filter:saturate(140%) blur(10px);border-bottom:1px solid var(--line)}
.topbar-inner{max-width:var(--max);margin:0 auto;padding:12px 18px;display:flex;align-items:center;justify-content:space-between;gap:14px}
.brand{font-weight:900;letter-spacing:-.02em;text-decoration:none}
.nav{display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-end}
.nav a:not(.btn){text-decoration:none;font-size:13px;color:var(--muted);padding:7px 10px;border-radius:12px;border:1px solid transparent}
.nav a:not(.btn):hover{background:var(--soft);border-color:var(--line)}
.nav a:not(.btn)[aria-current="page"]{color:var(--ink);background:var(--soft);border:1px solid var(--line)}
.btn{display:inline-block;padding:9px 12px;background:var(--cta);color:#fff;border-radius:12px;text-decoration:none;font-weight:900;font-size:13px;border:1px solid rgba(0,0,0,.04);box-shadow:0 8px 18px rgba(22,163,74,.18)}
.btn:hover{background:var(--cta2)}
header{border-bottom:1px solid var(--line);background:radial-gradient(1200px 380px at 10% -20%, rgba(22,163,74,.08), transparent 55%),radial-gradient(900px 320px at 95% -25%, rgba(17,24,39,.06), transparent 50%),#fbfbfa}
.hero{max-width:var(--max);margin:0 auto;padding:34px 18px 24px;display:grid;gap:10px}
.hero h1{margin:0;font-size:30px;letter-spacing:-.03em;line-height:1.18}
.sub{margin:0;color:var(--muted);max-width:78ch;font-size:14px}
main{max-width:var(--max);margin:0 auto;padding:22px 18px 46px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px;box-shadow:var(--shadow);max-width:100%}
.img{margin-top:14px;margin-bottom:16px;border-radius:14px;overflow:hidden;border:1px solid var(--line);background:var(--soft);box-shadow:var(--shadow2);width:100%}
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

/* ---------- TABLES (base look) ---------- */
table{width:100%;border-collapse:separate;border-spacing:0;margin:14px 0;background:#fff;border:1px solid var(--line);border-radius:14px}
thead th{background:var(--soft);color:var(--ink);font-size:13px;text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:10px 12px;vertical-align:top;border-bottom:1px solid var(--line);font-size:14px;color:var(--ink)}
tbody tr:last-child td{border-bottom:none}

/* wrapper that scrolls (only works if you wrap tables in .table-scroll) */
.table-scroll{max-width:100%}

@media (max-width:640px){
  .topbar-inner{flex-direction:column;align-items:stretch;gap:10px}
  .nav{justify-content:center}
  .nav .btn{width:100%;text-align:center}

  /* only the wrapper scrolls, NOT the whole page */
  .table-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
  .table-scroll table{min-width:720px}
}

/* -----------------------
   CONTACT FORM (match first block)
----------------------- */
.form-grid{
  margin-top:14px;
  display:grid;
  gap:14px;
  grid-template-columns:1fr 320px;
  align-items:start;
}
@media (max-width: 900px){
  .form-grid{grid-template-columns:1fr}
}

.embed-card{
  border:1px solid var(--line);
  border-radius:14px;
  padding:18px;
  background:var(--soft);
}

.nx-center{
  display:flex;
  justify-content:center; /* keep the small iframe centered */
}

/* Keep Networx at the required embedded size */
#nx_form{
  width:242px;
  height:375px;
}

/* Force iframe to fill the fixed-size container */
#networx_form_container iframe{
  width:100% !important;
  height:100% !important;
  border:0 !important;
}

/* -----------------------
   WHY BOX (match first block)
----------------------- */
.why-box{
  background:#fff;
  border:1px solid var(--line);
  border-radius:14px;
  padding:14px;
  box-shadow:0 10px 24px rgba(17,24,39,0.05);
}
.why-box h3{
  margin:0 0 10px;
  font-size:15px;
}
.why-list{
  list-style:none;
  padding:0;
  margin:0;
  display:grid;
  gap:10px;
}
.why-item{
  display:flex;
  gap:10px;
  align-items:flex-start;
  color:var(--muted);
  font-size:13px;
}
.tick{
  width:18px;
  height:18px;
  border-radius:999px;
  background:rgba(22,163,74,0.12);
  border:1px solid rgba(22,163,74,0.22);
  display:inline-flex;
  align-items:center;
  justify-content:center;
}
.tick:before{
  content:"✓";
  font-weight:900;
  font-size:12px;
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
  img_src = f"/{CONFIG.image_filename}"
  img_alt = filename_to_alt(CONFIG.image_filename)
  img_html = ""
  if show_image:
    img_html = f"""
    <div class="img">
      <img src="{img_src}" alt="{img_alt}" loading="lazy" />
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


def make_section(*, headings: tuple[str, ...], paras: tuple[str, ...]) -> str:
  parts: list[str] = []
  for h2, p in zip(headings, paras):
    parts.append(f"<h2>{esc(h2)}</h2>")
    parts.append(f"<p>{esc(p)}</p>")
  return "\n".join(parts)


def location_cost_section(city: str = "", st: str = "", col: float = 1) -> str:
  rep = (
    f" in {city}, {st}"
    if city and st
    else f" in {st}"
    if st
    else ""
  )
  cost_lo = f"<strong>${int(CONFIG.cost_low * col)}</strong>"
  cost_hi = f"<strong>${int(CONFIG.cost_high * col)}</strong>"

  h2 = CONFIG.location_cost_h2.replace("{loc}", rep)
  p = (
    CONFIG.location_cost_p
    .replace("{loc}", rep)
    .replace("{cost_lo}", cost_lo)
    .replace("{cost_hi}", cost_hi)
  )
  return f"<h2>{esc(h2)}</h2>\n<p>{p}</p>"

def about_section(city: str = "", st: str = "") -> str:
  rep = (
    f" in {city}, {st}"
    if city and st
    else f" in {st}"
    if st
    else " nationwide"
  )

  p = (
    CONFIG.about_blurb
    .replace("{loc}", rep)
  )

  return f"<p>{p}</p>"
# ============================================================
# PAGE BODY SNIPPETS (simple defaults)
# ============================================================


# ============================================================
# PAGE CONTENT FACTORIES
# ============================================================

def homepage_html(*, mode: Mode) -> str:
  links = "\n".join(
    f'<li><a href="{esc(href_city(mode, c, s))}">{esc(c)}, {esc(s)}</a></li>'
    for c, s, _ in CITIES
  )

  inner = (
    about_section()
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p)
    + location_cost_section()
    + """
<hr />
<h2>Our Service Area</h2>
<p class="muted">We provide services nationwide, including in the following cities:</p>
<ul class="city-grid">
"""
    + links
    + """
</ul>
"""
  )

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  return make_page(
    mode=mode,
    h1=CONFIG.h1_title,
    canonical="/",
    nav_key="home",
    sub=CONFIG.h1_sub,
    inner=inner,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def contact_page_html(mode: Mode) -> str:
  h1 = "Get Your Free Estimate"
  sub = "All you have to do is fill out the form below."

  why_title = "Why Choose Us?"
  why_bullets = (
    "Free, no-obligation estimates",
    "Trusted, experienced professionals",
    "Nationwide service coverage",
    "Fast response times",
  )

  why_items = "\n".join(
    f'<li class="why-item"><span class="tick" aria-hidden="true"></span><span>{esc(t)}</span></li>'
    for t in why_bullets
  )

  networx_embed = """
<div id="networx_form_container" style="margin:0px;padding:0px;">
    <div id = "nx_form" style = "width: 242px; height: 375px;">
        <script type="text/javascript" src = "https://api.networx.com/iframe.php?aff_id=73601bc3bd5a961a61a973e92e29f169&aff_to_form_id=8008"></script>
    </div>
</div>
""".strip()

  inner = f"""
<div class="form-grid">
  <div class="embed-card">
    <div class="nx-center">
      {networx_embed}
    </div>
  </div>

  <aside class="why-box" aria-label="Why choose us">
    <h3>{esc(why_title)}</h3>
    <ul class="why-list">
      {why_items}
    </ul>
  </aside>
</div>
""".strip()

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  return make_page(
    mode=mode,
    h1=h1,
    canonical="/contact/",
    nav_key="contact",
    sub=sub,
    inner=inner,
    show_image=False,
    show_footer_cta=False,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def city_page_html(*, mode: Mode, city: str, st: str, col: float, canonical: str) -> str:
  inner = (
    about_section(city=city, st=st)
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p)
    + location_cost_section(city, st, col)
  )

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  return make_page(
    mode=mode,
    h1=clamp_title(f"{CONFIG.h1_short} in {city}, {st}", 70),
    canonical=canonical,
    nav_key="home",
    sub=CONFIG.h1_sub,
    inner=inner,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def cost_page_html(*, mode: Mode, include_city_index: bool) -> str:
  inner = COST_INNER

  if include_city_index:
    links = "\n".join(
      f'<li><a href="{esc(cost_city_href(mode, c, s))}">{esc(c)}, {esc(s)}</a></li>'
      for c, s, _ in CITIES
    )
    inner += (
      """
<hr />
<h2>Our Service Area</h2>
<p class="muted">See local price ranges by city:</p>
<ul class="city-grid">
"""
      + links
      + """
</ul>
"""
    )

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  return make_page(
    mode=mode,
    h1=CONFIG.cost_title,
    canonical="/cost/",
    nav_key="cost",
    sub=CONFIG.cost_sub,
    inner=inner,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def cost_city_href(mode: Mode, city: str, st: str) -> str:
  if mode == "subdomain" and SITE_ORIGIN:
    return SITE_ORIGIN + f"/cost/{slugify(city)}-{slugify(st)}/"
  return f"/cost/{slugify(city)}-{slugify(st)}/"


def cost_city_page_html(*, mode: Mode, city: str, st: str, col: float) -> str:
  canonical = f"/cost/{slugify(city)}-{slugify(st)}/"
  h1 = clamp_title(f"{CONFIG.cost_title} in {city}, {st}", 70)

  inner = location_cost_section(city, st, col) + COST_INNER

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  return make_page(
    mode=mode,
    h1=h1,
    canonical=canonical,
    nav_key="cost",
    sub=CONFIG.cost_sub,
    inner=inner,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def howto_page_html(*, mode: Mode) -> str:
  inner = HOWTO_INNER
  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  return make_page(
    mode=mode,
    h1=CONFIG.howto_title,
    canonical="/how-to/",
    nav_key="howto",
    sub=CONFIG.howto_sub,
    inner=inner,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def state_homepage_html(*, mode: Mode) -> str:
  by_state = cities_by_state(CITIES)
  states = sorted(by_state.keys())

  links = "\n".join(
    f'<li><a href="{esc(href_state(mode, st))}">{esc(state_full(st))}</a></li>'
    for st in states
  )

  inner = (
    about_section()
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p)
    + location_cost_section()
    + """
<hr />
<h2>Our Service Area</h2>
<p class="muted">We provide services nationwide, including in the following states:</p>
<ul class="city-grid">
"""
    + links
    + """
</ul>
"""
  )

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  return make_page(
    mode=mode,
    h1=CONFIG.h1_title,
    canonical="/",
    nav_key="home",
    sub=CONFIG.h1_sub,
    inner=inner,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def state_page_html(*, mode: Mode, st: str, cities: list[CityWithCol]) -> str:
  links = "\n".join(
    f'<li><a href="{esc(href_city(mode, c, st))}">{esc(c)}, {esc(st)}</a></li>'
    for c, st, _ in cities
  )

  inner = (
    about_section(st=state_full(st))
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p)
    + location_cost_section(st=state_full(st), col=STATE_TO_COL_MAP[st])
    + f"""
<h2>Cities we serve in {esc(state_full(st))}</h2>
<p class="muted">Choose your city to see local details and typical pricing ranges.</p>
<ul class="city-grid">
{links}
</ul>
""".strip()
  )

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  return make_page(
    mode=mode,
    h1=clamp_title(f"{CONFIG.h1_short} in {state_full(st)}", 70),
    canonical=f"/{slugify(st)}/",
    nav_key="home",
    sub=CONFIG.h1_sub,
    inner=inner,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
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
  Writes shared core pages for the given mode.
  Returns list of sitemap URLs (relative or absolute depending on mode/canonicals).
  """
  urls: list[str] = ["/"]

  if feature(mode, "cost"):
    write_text(out / "cost" / "index.html", cost_page_html(mode=mode, include_city_index=(mode == "cost")))
    urls.append("/cost/")

  if feature(mode, "howto"):
    write_text(out / "how-to" / "index.html", howto_page_html(mode=mode))
    urls.append("/how-to/")

  if feature(mode, "contact"):
    write_text(out / "contact" / "index.html", contact_page_html(mode=mode))
    urls.append("/contact/")

  return urls


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
    - Home + Contact stay on the root domain (and are rendered in /public).
    - City pages are meant to be served via host-based rewrites (Vercel/Cloudflare).
    - No Cost / How-To pages in this mode.
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
    write_text(
      out / slug / "index.html",
      city_page_html(mode=mode, city=city, st=st, col=col, canonical=city_origin)
    )
    urls.append(city_origin)

  write_text(out / "robots.txt", robots_txt())
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ subdomain: Generated {len(urls)} pages into: {out.resolve()}")


def build_regular_city_only(*, out: Path) -> None:
  """
  regular_city_only:
    - Generates / (homepage) + city pages /{city-st}/ + /contact/
    - Does NOT generate /cost/ or /how-to/
    - Navbar/Footer hide Cost + How-To
  """
  mode: Mode = "regular_city_only"
  urls: list[str] = ["/", "/contact/"]

  write_text(out / "index.html", homepage_html(mode=mode))
  write_text(out / "contact" / "index.html", contact_page_html(mode=mode))

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
          location_cost_section(city, st, col)
          + "<hr />\n"
          + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p)
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

VALID_MODES: set[str] = {"regular", "cost", "state", "subdomain", "regular_city_only"}

SITE_MODE: Mode = sys.argv[1] if len(sys.argv) > 1 else "regular"
COPY_IDX: int = resolve_copy_idx(SITE_MODE)  # reserved; not used

if SITE_MODE not in VALID_MODES:
  raise ValueError(
    f"Invalid SITE_MODE {SITE_MODE!r}. "
    f"Choose one of: {', '.join(sorted(VALID_MODES))}"
  )

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








