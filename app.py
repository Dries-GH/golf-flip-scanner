
import os
import re
import json
from urllib.parse import urlparse, quote_plus

import requests
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

MODEL = "gpt-5.6-luna"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FlipGolf/0.7)",
      "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8"}

st.set_page_config(page_title="FlipGolf", page_icon="⛳", layout="centered")

# ----------------------------------------------------------------- style
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@700;800&display=swap');
:root{--ink:#17231f;--muted:#6b7772;--cream:#f4f1e8;--paper:#fff;--line:#e2e6df;
      --green:#1e4b3b;--green2:#2d6a4f;--orange:#c9752f;--red:#b3403d;}
html,body,[class*="css"]{font-family:"DM Sans",sans-serif;}
.stApp{background:var(--cream);color:var(--ink);}
.block-container{max-width:840px;padding-top:2rem;padding-bottom:4rem;}
h1,h2,h3{font-family:"Manrope",sans-serif!important;letter-spacing:-.035em;color:var(--ink)!important;}
#MainMenu,footer{visibility:hidden;}
.hdr{display:flex;align-items:center;gap:11px;margin-bottom:2px;}
.mark{width:38px;height:38px;border-radius:11px;background:var(--green);color:#fff;
      display:flex;align-items:center;justify-content:center;font-size:20px;}
.name{font-family:"Manrope";font-size:26px;font-weight:800;letter-spacing:-.05em;}
.tag{color:var(--muted);font-size:13px;margin:0 0 18px 49px;}
.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:14px 16px;}
.lbl{color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.09em;font-weight:700;}
.val{font-family:"Manrope";font-size:23px;font-weight:800;margin-top:5px;}
.note{color:var(--muted);font-size:11px;margin-top:2px;}
.verdict{border-radius:14px;padding:17px 20px;margin:14px 0;background:var(--paper);
         border:1px solid var(--line);border-left:5px solid var(--green2);}
.verdict .v{font-family:"Manrope";font-size:22px;font-weight:800;}
.verdict .s{color:var(--muted);font-size:13px;margin-top:3px;}
.v-BUY{border-left-color:var(--green2);} .v-NEGOTIATE{border-left-color:var(--orange);}
.v-PASS{border-left-color:var(--red);}
.row{background:var(--paper);border:1px solid var(--line);border-radius:12px;
     padding:12px 14px;margin:7px 0;}
.row-t{display:flex;justify-content:space-between;gap:14px;align-items:baseline;}
.row-n{font-weight:700;font-size:14px;}
.row-p{font-family:"Manrope";font-weight:800;white-space:nowrap;}
.row-m{color:var(--muted);font-size:11px;margin-top:4px;}
.pill{display:inline-block;padding:3px 8px;border-radius:999px;background:#e9efe9;
      color:var(--green);font-size:10px;font-weight:700;text-transform:uppercase;}
a{color:var(--green2);}
div[data-testid="stButton"] button{border-radius:10px!important;font-weight:700!important;min-height:44px;}
button[kind="primary"]{background:var(--green)!important;border-color:var(--green)!important;}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------- helpers
def secret(n):
    try: return st.secrets.get(n, os.getenv(n, ""))
    except Exception: return os.getenv(n, "")

def parse_euro(v):
    if v is None: return None
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s: return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try: return float(s)
    except Exception: return None

def eur(v):
    return "—" if v is None else "€{:,.0f}".format(float(v)).replace(",", ".")

def clamp(v, lo, hi): return max(lo, min(hi, float(v)))

def card(label, value, note=""):
    return f'<div class="card"><div class="lbl">{label}</div><div class="val">{value}</div><div class="note">{note}</div></div>'

def client():
    k = secret("OPENAI_API_KEY")
    if not k:
        st.error("OPENAI_API_KEY is not set in Streamlit Secrets.")
        st.stop()
    return OpenAI(api_key=k)

# ----------------------------------------------------------------- scraping
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_listing(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise ValueError("Paste a full https:// link.")
    if not any(d in p.netloc.lower() for d in ("2dehands.be", "2ememain.be")):
        raise ValueError("Use a 2dehands.be or 2ememain.be link.")
    if "/v/" not in p.path.lower():
        raise ValueError("Paste one individual listing, not a search page.")
    r = requests.get(url, headers=UA, timeout=20); r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")
    def og(k):
        t = s.find("meta", property=k)
        return t.get("content", "").strip() if t else ""
    title, desc, prices = og("og:title"), og("og:description"), []
    if not title and s.title: title = s.title.get_text(" ", strip=True)
    for t in s.find_all("script", type="application/ld+json"):
        try: d = json.loads(t.string or t.get_text())
        except Exception: continue
        for o in (d if isinstance(d, list) else [d]):
            if isinstance(o, dict):
                title = title or str(o.get("name", ""))
                desc = desc or str(o.get("description", ""))
                offers = o.get("offers", [])
                for x in (offers if isinstance(offers, list) else [offers]):
                    if isinstance(x, dict):
                        q = parse_euro(x.get("price"))
                        if q and q > 0: prices.append(q)
    text = s.get_text("\n", strip=True)
    for m in re.findall(r"€\s*(\d[\d.\s]*(?:,\d{1,2})?)", text):
        q = parse_euro(m)
        if q and q >= 5: prices.append(q)
    img = og("og:image")
    return {"url": url, "title": title, "description": desc, "image": img,
            "prices": list(dict.fromkeys(prices))[:12],
            "text": text[:14000],
            "type": "auction" if "bieden" in text.lower() else "fixed"}

@st.cache_data(ttl=900, show_spinner=False)
def search_2dehands(query, min_p, max_p, limit=40):
    base = "https://www.2dehands.be"
    url = f"{base}/l/sport-en-fitness/golf/q/{quote_plus(query)}/"
    if min_p or max_p:
        url += f"#PriceCentsFrom:{int((min_p or 0)*100)}|PriceCentsTo:{int((max_p or 99999)*100)}"
    r = requests.get(url, headers=UA, timeout=25); r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")
    out, seen = [], set()
    for a in s.find_all("a", href=True):
        if "/v/" not in a["href"]: continue
        u = (a["href"] if a["href"].startswith("http") else base + a["href"]).split("?")[0]
        if u in seen: continue
        blk, n = None, a
        for _ in range(4):
            n = n.parent
            if n is None: break
            if "€" in n.get_text() or "ieden" in n.get_text(): blk = n; break
        txt = blk.get_text(" ", strip=True) if blk else a.get_text(" ", strip=True)
        title = a.get_text(" ", strip=True)
        if len(title) < 5 and blk:
            h = blk.find(["h2", "h3"])
            title = h.get_text(" ", strip=True) if h else title
        if len(title) < 5: continue
        m = re.search(r"€\s*([\d.\s]*\d(?:,\d{1,2})?)", txt)
        price = parse_euro(m.group(1)) if m else None
        if price is not None:
            if min_p and price < min_p: continue
            if max_p and price > max_p: continue
        seen.add(u)
        out.append({"title": title[:130], "price": price,
                    "bidding": price is None and "ieden" in txt.lower(),
                    "url": u, "blurb": txt[:200]})
        if len(out) >= limit: break
    return out

# ----------------------------------------------------------------- AI
IDENT = {
    "type": "object",
    "properties": {
        "brand": {"type": "string"}, "model": {"type": "string"},
        "category": {"type": "string"}, "specs": {"type": "string"},
        "condition": {"type": "string"},
        "price_eur": {"type": "number"},
        "confidence": {"type": "number"},
        "checks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["brand","model","category","specs","condition","price_eur","confidence","checks"],
    "additionalProperties": False,
}

VALUE = {
    "type": "object",
    "properties": {
        "low_eur": {"type": "number"}, "high_eur": {"type": "number"},
        "likely_eur": {"type": "number"},
        "confidence": {"type": "number"},
        "liquidity": {"type": "string"},
        "summary": {"type": "string"},
        "comps": {"type": "array", "items": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "price_eur": {"type": "number"},
                           "source": {"type": "string"}, "kind": {"type": "string"},
                           "url": {"type": "string"}},
            "required": ["title","price_eur","source","kind","url"],
            "additionalProperties": False}},
    },
    "required": ["low_eur","high_eur","likely_eur","confidence","liquidity","summary","comps"],
    "additionalProperties": False,
}

def ai_identify(x):
    prompt = f"""Identify the used golf equipment in this Belgian 2dehands listing.
Never invent specs - use "Unknown" if absent. Listing type: {x['type']}.
price_eur = the actual asking price (or current bid). Euro amounts detected on the page: {x['prices']}.
If auction with no visible bid, price_eur = 0.
checks = short practical things to verify before buying (authenticity, wear, completeness).

TITLE: {x['title']}
DESCRIPTION: {x['description']}
PAGE: {x['text'][:9000]}"""
    r = client().responses.create(
        model=MODEL, input=prompt,
        text={"format": {"type": "json_schema", "name": "ident", "schema": IDENT, "strict": True}})
    return json.loads(r.output_text)

def ai_value(eq):
    prompt = f"""Research the current second-hand market value in Europe for:
{eq['brand']} {eq['model']} ({eq['category']}) - {eq['specs']} - condition: {eq['condition']}

Rules:
- Weight evidence: Belgium private (2dehands/2ememain) > Netherlands private (Marktplaats) > European used-golf retailers > eBay/international (support only).
- Never use new retail price as a resale comp.
- Never invent a URL or price. Exclude anything you cannot verify.
- likely_eur = realistic achievable private-sale price in Belgium, inside low..high. Not the highest asking price.
- confidence 0-100 = strength of evidence. If thin, say so and widen the range.
- liquidity = one of "high", "medium", "low" with how fast this sells privately.
- summary = max 2 sentences, plain language.
- Return up to 5 comps, real URLs only."""
    r = client().responses.create(
        model=MODEL,
        tools=[{"type": "web_search", "search_context_size": "high"}],
        input=prompt,
        text={"format": {"type": "json_schema", "name": "value", "schema": VALUE, "strict": True}})
    return json.loads(r.output_text)

SCREEN = {
    "type": "object",
    "properties": {"picks": {"type": "array", "items": {
        "type": "object",
        "properties": {"url": {"type": "string"}, "item": {"type": "string"},
                       "price_eur": {"type": "number"},
                       "est_resale_eur": {"type": "number"},
                       "est_profit_eur": {"type": "number"},
                       "score": {"type": "number"},
                       "why": {"type": "string"}},
        "required": ["url","item","price_eur","est_resale_eur","est_profit_eur","score","why"],
        "additionalProperties": False}}},
    "required": ["picks"],
    "additionalProperties": False,
}

def ai_screen(rows, target_profit, max_budget):
    listings = json.dumps([{"i": i, "title": r["title"], "price": r["price"],
                            "bidding": r["bidding"], "url": r["url"]}
                           for i, r in enumerate(rows)], ensure_ascii=False)
    prompt = f"""You are triaging live 2dehands golf listings for a Belgian flipper.
Budget per item: max €{max_budget:.0f}. Target profit: €{target_profit:.0f}+.

For each listing judge from the title/price whether it is plausibly underpriced versus the
European second-hand market. Use your knowledge of used golf pricing; you do not need to search.

Rules:
- Only return listings with plausible profit >= €{target_profit:.0f} after ~€35 of costs.
- Ignore: golf balls in bulk, tees, gloves, clothing, trolleys under €40, junior sets, unbranded/vintage clubs.
- Skip anything you cannot identify as a specific branded club/set.
- Be sceptical: a cheap price on an unclear listing is usually a bad club, not a bargain.
- score 0-100 = how attractive the flip is.
- est_resale_eur = realistic Belgian private-sale price. est_profit_eur = est_resale - price - 35.
- why = max 12 words.
- Copy the url exactly from the input. Return at most 8 picks, best first. Empty list is fine.

LISTINGS: {listings}"""
    r = client().responses.create(
        model=MODEL, input=prompt,
        text={"format": {"type": "json_schema", "name": "screen", "schema": SCREEN, "strict": True}})
    return json.loads(r.output_text)["picks"]

# ----------------------------------------------------------------- maths
def economics(v, price, costs, target_profit, min_roi):
    low = max(0.0, float(v["low_eur"]))
    high = max(low, float(v["high_eur"]))
    likely = clamp(v["likely_eur"] or (low + high) / 2, low, high)   # fix: always in range
    conf = clamp(v["confidence"], 0, 100)
    buffer = round(likely * (0.20 - 0.12 * conf / 100))              # fix: driven by confidence
    ceiling = max(0.0, likely - costs - buffer - target_profit)
    profit = likely - costs - buffer - price
    roi = (profit / price * 100) if price else 0.0
    if price <= 0:                                  v = "CEILING"
    elif price <= ceiling and roi >= min_roi:       v = "BUY"
    elif price <= ceiling * 1.12:                   v = "NEGOTIATE"
    else:                                           v = "PASS"
    return dict(low=low, high=high, likely=likely, conf=conf, buffer=buffer,
                ceiling=ceiling, profit=profit, roi=roi, verdict=v)

# ----------------------------------------------------------------- ui
st.markdown('<div class="hdr"><div class="mark">⛳</div><div class="name">FlipGolf</div></div>'
            '<div class="tag">Used golf. Bought with a margin.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("#### Settings")
    target_profit = st.number_input("Target profit (€)", 0.0, 1000.0, 75.0, 5.0)
    min_roi = st.number_input("Minimum ROI (%)", 0.0, 200.0, 20.0, 5.0)
    costs = st.number_input("Costs per flip (€)", 0.0, 300.0, 35.0, 5.0,
                            help="Shipping, packaging, travel, fees. Use 0 for local pickup.")
    st.caption("Ceiling = likely resale − costs − risk buffer − target profit. "
               "The buffer shrinks as research confidence rises.")

t1, t2 = st.tabs(["Analyse a listing", "Screen the market"])

# ---------------- TAB 1
with t1:
    url = st.text_input("2dehands listing URL", placeholder="https://www.2dehands.be/v/...",
                        label_visibility="collapsed")
    if st.button("Analyse", type="primary", use_container_width=True):
        if not url.strip():
            st.warning("Paste a listing link first.")
        else:
            try:
                with st.spinner("Reading listing…"):
                    x = fetch_listing(url.strip())
                with st.spinner("Identifying equipment…"):
                    eq = ai_identify(x)
                with st.spinner("Researching the market…"):
                    v = ai_value(eq)

                price = float(eq["price_eur"])
                e = economics(v, price, costs, target_profit, min_roi)

                st.markdown(f"**{eq['brand']} {eq['model']}** · {eq['category']}")
                st.caption(f"{eq['specs']} · condition: {eq['condition']} · "
                           f"{'auction' if x['type']=='auction' else 'fixed price'} · "
                           f"ID confidence {eq['confidence']:.0f}%")

                c = st.columns(4)
                c[0].markdown(card("Price", eur(price) if price else "No bid"), unsafe_allow_html=True)
                c[1].markdown(card("Likely resale", eur(e["likely"]), f"range {eur(e['low'])}–{eur(e['high'])}"), unsafe_allow_html=True)
                c[2].markdown(card("Max buy", eur(e["ceiling"]), "your hard ceiling"), unsafe_allow_html=True)
                c[3].markdown(card("Profit", eur(e["profit"]) if price else "—",
                                   f"ROI {e['roi']:.0f}%" if price else "no price yet"), unsafe_allow_html=True)

                sub = (f"Price {eur(price)} · profit {eur(e['profit'])} · ROI {e['roi']:.0f}%"
                       if price else f"No visible bid. Do not go above {eur(e['ceiling'])}.")
                st.markdown(f'<div class="verdict v-{e["verdict"]}"><div class="v">{e["verdict"]}</div>'
                            f'<div class="s">{sub}</div></div>', unsafe_allow_html=True)

                st.caption(f"{v['summary']}  ·  liquidity: {v['liquidity']}  ·  "
                           f"research confidence {e['conf']:.0f}%  ·  risk buffer {eur(e['buffer'])}")

                if v["comps"]:
                    st.markdown("**Comparable evidence**")
                    for cp in v["comps"][:5]:
                        link = (f'<a href="{cp["url"]}" target="_blank">source</a>'
                                if str(cp["url"]).startswith("http") else "")   # fix: real HTML link
                        st.markdown(f'<div class="row"><div class="row-t">'
                                    f'<div class="row-n">{cp["title"]}</div>'
                                    f'<div class="row-p">{eur(cp["price_eur"])}</div></div>'
                                    f'<div class="row-m"><span class="pill">{cp["source"]}</span> '
                                    f'&nbsp;{cp["kind"]} &nbsp;{link}</div></div>',
                                    unsafe_allow_html=True)
                else:
                    st.warning("No verifiable comps found — treat this valuation as low confidence.")

                if eq["checks"]:
                    with st.expander("Check before buying", expanded=True):
                        for i in eq["checks"]: st.write("•", i)

            except ValueError as e:  st.warning(str(e))
            except requests.HTTPError as e:
                st.error(f"2dehands could not be reached ({getattr(e.response,'status_code','?')}).")
            except Exception as e:   st.error(str(e))

# ---------------- TAB 2
with t2:
    st.caption("Scans live 2dehands golf listings and shows only the ones worth a second look.")
    a, b, c = st.columns([2, 1, 1])
    q = a.text_input("Search", value="golf", label_visibility="collapsed")
    lo = b.number_input("Min €", 0.0, 5000.0, 50.0, 10.0)
    hi = c.number_input("Max €", 0.0, 5000.0, 600.0, 10.0)

    quick = st.radio("Preset", ["Custom", "Drivers", "Iron sets", "Putters", "Full bags"],
                     horizontal=True, index=0)
    preset = {"Drivers": "driver", "Iron sets": "ijzers set",
              "Putters": "putter", "Full bags": "golfset"}.get(quick)

    if st.button("Screen market", type="primary", use_container_width=True):
        term = preset or q
        try:
            with st.spinner(f"Scanning 2dehands for “{term}”…"):
                rows = search_2dehands(term, lo, hi)
            if not rows:
                st.warning("Nothing found — try a broader term or wider price range.")
            else:
                st.caption(f"{len(rows)} listings found. Triaging…")
                with st.spinner("AI is picking the deals…"):
                    picks = ai_screen(rows, target_profit, hi)
                if not picks:
                    st.info("No listing looked clearly underpriced right now. "
                            "That is a normal result — try again later or widen the range.")
                else:
                    st.success(f"{len(picks)} worth a look")
                    for p in sorted(picks, key=lambda z: -z["score"]):
                        st.markdown(
                            f'<div class="row"><div class="row-t">'
                            f'<div class="row-n">{p["item"]}</div>'
                            f'<div class="row-p">{eur(p["price_eur"])}</div></div>'
                            f'<div class="row-m"><span class="pill">score {p["score"]:.0f}</span> '
                            f'&nbsp;est. resale {eur(p["est_resale_eur"])} · '
                            f'profit ~{eur(p["est_profit_eur"])} &nbsp;'
                            f'<a href="{p["url"]}" target="_blank">open listing</a></div>'
                            f'<div class="row-m">{p["why"]}</div></div>',
                            unsafe_allow_html=True)
                    st.caption("Screening is a rough filter from titles and prices only. "
                               "Paste a promising link into the Analyse tab for real market research.")
        except requests.HTTPError as e:
            st.error(f"2dehands could not be reached ({getattr(e.response,'status_code','?')}).")
        except Exception as e:
            st.error(str(e))
