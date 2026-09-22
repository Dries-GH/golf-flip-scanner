import os
import re
import json
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

# -----------------------------
# App configuration
# -----------------------------
st.set_page_config(
    page_title="FlipGolf",
    page_icon="⛳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Brand / styling
# -----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');

:root {
  --ink: #17231f;
  --muted: #66736e;
  --cream: #f4f1e8;
  --paper: #fbfaf6;
  --line: #dfe3dc;
  --green: #1e4b3b;
  --green-2: #2d6a4f;
  --lime: #b8d66a;
  --orange: #d98145;
  --red: #b94b48;
}

html, body, [class*="css"] {
  font-family: "DM Sans", sans-serif;
}

.stApp {
  background: var(--cream);
  color: var(--ink);
}

.block-container {
  max-width: 1180px;
  padding-top: 2.0rem;
  padding-bottom: 4rem;
}

h1, h2, h3 {
  font-family: "Manrope", sans-serif !important;
  color: var(--ink) !important;
  letter-spacing: -0.035em;
}

.brand {
  display:flex;
  align-items:center;
  gap:12px;
  margin-bottom:4px;
}
.brand-mark {
  width:42px;
  height:42px;
  border-radius:12px;
  background:var(--green);
  color:white;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:22px;
  box-shadow: 0 8px 24px rgba(30,75,59,.16);
}
.brand-name {
  font-family:"Manrope",sans-serif;
  font-size:28px;
  font-weight:800;
  letter-spacing:-.05em;
}
.brand-tag {
  color:var(--muted);
  font-size:13px;
  margin-left:54px;
  margin-top:-4px;
}

.hero {
  background:var(--paper);
  border:1px solid var(--line);
  border-radius:20px;
  padding:28px 30px 26px;
  box-shadow:0 10px 35px rgba(23,35,31,.05);
  margin:18px 0 22px;
}

.hero-kicker {
  text-transform:uppercase;
  letter-spacing:.12em;
  font-size:11px;
  font-weight:700;
  color:var(--green-2);
  margin-bottom:8px;
}
.hero-title {
  font-family:"Manrope",sans-serif;
  font-size:34px;
  line-height:1.08;
  font-weight:800;
  letter-spacing:-.05em;
  margin-bottom:8px;
}
.hero-copy {
  color:var(--muted);
  font-size:14px;
  max-width:760px;
}

div[data-testid="stTextInput"] input {
  border-radius:10px !important;
  border:1px solid #cfd6cf !important;
  background:white !important;
  color:var(--ink) !important;
}
div[data-testid="stButton"] button {
  border-radius:10px !important;
  font-weight:700 !important;
  min-height:44px;
}
button[kind="primary"] {
  background:var(--green) !important;
  border-color:var(--green) !important;
}

.section-label {
  text-transform:uppercase;
  letter-spacing:.12em;
  font-size:11px;
  font-weight:700;
  color:var(--green-2);
  margin:26px 0 8px;
}

.metric-card {
  background:var(--paper);
  border:1px solid var(--line);
  border-radius:15px;
  padding:16px 18px;
  min-height:94px;
}
.metric-label {
  color:var(--muted);
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.08em;
  font-weight:700;
}
.metric-value {
  font-family:"Manrope",sans-serif;
  font-size:25px;
  font-weight:800;
  margin-top:6px;
}
.metric-note {
  color:var(--muted);
  font-size:11px;
  margin-top:2px;
}

.decision {
  border-radius:16px;
  padding:19px 22px;
  margin:16px 0;
  border:1px solid var(--line);
  background:var(--paper);
}
.decision-title {
  font-family:"Manrope",sans-serif;
  font-size:23px;
  font-weight:800;
  letter-spacing:-.035em;
}
.decision-sub {
  color:var(--muted);
  font-size:13px;
  margin-top:4px;
}
.decision.buy { border-left:5px solid var(--green-2); }
.decision.negotiate { border-left:5px solid var(--orange); }
.decision.pass { border-left:5px solid var(--red); }
.decision.ceiling { border-left:5px solid var(--green); }

.comp {
  background:var(--paper);
  border:1px solid var(--line);
  border-radius:14px;
  padding:14px 16px;
  margin:8px 0;
}
.comp-head {
  display:flex;
  justify-content:space-between;
  gap:16px;
}
.comp-title {
  font-weight:700;
  color:var(--ink);
}
.comp-price {
  font-family:"Manrope",sans-serif;
  font-weight:800;
  white-space:nowrap;
}
.comp-meta {
  color:var(--muted);
  font-size:11px;
  margin-top:4px;
}
.comp-rationale {
  color:#4f5c57;
  font-size:12px;
  margin-top:7px;
}

.pill {
  display:inline-block;
  padding:4px 8px;
  border-radius:999px;
  background:#e8eee9;
  color:var(--green);
  font-size:10px;
  font-weight:700;
  text-transform:uppercase;
  letter-spacing:.05em;
}

.small-note {
  color:var(--muted);
  font-size:11px;
  line-height:1.5;
}

.sidebar-title {
  font-family:"Manrope",sans-serif;
  font-weight:800;
  font-size:18px;
  letter-spacing:-.03em;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Helpers
# -----------------------------
def secret(name):
    try:
        return st.secrets.get(name, os.getenv(name, ""))
    except Exception:
        return os.getenv(name, "")

def parse_euro(v):
    if v is None:
        return None
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def eur(v):
    if v is None:
        return "—"
    return "€{:,.0f}".format(float(v)).replace(",", ".")

def pct(v):
    return f"{float(v):.0f}%"

def clamp(v, lo, hi):
    return max(lo, min(hi, float(v)))

def metric_card(label, value, note=""):
    return f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      <div class="metric-note">{note}</div>
    </div>
    """

# -----------------------------
# Listing retrieval
# -----------------------------
def fetch_listing(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise ValueError("Please enter a full https:// URL.")
    if not any(x in p.netloc.lower() for x in ("2dehands.be", "2ememain.be")):
        raise ValueError("Please use a 2dehands.be or 2ememain.be URL.")
    if "/v/" not in p.path.lower():
        raise ValueError("Please paste the URL of one individual listing, not a category/search page.")

    r = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; FlipGolf/0.6)",
            "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
        },
        timeout=20,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    title = ""
    desc = ""
    cands = []

    t = soup.find("meta", property="og:title")
    if t:
        title = t.get("content", "").strip()
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    t = soup.find("meta", property="og:description")
    if t:
        desc = t.get("content", "").strip()

    for t in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(t.string or t.get_text())
        except Exception:
            continue
        for o in (d if isinstance(d, list) else [d]):
            if isinstance(o, dict):
                title = title or str(o.get("name", ""))
                desc = desc or str(o.get("description", ""))
                offers = o.get("offers", [])
                for x in (offers if isinstance(offers, list) else [offers]):
                    if isinstance(x, dict):
                        q = parse_euro(x.get("price"))
                        if q and q > 0:
                            cands.append(q)

    text = soup.get_text("\n", strip=True)
    for m in re.findall(r"(?:€\s*|EUR\s*)(\d[\d.\s]*(?:,\d{1,2})?)", text, re.I):
        q = parse_euro(m)
        if q and q >= 5:
            cands.append(q)

    cands = list(dict.fromkeys(cands))
    lower = text.lower()
    listing_type = "auction" if "bieden" in lower else "fixed_price"

    return {
        "url": url,
        "title": title,
        "description": desc,
        "price_candidates": cands[:30],
        "page_text": text[:18000],
        "listing_type": listing_type,
    }

# -----------------------------
# OpenAI analysis
# -----------------------------
EQUIPMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "brand": {"type": "string"},
        "model": {"type": "string"},
        "category": {"type": "string"},
        "generation": {"type": "string"},
        "set_composition": {"type": "string"},
        "shaft": {"type": "string"},
        "flex": {"type": "string"},
        "loft": {"type": "string"},
        "handedness": {"type": "string"},
        "condition": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": [
        "brand","model","category","generation","set_composition",
        "shaft","flex","loft","handedness","condition","notes"
    ],
    "additionalProperties": False,
}

def identify_equipment(x):
    key = secret("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured in Streamlit Secrets.")

    schema = {
        "type": "object",
        "properties": {
            "equipment": EQUIPMENT_SCHEMA,
            "identification_confidence": {"type": "number"},
            "asking_price_eur": {"type": "number"},
            "current_bid_eur": {"type": "number"},
            "condition_summary": {"type": "string"},
            "spec_summary": {"type": "string"},
            "risks": {"type": "array", "items": {"type": "string"}},
            "missing_information": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "equipment","identification_confidence","asking_price_eur",
            "current_bid_eur","condition_summary","spec_summary",
            "risks","missing_information"
        ],
        "additionalProperties": False,
    }

    prompt = f"""
You are identifying used golf equipment from a Belgian 2dehands/2ememain listing.

Rules:
- Never invent specifications.
- Use "Unknown" when the listing does not provide a detail.
- Listing type: {x["listing_type"]}.
- For bidding listings, current_bid_eur must be 0 unless a current bid is explicitly visible.
- Do not mistake unrelated euro amounts for the listing price.
- Extract the exact model/generation/set composition/shaft/flex where supported.

URL:
{x["url"]}

TITLE:
{x["title"]}

DESCRIPTION:
{x["description"]}

PAGE TEXT:
{x["page_text"]}
"""

    client = OpenAI(api_key=key)
    r = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt,
        text={"format": {"type": "json_schema", "name": "equipment_identification", "schema": schema, "strict": True}},
    )
    return json.loads(r.output_text)

def research_market(equipment):
    key = secret("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured in Streamlit Secrets.")

    eq = equipment["equipment"]
    schema = {
        "type": "object",
        "properties": {
            "market_summary": {"type": "string"},
            "market_confidence": {"type": "number"},
            "estimated_sale_low_eur": {"type": "number"},
            "estimated_sale_high_eur": {"type": "number"},
            "conservative_sale_eur": {"type": "number"},
            "liquidity": {"type": "string"},
            "liquidity_reason": {"type": "string"},
            "comps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "price_eur": {"type": "number"},
                        "market": {"type": "string"},
                        "source_type": {"type": "string"},
                        "url": {"type": "string"},
                        "match_pct": {"type": "number"},
                        "price_type": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": [
                        "title","price_eur","market","source_type","url",
                        "match_pct","price_type","rationale"
                    ],
                    "additionalProperties": False,
                },
            },
            "excluded_evidence": {"type": "array", "items": {"type": "string"}},
            "valuation_note": {"type": "string"},
        },
        "required": [
            "market_summary","market_confidence","estimated_sale_low_eur",
            "estimated_sale_high_eur","conservative_sale_eur","liquidity",
            "liquidity_reason","comps","excluded_evidence","valuation_note"
        ],
        "additionalProperties": False,
    }

    search_prompt = f"""
You are the market-research engine for a Belgian golf equipment flipping app.

Find CURRENT market evidence for this exact used golf equipment:

Brand: {eq["brand"]}
Model: {eq["model"]}
Category: {eq["category"]}
Generation: {eq["generation"]}
Set: {eq["set_composition"]}
Shaft: {eq["shaft"]}
Flex: {eq["flex"]}
Loft: {eq["loft"]}
Handedness: {eq["handedness"]}
Condition: {eq["condition"]}

Research rules:
1. Prioritise Belgium private listings: 2dehands.be and 2ememain.be.
2. Then Netherlands private listings, especially Marktplaats.
3. Then established European used-golf retailers.
4. eBay and other international sources are supporting evidence only.
5. Prefer the exact model/generation and similar set composition/specification.
6. Do NOT use new retail prices as direct resale comps.
7. Clearly distinguish asking price, current bid, and sold/completed price when the source makes that distinction.
8. Never invent a URL or price. If a source cannot be verified, exclude it.
9. Try to find at least 5 useful pieces of evidence if available, but return fewer rather than padding with weak comps.
10. Estimate an achievable private-sale price, not simply the highest asking price.
11. Account qualitatively for liquidity: how many relevant listings exist, how niche the configuration is, and whether the observed prices are asking prices rather than completed sales.
12. Match percentage is your estimate of specification/condition similarity, not a confidence score.
13. In the final valuation, weight Belgian private evidence most heavily. Netherlands is secondary. Retail/eBay is tertiary.
14. If evidence is weak, say so explicitly and widen the uncertainty range rather than inventing precision.

Return the evidence and valuation in the requested JSON format. Include the source URL for every comparable.
"""

    client = OpenAI(api_key=key)
    r = client.responses.create(
        model="gpt-5.6-luna",
        tools=[{"type": "web_search"}],
        input=search_prompt,
        text={"format": {"type": "json_schema", "name": "market_research", "schema": schema, "strict": True}},
    )
    return json.loads(r.output_text)

# -----------------------------
# UI
# -----------------------------
st.markdown("""
<div class="brand">
  <div class="brand-mark">⛳</div>
  <div class="brand-name">FlipGolf</div>
</div>
<div class="brand-tag">Used golf. Bought with a margin.</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="sidebar-title">Scanner settings</div>', unsafe_allow_html=True)
    target_profit = st.number_input("Target profit (€)", min_value=0.0, max_value=1000.0, value=75.0, step=5.0)
    min_roi = st.number_input("Minimum ROI (%)", min_value=0.0, max_value=200.0, value=20.0, step=5.0)
    st.divider()
    st.markdown("**Valuation hierarchy**")
    st.markdown(
        '<div class="small-note">Belgium private → Netherlands private → European used-golf → international support.</div>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown('<div class="small-note">Market evidence is researched live. Prices are asking/bid evidence unless explicitly identified as sold prices.</div>', unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="hero-kicker">Deal scanner · v0.6</div>
  <div class="hero-title">Know your number before you buy.</div>
  <div class="hero-copy">Paste a 2dehands or 2ememain golf listing. FlipGolf identifies the equipment, researches the current second-hand market and gives you a disciplined purchase ceiling.</div>
</div>
""", unsafe_allow_html=True)

url = st.text_input(
    "Listing URL",
    placeholder="https://www.2dehands.be/v/sport-en-fitness/golf/...",
    label_visibility="collapsed",
)

analyze = st.button("Analyse listing", type="primary", use_container_width=True)

if analyze:
    if not url.strip():
        st.warning("Paste an individual listing URL first.")
        st.stop()

    try:
        with st.spinner("Reading listing…"):
            x = fetch_listing(url.strip())

        st.markdown('<div class="section-label">01 · Listing</div>', unsafe_allow_html=True)
        st.markdown(f"### {x['title'] or 'Golf listing'}")
        st.caption("Bidding / auction" if x["listing_type"] == "auction" else "Fixed price listing")
        if x["description"]:
            st.write(x["description"])

        with st.spinner("Identifying equipment…"):
            identification = identify_equipment(x)

        eq = identification["equipment"]
        st.markdown('<div class="section-label">02 · Equipment</div>', unsafe_allow_html=True)

        e1, e2, e3, e4 = st.columns(4)
        e1.markdown(metric_card("Model", f"{eq['brand']} {eq['model']}", eq["category"]), unsafe_allow_html=True)
        e2.markdown(metric_card("Set", eq["set_composition"], "Composition"), unsafe_allow_html=True)
        e3.markdown(metric_card("Shaft", eq["shaft"], eq["flex"]), unsafe_allow_html=True)
        e4.markdown(metric_card("Condition", eq["condition"], f"ID confidence {pct(identification['identification_confidence'])}"), unsafe_allow_html=True)

        with st.spinner("Researching current market evidence…"):
            market = research_market(identification)

        low = max(0.0, float(market["estimated_sale_low_eur"]))
        high = max(low, float(market["estimated_sale_high_eur"]))
        resale = max(0.0, float(market["conservative_sale_eur"]))
        market_conf = clamp(market["market_confidence"], 0, 100)

        # Cost model. These are deliberately separated from market valuation.
        platform_cost = 0.0
        shipping_cost = 15.0
        selling_cost = 20.0
        risk_buffer = max(25.0, round((high - low) * 0.35, 0))
        total_costs = platform_cost + shipping_cost + selling_cost

        max_buy = max(0.0, resale - total_costs - risk_buffer - target_profit)
        ask = float(identification["asking_price_eur"])
        bid = float(identification["current_bid_eur"])

        st.markdown('<div class="section-label">03 · Market</div>', unsafe_allow_html=True)
        st.markdown("### What the market says")

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(metric_card("Achievable sale", f"{eur(low)}–{eur(high)}", "Estimated private-sale range"), unsafe_allow_html=True)
        m2.markdown(metric_card("Conservative resale", eur(resale), "Used for purchase ceiling"), unsafe_allow_html=True)
        m3.markdown(metric_card("Liquidity", market["liquidity"], market["liquidity_reason"]), unsafe_allow_html=True)
        m4.markdown(metric_card("Research confidence", pct(market_conf), "Strength of available evidence"), unsafe_allow_html=True)

        if market["market_summary"]:
            st.info(market["market_summary"])

        st.markdown('<div class="section-label">04 · Comparable evidence</div>', unsafe_allow_html=True)
        comps = market.get("comps", [])
        if not comps:
            st.warning("No sufficiently reliable comparable listings were found. The valuation should be treated as low-confidence.")
        else:
            for comp in comps[:8]:
                title = comp["title"] or "Comparable listing"
                url2 = comp["url"]
                link = f"[Open listing]({url2})" if url2.startswith("http") else ""
                st.markdown(
                    f"""
                    <div class="comp">
                      <div class="comp-head">
                        <div class="comp-title">{title}</div>
                        <div class="comp-price">{eur(comp['price_eur'])}</div>
                      </div>
                      <div class="comp-meta">
                        <span class="pill">{comp['market']}</span>
                        &nbsp; {comp['source_type']} · {comp['price_type']} · {comp['match_pct']:.0f}% match
                        &nbsp; {link}
                      </div>
                      <div class="comp-rationale">{comp['rationale']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if market.get("excluded_evidence"):
            with st.expander("Evidence excluded from valuation"):
                for item in market["excluded_evidence"]:
                    st.write("•", item)

        st.markdown('<div class="section-label">05 · Flip economics</div>', unsafe_allow_html=True)

        if x["listing_type"] == "auction":
            profit_at_ceiling = resale - total_costs - risk_buffer - max_buy
            roi_at_ceiling = profit_at_ceiling / max_buy * 100 if max_buy else 0
            current_label = eur(bid) if bid > 0 else "Not shown"

            a, b, c, d = st.columns(4)
            a.markdown(metric_card("Current bid", current_label, "Visible on listing" if bid > 0 else "No visible bid"), unsafe_allow_html=True)
            b.markdown(metric_card("Conservative resale", eur(resale), "Market-backed"), unsafe_allow_html=True)
            c.markdown(metric_card("Maximum bid", eur(max_buy), "Hard ceiling"), unsafe_allow_html=True)
            d.markdown(metric_card("Profit at ceiling", eur(profit_at_ceiling), f"ROI {roi_at_ceiling:.0f}%"), unsafe_allow_html=True)

            if bid > 0:
                profit = resale - total_costs - risk_buffer - bid
                roi = profit / bid * 100 if bid else 0
                decision = "BID" if bid <= max_buy and roi >= min_roi else "PASS"
                cls = "ceiling" if decision == "BID" else "pass"
                subtitle = f"Current bid {eur(bid)} · estimated profit {eur(profit)} · ROI {roi:.0f}%"
            else:
                decision = "CEILING"
                cls = "ceiling"
                subtitle = "No current bid was visible. Treat the maximum bid as your hard ceiling."

        else:
            if ask <= 0:
                st.error("The listing appears to be fixed-price, but no reliable asking price was detected.")
                st.stop()

            profit = resale - total_costs - risk_buffer - ask
            roi = profit / ask * 100 if ask else 0
            decision = "BUY" if ask <= max_buy and roi >= min_roi else ("NEGOTIATE" if ask <= max_buy * 1.10 else "PASS")
            cls = {"BUY": "buy", "NEGOTIATE": "negotiate", "PASS": "pass"}[decision]
            subtitle = f"Asking {eur(ask)} · estimated profit {eur(profit)} · ROI {roi:.0f}%"

            a, b, c, d = st.columns(4)
            a.markdown(metric_card("Asking", eur(ask), "Listing price"), unsafe_allow_html=True)
            b.markdown(metric_card("Conservative resale", eur(resale), "Market-backed"), unsafe_allow_html=True)
            c.markdown(metric_card("Maximum buy", eur(max_buy), "Hard ceiling"), unsafe_allow_html=True)
            d.markdown(metric_card("Profit at asking", eur(profit), f"ROI {roi:.0f}%"), unsafe_allow_html=True)

        st.markdown(
            f'<div class="decision {cls}"><div class="decision-title">{decision}</div><div class="decision-sub">{subtitle}</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-label">06 · Purchase ceiling</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="decision ceiling">
              <div class="decision-title">{eur(max_buy)}</div>
              <div class="decision-sub">
                Conservative resale {eur(resale)} − selling/logistics costs {eur(total_costs)}
                − risk buffer {eur(risk_buffer)} − target profit {eur(target_profit)}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-label">07 · Checks before buying</div>', unsafe_allow_html=True)
        checks = identification["missing_information"] + identification["risks"]
        if not checks:
            st.success("No additional red flags were identified from the listing text.")
        else:
            with st.expander("Open checklist", expanded=True):
                for item in checks:
                    st.write("•", item)

        with st.expander("Equipment details"):
            st.json(eq)

        st.caption(
            "Market prices are observed listing/bid evidence, not guaranteed transaction prices. "
            "The scanner uses conservative assumptions and should be treated as decision support."
        )

    except ValueError as e:
        st.warning(str(e))
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        st.error(f"2dehands could not be retrieved ({status}).")
    except Exception as e:
        st.error(str(e))
