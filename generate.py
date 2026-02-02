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
  image_filename: str = "picture.png"  # sits next to generate.py

  # Identity
  base_name: str = "Woodpecker Damage Repair"
  brand_name: str = "Woodpecker Damage Repair Company"

  # CTA
  cta_text: str = "Get Free Estimate"
  cta_href: str = "/contact/"

  # Pricing base
  cost_low: int = 300
  cost_high: int = 800

  # Core titles/subs
  h1_title: str = "Woodpecker Damage Repair/Woodpecker Hole Repair/Siding Repair Services"
  h1_short: str = "Woodpecker Damage Repair Services"
  h1_sub: str = "Weather-tight siding and trim repairs that seal holes, match finishes, and reduce repeat damage."

  cost_title: str = "Woodpecker Damage Repair Cost"
  cost_sub: str = "Typical pricing ranges, scope examples, and what drives the total for siding and trim repairs."

  howto_title: str = "How Woodpecker Damage Repair Works"
  howto_sub: str = "A practical, homeowner-friendly guide to how repairs are typically done and when DIY breaks down."

  about_blurb: tuple[str, ...] = (
    "We focus on woodpecker damage repair for homeowners dealing with holes in siding, trim, and exterior wood. "
    "Our work seals woodpecker holes, restores affected areas, and helps prevent moisture intrusion and repeat damage. "
    "Get a fast quote and schedule service with a trusted local professional.",

    "We provide woodpecker damage repair for homes with holes in siding, trim, and exterior wood surfaces. "
    "Our repairs seal damaged areas, protect against moisture, and reduce the chance of repeat woodpecker activity. "
    "Request a quick quote and connect with a local repair professional.",

    "We offer professional woodpecker damage repair for homeowners facing holes in siding and exterior wood. "
    "Our repairs restore damaged sections, seal woodpecker holes, and help protect your home from ongoing damage. "
    "Get a fast estimate and book service with a reliable local pro.",
  
    "We specialize in repairing woodpecker damage on homes with holes in siding, trim, and exterior wood. "
    "Our services seal woodpecker holes, restore damaged areas, and help protect your house from moisture and repeat issues. "
    "Request a fast quote and work with a local professional you can trust.",
  
    "We help homeowners repair woodpecker damage by fixing holes in siding, trim, and exterior wood. "
    "Our repairs seal damaged areas, restore the exterior, and reduce the risk of moisture and repeat woodpecker damage. "
    "Get a quick quote and schedule service with a local professional."
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

  main_p: tuple[tuple[str, ...], ...] = (
  (
    "Woodpeckers commonly damage homes by boring holes into siding, trim, fascia, and corner boards, which can expose exterior surfaces to moisture and pests. Even minor holes can weaken exterior wood and cause paint or material breakdown when water repeatedly enters.",
    "Woodpeckers typically peck houses to look for insects, form a nesting cavity, or drum against the surface to mark territory. Homes with exterior wood, shaded conditions, or existing damage are more likely to experience repeat activity if the cause isn’t addressed.",
    "Woodpecker holes usually show up as round openings, tight clusters of small holes, or deeper cavities created by repeated pecking. The size and grouping often reveal whether the bird was briefly probing or engaging in ongoing nesting or feeding.",
    "When woodpecker damage is left unrepaired, moisture can pass through the holes and slowly deteriorate nearby materials. Over time, this can lead to rot, peeling paint, and broader exterior damage that requires more extensive repairs.",
    "Woodpecker activity doesn’t always indicate termites, but it can point to insects living in or near the wood. Since birds may be targeting ants or larvae, evaluating the wood before sealing holes helps avoid trapping a hidden issue.",
    "Whether woodpecker damage is covered depends on how a homeowners insurance policy handles animal-related exterior damage. Some policies may cover sudden events, while others treat gradual damage as maintenance.",
    "Preventing woodpeckers from returning after repairs usually means removing what attracted them and limiting future access. Treating insect problems, reinforcing repaired sections, and protecting exposed exterior wood can reduce repeat damage.",
  ),
  (
    "Woodpeckers often damage houses by drilling into siding, trim, fascia, and corner boards, creating openings that allow moisture and pests inside. Even small holes can compromise exterior wood and lead to deterioration if water continues to enter.",
    "Most woodpeckers peck homes while searching for insects, carving out nesting spaces, or drumming to claim territory. Properties with exterior wood, shade, or prior damage tend to attract repeated activity when the root cause isn’t resolved.",
    "Damage from woodpeckers commonly appears as round holes, groups of small punctures, or deeper cavities formed over time. The pattern of the holes can indicate whether the bird was briefly investigating or repeatedly returning to the same area.",
    "Ignoring woodpecker damage allows moisture to enter through the openings and gradually weaken surrounding materials. Over time, this exposure can cause rot, coating failure, and expanded damage that requires larger repairs.",
    "Seeing woodpecker damage doesn’t necessarily mean termites are present, but it may signal insects in the wood. Because birds often hunt ants or larvae, checking the wood’s condition before sealing holes is important.",
    "Insurance coverage for woodpecker damage varies based on how a homeowners insurance policy defines animal-related damage. Sudden damage may be covered, while long-term issues are often considered routine maintenance.",
    "Keeping woodpeckers away after repairs typically involves addressing what drew them to the house in the first place. Managing insects, strengthening repaired areas, and shielding exposed wood help lower the chance of repeat damage.",
  ),
  (
    "Woodpeckers damage homes by pecking holes into siding, trim, fascia, and corner boards, which can leave the exterior vulnerable to moisture and pests. Over time, even small openings can weaken exterior wood and accelerate surface deterioration.",
    "Houses are usually pecked by woodpeckers when birds are searching for insects, building nesting cavities, or drumming to signal territory. Structures with exterior wood or shaded, damaged areas are more likely to be targeted repeatedly.",
    "Woodpecker holes often appear as smooth, round openings, tight groupings of small holes, or deeper cavities formed from repeated pecking. These patterns help distinguish brief activity from ongoing nesting or feeding behavior.",
    "Leaving woodpecker damage unrepaired allows water to pass through the holes and slowly damage surrounding materials. Continued exposure can result in rot, peeling finishes, and a much larger repair area over time.",
    "Woodpecker activity alone doesn’t confirm termites, but it can indicate insects present in the wood. Since birds may be feeding on ants or larvae, inspecting the wood before sealing repairs helps prevent sealing in a problem.",
    "Whether homeowners insurance covers woodpecker damage depends on policy terms and how the damage is classified. Some policies cover sudden animal damage, while gradual issues may fall under maintenance exclusions.",
    "Reducing repeat woodpecker damage after repairs usually requires removing attractants and limiting access. Addressing insect activity, reinforcing repaired sections, and protecting exterior wood can help discourage return visits.",
  ),
  (
    "Woodpecker damage typically involves holes drilled into siding, trim, fascia, and corner boards, creating paths for moisture and pests to enter the home. Even minor holes can weaken exterior wood and contribute to long-term deterioration.",
    "Woodpeckers peck houses most often while hunting insects, forming nesting spaces, or drumming to establish territory. Homes with exterior wood or shaded, damaged areas are more appealing when the underlying cause isn’t corrected.",
    "Holes caused by woodpeckers usually appear as clean round openings, clusters of small punctures, or deeper cavities formed by repeated activity. The size and placement often reveal whether the damage was brief or ongoing.",
    "If woodpecker damage isn’t repaired, water can seep through the holes and gradually degrade nearby materials. Over time, this can lead to rot, finish failure, and more extensive exterior repairs.",
    "Woodpecker damage doesn’t always point to termites, but it may indicate insects living in the wood. Because birds often target ants or larvae, assessing the condition of the wood before sealing holes is important.",
    "Homeowners insurance coverage for woodpecker damage depends on how animal-related exterior damage is defined in the policy. Some coverage applies to sudden damage, while gradual issues may not be included.",
    "Preventing woodpeckers from returning after repairs usually means addressing what attracted them initially. Managing insects, reinforcing repaired areas, and protecting exposed wood help reduce future damage.",
  ),
  (
    "Woodpeckers damage houses by creating holes in siding, trim, fascia, and corner boards, leaving the exterior open to moisture and pests. Even small holes can weaken exterior wood and cause progressive surface damage when water intrusion continues.",
    "Woodpeckers usually peck homes while searching for insects, carving nesting cavities, or drumming to mark territory. Homes with exterior wood, shade, or prior damage are more likely to experience repeat pecking if the cause isn’t addressed.",
    "Woodpecker holes commonly appear as round openings, clusters of small holes, or deeper cavities created over time. The pattern and depth help indicate whether the activity was brief probing or repeated nesting behavior.",
    "When woodpecker damage is ignored, moisture can enter through the openings and slowly damage surrounding materials. Continued exposure often leads to rot, paint breakdown, and larger repair needs.",
    "Woodpecker activity does not automatically mean termites are present, but it can suggest insects in the wood. Since birds often target ants or larvae, evaluating the wood before sealing holes helps avoid sealing in pests.",
    "Insurance coverage for woodpecker damage depends on the terms of a homeowners insurance policy and how the damage is classified. Sudden damage may be covered, while long-term deterioration is often excluded.",
    "Keeping woodpeckers away after repairs usually involves removing attractants and strengthening repaired areas. Addressing insect problems and protecting exposed exterior wood can help prevent repeat damage.",
  ),
)


  howto_h2: tuple[str, ...] = (
    "How Woodpecker Damage Is Typically Identified on a House",
    "How Professionals Determine Whether Damage Is Surface-Level or Structural",
    "How Different Repair Methods Are Used for Woodpecker Holes",
    "How Woodpecker Damage Is Sealed to Prevent Moisture Intrusion",
    "How Finish Matching Affects the Durability and Appearance of Repairs",
    "When Woodpecker Damage Repair Is Not a DIY-Friendly Project",
  )

  howto_p: tuple[tuple[str, ...], ...] = (
  (
    "Woodpecker damage is typically identified by spotting round holes, clusters of small punctures, or repeated cavities in siding and trim. These marks often appear on exterior wood surfaces and may vary in depth depending on how long the bird has been active.",
    "Most woodpecker damage is identified by visible holes or peck marks in siding, fascia, or trim boards. The size and grouping of these holes often indicate whether the activity was brief or ongoing.",
    "Identifying woodpecker damage usually starts with noticing clean, round holes or patterned clusters in exterior materials. These signs are most common on wood surfaces that sound hollow or retain moisture.",
    "Woodpecker damage is commonly recognized by small to large holes in siding or trim, often appearing in repeated patterns. The visual layout of the holes helps determine how aggressively the area was targeted."
  ),
  (
    "Professionals determine whether damage is surface-level or structural by checking the firmness of the surrounding wood and looking for moisture intrusion. Soft areas or discoloration can indicate deeper issues beyond the visible hole.",
    "The difference between surface damage and structural damage is assessed by probing the material around the hole for softness or hidden rot. Damage that extends beyond the exterior layer usually requires more than a simple patch.",
    "To determine damage severity, professionals examine whether the wood around the hole is solid or deteriorated. Moisture staining, softness, or movement often signals that the damage goes deeper than the surface.",
    "Structural involvement is identified by inspecting how far the damage extends into the material and whether moisture has compromised the surrounding area. Surface-only damage typically remains firm and dry."
  ),
  (
    "Different repair methods are used based on hole size, hole density, and the condition of the surrounding material. Small, isolated holes may be stabilized differently than areas with repeated or widespread damage.",
    "Repair methods vary depending on whether damage is limited to a few small holes or spread across multiple boards. The condition of the surrounding wood largely determines whether patching or replacement is appropriate.",
    "Professionals choose repair methods by evaluating how many holes are present and whether the material can support a durable repair. Stable wood allows for lighter repairs, while weakened areas often need replacement.",
    "The repair approach is selected based on damage pattern and material condition rather than hole size alone. Repeated damage in one area often requires a more durable solution than isolated marks."
  ),
  (
    "Woodpecker damage is sealed by closing the opening and stabilizing the surrounding area to keep moisture from entering the wall system. Proper sealing prevents water from reaching the wood behind the exterior surface.",
    "Preventing moisture intrusion involves sealing both the hole itself and the edges around it so water cannot wick behind the repair. This step is critical for long-term durability.",
    "Sealing woodpecker damage focuses on blocking water entry at the surface and around the repair boundary. Without proper sealing, moisture can undermine even a visually solid repair.",
    "Moisture prevention is achieved by sealing the repaired area completely so rain and condensation cannot penetrate behind the exterior finish. This protects the structure from rot and deterioration."
  ),
  (
    "Finish matching affects repair durability by helping protect the repaired area from weather exposure and UV breakdown. A consistent finish also prevents the repair from standing out visually.",
    "Matching the existing finish helps repairs last longer by ensuring coatings bond evenly across old and new material. Poor finish blending can lead to premature peeling or moisture penetration.",
    "Finish matching plays a role in durability by maintaining a continuous protective layer over the repair. Differences in texture or coating can shorten the lifespan of the repair.",
    "A properly matched finish supports both appearance and performance by sealing the repair uniformly. Mismatched finishes often fail faster due to uneven exposure."
  ),
  (
    "Woodpecker damage repair is not DIY-friendly when damage is widespread, access requires ladder work, or finish blending is critical. These situations increase the risk of repeat failure or personal injury.",
    "DIY repair becomes impractical when holes are spread across multiple areas or when the surrounding wood is deteriorated. In these cases, repairs often fail without proper stabilization and sealing.",
    "Projects involving height, multiple repair zones, or weakened materials are generally not suitable for DIY repair. These conditions make long-term durability difficult to achieve without professional methods.",
    "Woodpecker repairs are poor DIY candidates when safety risks, material instability, or appearance expectations are high. Improper repairs in these situations often need to be redone."
  ),
)


  cost_h2: tuple[str, ...] = (
    "How Much Does Woodpecker Damage Repair Cost?",
    "What Is Included in Woodpecker Damage Repair Cost?",
    "How Woodpecker Damage Repair Cost Varies by Number of Holes and Areas",
    "How Patching vs Board Replacement Affects Woodpecker Damage Repair Cost",
    "What Factors Affect Woodpecker Damage Repair Cost?",
    "Is Professional Woodpecker Damage Repair Worth the Cost?",
  )
  cost_p: tuple[tuple[str, ...], ...] = (
  (
    "Woodpecker damage repair typically costs between a few hundred dollars for minor repairs and over a thousand dollars for widespread damage. Pricing depends on how many holes need repair, whether boards require replacement, and how much finish blending is needed.",
    "Most woodpecker damage repairs fall within a mid-range cost, with smaller jobs on the lower end and extensive repairs costing more. The final price is driven by damage extent, access difficulty, and material condition.",
    "The cost to repair woodpecker damage usually ranges based on repair size and complexity. Small patch jobs cost less, while multiple damaged areas or replacement work increase total pricing.",
    "Homeowners can expect woodpecker damage repair costs to vary widely depending on scope and materials. Simple repairs are more affordable, while repeated damage and finish matching raise costs."
  ),
  (
    "Woodpecker damage repair cost usually includes labor, material stabilization, sealing, and finish matching to restore the exterior. Pricing often reflects the time required to make repairs durable and visually consistent.",
    "Most repair estimates include preparing the damaged area, sealing holes, repairing or replacing affected material, and restoring the exterior finish. These steps are necessary to prevent moisture intrusion and repeat damage.",
    "Included costs typically cover patching or replacement, sealing against water, and blending the repaired area with the surrounding surface. The goal is a repair that holds up and doesn’t stand out.",
    "Woodpecker repair pricing generally accounts for access setup, repair materials, sealing work, and finish restoration. These components ensure the repair is weather-tight and long-lasting."
  ),
  (
    "Woodpecker damage repair cost increases as the number of holes and affected areas grows. Repairs concentrated in one spot usually cost less than scattered damage across multiple sections of the home.",
    "Pricing varies by scope because multiple holes or separate repair locations require more labor, setup, and finish blending. Widely spread damage often raises costs faster than hole size alone.",
    "The more holes and distinct areas that need repair, the higher the total cost tends to be. Scattered damage increases labor time and complexity compared to localized repairs.",
    "Repair costs scale with how many areas are affected and how accessible they are. Multiple repair zones often require additional setup and blending, which increases pricing."
  ),
  (
    "Patching typically costs less than board replacement because it requires fewer materials and less labor. Replacement raises costs due to removal, installation, and additional finish matching.",
    "The cost difference between patching and board replacement comes down to material condition and durability. Replacement is more expensive but often necessary when wood is weak or damage is repeated.",
    "Patching is generally cheaper for isolated holes, while board replacement increases costs when damage compromises structural integrity. Replacement work also adds labor and finishing time.",
    "Repair method significantly affects pricing, with patching on solid wood being more affordable than full board replacement. Replacement becomes more costly as finish blending and access requirements increase."
  ),
  (
    "Several factors affect woodpecker damage repair cost, including access height, material type, finish matching, and moisture damage. These variables influence both labor time and repair complexity.",
    "Cost is affected by rooflines, ladder access, exterior materials, and whether surrounding wood is deteriorated. Repairs that require additional stabilization or blending usually cost more.",
    "Factors that raise repair cost include difficult access, widespread damage, weakened wood, and the need for extensive finish restoration. Each adds time and labor to the project.",
    "Woodpecker repair pricing is influenced by damage severity, location on the house, material condition, and appearance requirements. More complex repairs naturally increase total cost."
  ),
)


  # Local cost snippet
  location_cost_h2: str = "How Much Does Woodpecker Damage Repair Cost in {City, State}?"
  location_cost_p: tuple[str, ...] = (
  (
    "In {City, State}, woodpecker damage repair typically costs between {cost_lo} and {cost_hi}, depending on how many holes need repair and how accessible the damaged areas are. "
    "Local labor rates and finish matching requirements can also influence the final price."
  ),
  (
    "Most woodpecker damage repair projects in {City, State} fall within the {cost_lo} to {cost_hi} range, with pricing based on damage extent and access difficulty. "
    "Costs may vary depending on exterior materials and local labor conditions."
  ),
  (
    "Homeowners in {City, State} usually pay between {cost_lo} and {cost_hi} for woodpecker damage repair, depending on scope and repair complexity. "
    "Factors like ladder access, material condition, and finish blending can affect pricing."
  ),
  (
    "The cost of woodpecker damage repair in {City, State} generally ranges from {cost_lo} to {cost_hi}, based on the number of damaged areas and how spread out they are. "
    "Local labor rates and exterior finish requirements play a role in the total cost."
  ),
  (
    "In {City, State}, most woodpecker damage repair jobs cost between {cost_lo} and {cost_hi}, depending on repair scope and access height. "
    "Pricing can also vary based on local labor pricing and the level of finish matching needed."
  ),
)

COST_INNER = """
<section>
  <p>Exterior Siding &amp; Trim Repair</p>

  <h1>Woodpecker Damage Repair Cost: Real Price Ranges (By Hole Size, Siding Type, and Severity)</h1>

  <p>
    Woodpecker damage repair costs depend on three variables: how deep the holes go, what material was hit,
    and whether water or rot has started. This page gives price ranges you can compare to quotes and explains
    what pushes costs up.
  </p>

  <hr />

  <h2>Woodpecker Damage Repair Cost Ranges (Most Common Repairs)</h2>

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

  <hr />

  <h2>What a Repair Quote Should Include</h2>

  <ul>
    <li>Hole count and largest hole diameter</li>
    <li>Patch vs board/panel replacement scope</li>
    <li>Waterproofing plan (sealant, flashing, weather barrier restoration)</li>
    <li>Finish plan (prime + paint blend or stain match)</li>
    <li>Access plan (ladder vs lift and how it impacts price)</li>
    <li>Prevention plan (netting/barriers) to reduce repeat damage</li>
  </ul>

  <hr />

  <h2>Insurance Coverage (Common Reality)</h2>

  <p>
    Home insurance may cover woodpecker damage depending on the policy and exclusions. Coverage is more likely when
    damage is sudden and not tied to neglect. Document the damage immediately and ask whether animal-related exterior
    damage is covered.
  </p>

  <hr />

  <h2>FAQ</h2>

  <h3>Why are some quotes much higher than the averages?</h3>
  <p>
    Higher quotes usually mean access challenges, board replacement instead of patching, finish blending, or damage
    into sheathing/insulation. Moisture and rot expand scope quickly.
  </p>

  <h3>Is it cheaper to patch everything instead of replacing boards?</h3>
  <p>
    Patching is cheaper upfront, but repeated pecking or soft wood often fails. When wood is compromised, replacement
    is typically the lower-cost long-term option.
  </p>

  <h3>Do woodpecker holes always mean insects?</h3>
  <p>
    No. Woodpeckers also drum for territory and target resonant surfaces. Treat insects only when clear evidence exists,
    and use physical exclusion to prevent repeat damage.
  </p>
</section>
"""

HOWTO_INNER = """
<section>

  <p>Exterior Siding &amp; Trim Repair</p>

  <h1>How to Repair Woodpecker Damage (Cedar Siding, Trim, and Roofs) — And Stop It for Good</h1>

  <p>
    Woodpecker damage can look minor at first, but even small holes can allow water into siding, trim,
    and roof structures, leading to swelling, rot, and long-term structural issues. Repairing the damage
    correctly — and preventing repeat attacks — is the key to protecting your home.
  </p>

  <p>
    This guide explains how to repair woodpecker damage properly, when patching is enough, when
    replacement is required, and what actually works to keep woodpeckers from coming back.
  </p>

  <hr />

  <h2>Do Woodpecker Holes Mean You Have Insects?</h2>

  <p>Not always.</p>

  <p>
    While woodpeckers sometimes peck to find insects, many attacks on houses happen for other reasons:
  </p>

  <ul>
    <li>Territorial drumming, especially in spring</li>
    <li>Attraction to resonant surfaces like cedar siding or trim</li>
    <li>Existing holes that encourage repeat pecking</li>
  </ul>

  <p>
    Eliminating insects alone does not reliably stop woodpecker damage. In many cases, the bird will
    continue pecking even when no infestation is present.
  </p>

  <p>
    <strong>Bottom line:</strong> Repair the damage promptly and use physical exclusion to prevent
    recurrence. Treat insects only if clear evidence exists.
  </p>

  <hr />

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

  <hr />

  <h2>When Insects Do Matter</h2>

  <p>Insect treatment is appropriate only when clear signs are present, such as:</p>

  <ul>
    <li>Carpenter ants</li>
    <li>Carpenter bees</li>
    <li>Termites</li>
  </ul>

  <p>
    If insects are confirmed, address them in addition to repairing damage and excluding birds.
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

# ============================================================
# COPY VARIANTS (1..5) selected by mode (override with env)
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

def make_section(*, headings: tuple[str, ...], paras: tuple[str, ...]) -> str:

  parts: list[str] = []
  for h2, p in zip(headings, paras):
    parts.append(f"<h2>{esc(h2)}</h2>")
    parts.append(f"<p>{esc(p)}</p>")
  return "\n".join(parts)


def location_cost_section(city: str, st: str, col: float, home_href: str) -> str:
  cost_lo = f"<strong>${int(CONFIG.cost_low * col)}</strong>"
  cost_hi = f"<strong>${int(CONFIG.cost_high * col)}</strong>"

  h2 = CONFIG.location_cost_h2.replace("{City, State}", f"{city}, {st}")
  p = (
    CONFIG.location_cost_p[COPY_IDX]
    .replace("{City, State}", f"{city}, {st}")
    .replace("{cost_lo}", cost_lo)
    .replace("{cost_hi}", cost_hi)
  )

  return f"<h2>{esc(h2)}</h2>\n<p>{p}</p>"


# ============================================================
# PAGE CONTENT FACTORIES
# ============================================================

def homepage_html(*, mode: Mode) -> str:
  links = "\n".join(
    f'<li><a href="{esc(href_city(mode, c, s))}">{esc(c)}, {esc(s)}</a></li>'
    for c, s, _ in CITIES
  )

  inner = (
    f"<p>{esc(CONFIG.about_blurb[COPY_IDX])}</p>\n"
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p[COPY_IDX])
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
    make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p[COPY_IDX])
    + location_cost_section(city, st, col, home_href=href_home(mode))
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
  inner = COST_INNER
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
        for p in CONFIG.cost_p[COPY_IDX]
      ),
    )
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
  inner = HOWTO_INNER
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
    f"<p>{esc(CONFIG.about_blurb[COPY_IDX])}</p>\n"
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p[COPY_IDX])
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
        make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p[COPY_IDX],)
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
          + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p[COPY_IDX])
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

VALID_MODES: set[str] = {
  "regular",
  "cost",
  "state",
  "subdomain",
  "regular_city_only",
}

SITE_MODE: Mode = sys.argv[1] if len(sys.argv) > 1 else "regular"
COPY_IDX: int = resolve_copy_idx(SITE_MODE)

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

