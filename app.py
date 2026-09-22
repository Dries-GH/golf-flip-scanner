
import os
import re
import json
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Golf Flip Scanner", page_icon="⛳", layout="wide")

DEFAULT_TARGET_PROFIT = 75.0
DEFAULT_MIN_ROI = 25.0
NEGOTIATE_BUFFER = 0.10

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

def clean_url(url):
    return url.split("?")[0].strip()

def fetch_listing(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise ValueError("Please enter a full https:// URL.")
    if not any(x in p.netloc.lower() for x in ("2dehands.be", "2ememain.be")):
        raise ValueError("Please use a 2dehands.be or 2ememain.be URL.")
    if "/v/" not in p.path.lower():
        raise ValueError("Please paste the URL of one individual listing, not a category/search page.")

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; GolfFlipScanner/0.5)",
        "Accept-Language": "nl-BE,nl;q=0.9,fr-BE,fr;q=0.8,en;q=0.7",
    }
    r = requests.get(clean_url(url), headers=headers, timeout=20)
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

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(tag.string or tag.get_text())
        except Exception:
            continue
        for o in (d if isinstance(d, list) else [d]):
            if not isinstance(o, dict):
                continue
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
        "url": clean_url(url),
        "title": title,
        "description": desc,
        "price_candidates": cands[:30],
        "page_text": text[:18000],
        "listing_type": listing_type,
    }

EQUIPMENT_PROPERTIES = {
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
}

EQUIPMENT_SCHEMA = {
    "type": "object",
    "properties": EQUIPMENT_PROPERTIES,
    "required": list(EQUIPMENT_PROPERTIES.keys()),
    "additionalProperties": False,
}

def initial_identification(x):
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
            "risks": {"type": "array", "items": {"type": "string"}},
            "missing_information": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "equipment", "identification_confidence", "asking_price_eur",
            "current_bid_eur", "risks", "missing_information"
        ],
        "additionalProperties": False,
    }

    prompt = f"""
You are the equipment-identification stage of a used-golf resale scanner.

Classify the listing and identify the exact golf equipment from the supplied listing.
Never invent missing specifications: use "Unknown".
The listing type detected by the scraper is: {x["listing_type"]}.
For bidding listings, asking_price_eur must be 0 unless a fixed price is explicitly shown.
current_bid_eur must be 0 unless a current bid is explicitly visible.
Do not mistake unrelated euro values on the page for the listing price.
Identification confidence is 0-100.

URL:
{x["url"]}

Title:
{x["title"]}

Description:
{x["description"]}

Price candidates:
{x["price_candidates"]}

Page text:
{x["page_text"]}
"""

    client = OpenAI(api_key=key)
    r = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt,
        text={"format": {
            "type": "json_schema",
            "name": "golf_equipment_identification",
            "schema": schema,
            "strict": True,
        }},
    )
    return json.loads(r.output_text)

def market_research(equipment, listing):
    key = secret("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured in Streamlit Secrets.")

    schema = {
        "type": "object",
        "properties": {
            "search_summary": {"type": "string"},
            "comparables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "price_eur": {"type": "number"},
                        "condition": {"type": "string"},
                        "similarity": {"type": "number"},
                        "why_comparable": {"type": "string"},
                        "source_type": {"type": "string"},
                    },
                    "required": [
                        "title", "url", "price_eur", "condition",
                        "similarity", "why_comparable", "source_type"
                    ],
                    "additionalProperties": False,
                },
            },
            "estimated_resale_low_eur": {"type": "number"},
            "estimated_resale_high_eur": {"type": "number"},
            "conservative_resale_eur": {"type": "number"},
            "estimated_costs_eur": {"type": "number"},
            "risk_buffer_eur": {"type": "number"},
            "liquidity": {"type": "string"},
            "valuation_confidence": {"type": "number"},
            "valuation_note": {"type": "string"},
        },
        "required": [
            "search_summary", "comparables", "estimated_resale_low_eur",
            "estimated_resale_high_eur", "conservative_resale_eur",
            "estimated_costs_eur", "risk_buffer_eur", "liquidity",
            "valuation_confidence", "valuation_note"
        ],
        "additionalProperties": False,
    }

    e = equipment
    exact = " ".join(v for v in [
        e.get("brand"), e.get("model"), e.get("generation"),
        e.get("set_composition"), e.get("shaft"), e.get("flex"), e.get("loft")
    ] if v and v != "Unknown")

    prompt = f"""
You are the market-research and valuation stage of a used-golf flipping scanner.

Use web search to find CURRENT comparable listings. Prioritize individual listings on
2dehands.be and 2ememain.be. You may use Marktplaats.nl or established European golf
resellers only as secondary evidence when there are too few good Belgian comparables.

Search for the EXACT equipment first. Match model/generation, club count, shaft/flex,
handedness and condition as closely as possible. Do not include a listing just because
it contains a similar brand. Exclude obvious unrelated products, accessories, bundles
with materially different contents, and dealer listings when private comparables exist.

For each comparable, provide its actual listing URL and displayed asking/bid price.
Never invent a price or URL. If price is not visible, do not include the comparable.
Similarity is 0-100.

IMPORTANT:
- These are ASKING prices, not confirmed transaction prices.
- A conservative resale estimate should normally be below or around the lower/middle
  portion of relevant private asking prices, unless the evidence clearly supports otherwise.
- Do not use retail-new prices as direct used resale prices.
- If evidence is weak, widen the range and lower valuation_confidence.
- Estimated costs should include realistic selling/shipping/payment costs for a small
  Belgian private resale. Do not double-count the purchase price.
- Risk buffer should reflect condition/spec uncertainty and market/liquidity risk.
- liquidity should be one of: High, Medium, Low.
- valuation_confidence is 0-100.
- If there are fewer than 3 genuinely relevant comparables, say so explicitly.

TARGET LISTING:
URL: {listing["url"]}
Title: {listing["title"]}
Description: {listing["description"]}
Listing type: {listing["listing_type"]}

IDENTIFIED EQUIPMENT:
{json.dumps(e, ensure_ascii=False)}

EXACT SEARCH TERMS:
{exact}
"""

    client = OpenAI(api_key=key)
    r = client.responses.create(
        model="gpt-5.6-luna",
        tools=[{"type": "web_search"}],
        tool_choice={"type": "web_search"},
        input=prompt,
        text={"format": {
            "type": "json_schema",
            "name": "golf_market_research",
            "schema": schema,
            "strict": True,
        }},
    )
    return json.loads(r.output_text)

def calculate(resale, costs, risk, purchase, target_profit):
    max_buy = max(0.0, resale - costs - risk - target_profit)
    profit = resale - costs - risk - purchase
    roi = (profit / purchase * 100.0) if purchase > 0 else None
    return max_buy, profit, roi

def decision_for(price, max_buy):
    if price <= max_buy:
        return "BUY"
    if price <= max_buy * (1 + NEGOTIATE_BUFFER):
        return "NEGOTIATE"
    return "PASS"

# Sidebar settings
with st.sidebar:
    st.header("Scanner settings")
    target_profit = st.number_input(
        "Target profit (€)", min_value=0.0, value=DEFAULT_TARGET_PROFIT, step=25.0
    )
    min_roi = st.number_input(
        "Minimum ROI (%)", min_value=0.0, value=DEFAULT_MIN_ROI, step=5.0
    )
    st.caption("These settings change the decision threshold; the market valuation is researched separately.")
    st.divider()
    st.caption("V0.5 adds live comparable-price research via OpenAI web search.")

st.title("⛳ Golf Flip Scanner")
st.caption("Paste an individual 2dehands / 2ememain golf listing and get a market-backed flip analysis.")

url = st.text_input(
    "2dehands listing URL",
    placeholder="https://www.2dehands.be/v/sport-en-fitness/golf/..."
)

if st.button("Analyze deal", type="primary", use_container_width=True):
    if not url.strip():
        st.warning("Paste an individual listing URL first.")
        st.stop()

    try:
        with st.spinner("Retrieving listing…"):
            listing = fetch_listing(url.strip())

        with st.expander("1. Listing retrieved", expanded=False):
            st.write("**Title:**", listing["title"] or "Not detected")
            st.write(
                "**Listing type:**",
                "Bidding / auction" if listing["listing_type"] == "auction" else "Fixed price"
            )
            st.write(
                "**Detected price candidates:**",
                [eur(v) for v in listing["price_candidates"]]
            )
            st.write("**Description:**", listing["description"] or "Not detected")

        with st.spinner("Identifying the exact equipment…"):
            identification = initial_identification(listing)

        st.subheader("2. Equipment identification")
        e = identification["equipment"]
        a, b, c, d = st.columns(4)
        a.metric("Brand / model", f'{e["brand"]} {e["model"]}')
        b.metric("Set", e["set_composition"])
        c.metric("Shaft / flex", f'{e["shaft"]} / {e["flex"]}')
        d.metric("ID confidence", f'{identification["identification_confidence"]:.0f}%')

        with st.expander("Equipment details"):
            st.json(e)
            if identification["missing_information"]:
                st.write("**Missing information:**")
                for item in identification["missing_information"]:
                    st.write("•", item)

        with st.spinner("Searching live market comparables…"):
            research = market_research(e, listing)

        comps = research["comparables"]
        st.subheader("3. Live market evidence")

        if comps:
            import pandas as pd
            rows = []
            for comp in comps:
                rows.append({
                    "Comparable": comp["title"],
                    "Price": eur(comp["price_eur"]),
                    "Condition": comp["condition"],
                    "Similarity": f'{comp["similarity"]:.0f}%',
                    "Why": comp["why_comparable"],
                    "Source": comp["source_type"],
                    "URL": comp["url"],
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "URL": st.column_config.LinkColumn("Listing", display_text="Open")
                },
            )
        else:
            st.warning("No usable live comparables were found. The valuation below is therefore low-confidence.")

        st.caption(research["search_summary"])

        resale = float(research["conservative_resale_eur"])
        costs = max(0.0, float(research["estimated_costs_eur"]))
        risk = max(0.0, float(research["risk_buffer_eur"]))
        max_buy, _, _ = calculate(resale, costs, risk, 0, target_profit)

        ask = float(identification["asking_price_eur"])
        bid = float(identification["current_bid_eur"])

        st.subheader("4. Flip economics")

        if listing["listing_type"] == "auction":
            current = bid if bid > 0 else None
            a, b, c, d = st.columns(4)
            a.metric("Current bid", eur(current) if current else "Not shown")
            b.metric("Conservative resale", eur(resale))
            c.metric("Costs + risk", eur(costs + risk))
            d.metric("Maximum bid", eur(max_buy))

            if current:
                profit = resale - costs - risk - current
                roi = profit / current * 100 if current else 0
                # ROI is part of the user's threshold, but max bid already includes target profit.
                decision = "BID" if (current <= max_buy and roi >= min_roi) else "PASS"
                a, b, c = st.columns(3)
                a.metric("Profit at current bid", eur(profit))
                b.metric("ROI", f"{roi:.0f}%")
                c.metric("Valuation confidence", f'{research["valuation_confidence"]:.0f}%')
                st.markdown(f"## {'🟢' if decision == 'BID' else '🔴'} {decision}")
            else:
                st.markdown("## 🎯 MAXIMUM BID")
                st.metric("Your ceiling", eur(max_buy))
                st.write("No current bid was visible. Treat the maximum bid as your hard ceiling.")
        else:
            if ask <= 0:
                st.error("The app could not reliably determine the fixed asking price.")
                st.stop()

            profit = resale - costs - risk - ask
            roi = profit / ask * 100 if ask else 0
            decision = decision_for(ask, max_buy) if roi >= min_roi else "PASS"

            a, b, c, d = st.columns(4)
            a.metric("Asking", eur(ask))
            b.metric("Conservative resale", eur(resale))
            c.metric("Maximum buy", eur(max_buy))
            d.metric("Valuation confidence", f'{research["valuation_confidence"]:.0f}%')

            a, b = st.columns(2)
            a.metric("Expected profit", eur(profit))
            b.metric("ROI", f"{roi:.0f}%")

            icon = {"BUY": "🟢", "NEGOTIATE": "🟠", "PASS": "🔴"}[decision]
            st.markdown(f"## {icon} {decision}")
            st.write("**Suggested offer:**", eur(min(max_buy, ask * 0.90)))

        st.subheader("5. Valuation")
        a, b, c, d = st.columns(4)
        a.metric("Resale range low", eur(research["estimated_resale_low_eur"]))
        b.metric("Resale range high", eur(research["estimated_resale_high_eur"]))
        c.metric("Conservative resale", eur(resale))
        d.metric("Liquidity", research["liquidity"])

        st.write("**Valuation basis:**", research["valuation_note"])
        st.write("**Research confidence:**", f'{research["valuation_confidence"]:.0f}%')

        with st.expander("Risk & diligence checklist"):
            for item in identification["risks"]:
                st.write("•", item)
            for item in identification["missing_information"]:
                st.write("• Missing:", item)

        st.subheader("6. Decision formula")
        st.code(
            f"Maximum purchase price = conservative resale ({eur(resale)}) "
            f"- costs ({eur(costs)}) - risk buffer ({eur(risk)}) "
            f"- target profit ({eur(target_profit)})\n"
            f"= {eur(max_buy)}"
        )

        st.info(
            "Live comparables are current asking/bid evidence, not confirmed sale prices. "
            "Use the scanner as a decision-support tool and verify the listing condition/specs before buying."
        )

    except ValueError as e:
        st.warning(str(e))
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "unknown"
        st.error(f"2dehands could not be retrieved ({code}).")
    except Exception as e:
        st.error(str(e))
