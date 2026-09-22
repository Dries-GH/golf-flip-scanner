import os, re, json
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Golf Flip Scanner", page_icon="⛳")
st.title("⛳ Golf Flip Scanner")
st.caption("Paste a 2dehands / 2ememain golf listing and get an AI-powered flip analysis.")

def secret(name):
    try:
        return st.secrets.get(name, os.getenv(name, ""))
    except Exception:
        return os.getenv(name, "")

def fetch_listing(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Please enter a full URL starting with https://")
    if not any(x in parsed.netloc.lower() for x in ("2dehands.be", "2ememain.be")):
        raise ValueError("For V0.1, please use a 2dehands.be or 2ememain.be listing URL.")

    r = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; GolfFlipScanner/0.1)",
        "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8"
    }, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    title = ""
    description = ""
    price = ""

    tag = soup.find("meta", property="og:title")
    if tag: title = tag.get("content", "").strip()
    if not title and soup.title: title = soup.title.get_text(" ", strip=True)

    tag = soup.find("meta", property="og:description")
    if tag: description = tag.get("content", "").strip()

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for obj in items:
            if not isinstance(obj, dict): continue
            title = title or str(obj.get("name", ""))
            description = description or str(obj.get("description", ""))
            offers = obj.get("offers", {})
            if isinstance(offers, dict) and offers.get("price"):
                price = str(offers["price"])

    text = soup.get_text("\n", strip=True)
    if not price:
        m = re.search(r"(?:€\s*|EUR\s*)(\d+(?:[.,]\d{1,2})?)", text, re.I)
        if m: price = m.group(1).replace(".", "").replace(",", ".")

    return {
        "url": url, "title": title, "description": description,
        "price": price, "page_text": text[:12000]
    }

def analyze(listing):
    key = secret("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured yet.")

    client = OpenAI(api_key=key)
    system = """You are Golf Flip Scanner, a conservative used-golf resale analyst.
Identify the equipment and calculate an initial flip case. Never invent missing specs.
Use minimum target profit €75 and minimum ROI 25%.
Do not pretend live market research was performed unless comparable data is supplied.
Return ONLY valid JSON with keys:
equipment, identification_confidence, asking_price_eur, estimated_resale_low_eur,
estimated_resale_high_eur, conservative_resale_eur, estimated_costs_eur,
risk_buffer_eur, target_profit_eur, maximum_buy_price_eur,
expected_profit_at_asking_eur, roi_at_asking_percent, liquidity,
decision, suggested_offer_eur, key_reason, risks, missing_information, valuation_note."""
    prompt = f"""Analyze this listing.
URL: {listing['url']}
Title: {listing['title']}
Detected price: {listing['price']}
Description: {listing['description']}
Page text:
{listing['page_text']}"""
    res = client.responses.create(
        model="gpt-5-mini",
        input=[{"role":"system","content":system},{"role":"user","content":prompt}]
    )
    return json.loads(res.output_text)

def eur(v):
    if v in (None, ""): return "—"
    try: return "€{:,.0f}".format(float(v)).replace(",", ".")
    except: return str(v)

url = st.text_input("2dehands listing URL", placeholder="https://www.2dehands.be/v/...")

if st.button("Analyze deal", type="primary", use_container_width=True):
    if not url.strip():
        st.warning("Paste a listing URL first.")
        st.stop()
    try:
        with st.spinner("Retrieving listing…"):
            listing = fetch_listing(url.strip())

        with st.expander("Listing retrieved", expanded=True):
            st.write("**Title:**", listing["title"] or "Not detected")
            st.write("**Price:**", listing["price"] or "Not detected")
            st.write("**Description:**", listing["description"] or "Not detected")

        with st.spinner("AI is analyzing the equipment…"):
            result = analyze(listing)

        st.divider()
        st.subheader("⛳ Flip Analysis")
        decision = str(result.get("decision","UNKNOWN")).upper()
        icon = {"BUY":"🟢","NEGOTIATE":"🟠","PASS":"🔴"}.get(decision,"⚪")

        a,b,c = st.columns(3)
        a.metric("Asking", eur(result.get("asking_price_eur")))
        b.metric("Conservative resale", eur(result.get("conservative_resale_eur")))
        c.metric("Maximum buy", eur(result.get("maximum_buy_price_eur")))

        a,b,c = st.columns(3)
        a.metric("Expected profit", eur(result.get("expected_profit_at_asking_eur")))
        b.metric("ROI", f"{result.get('roi_at_asking_percent','—')}%")
        c.metric("Confidence", f"{result.get('identification_confidence','—')}%")

        st.markdown(f"## {icon} {decision}")
        st.write(result.get("key_reason",""))
        st.write("**Equipment**")
        st.json(result.get("equipment", {}))
        st.write("**Suggested offer:**", eur(result.get("suggested_offer_eur")))
        st.write("**Liquidity:**", result.get("liquidity","—"))

        with st.expander("Risks and missing information"):
            st.write(result.get("risks", []))
            st.write(result.get("missing_information", []))

        st.info("V0.1: AI identification and deal logic are connected. Live comparable-price research is the next upgrade.")

    except requests.HTTPError as e:
        st.error(f"2dehands could not be retrieved ({e.response.status_code}).")
    except Exception as e:
        st.error(str(e))
