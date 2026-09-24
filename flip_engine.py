
"""Engine layer: scraping, AI identification, valuation, screening, deal maths."""
import os
import re
import json
from urllib.parse import urlparse, quote_plus

import requests
from bs4 import BeautifulSoup

MODEL = "gpt-5.6-luna"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FlipGolf/1.0; +analysis)",
      "Accept-Language": "nl-BE,nl;q=0.9,fr-BE;q=0.8,en;q=0.7"}

CATEGORY_PATH = "/l/sport-en-fitness/golf/"
ALLOWED_HOSTS = ("2dehands.be", "2ememain.be")


# ----------------------------------------------------------------- utils
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


def clamp(v, lo, hi):
    return max(lo, min(hi, float(v)))


def client(api_key):
    from openai import OpenAI
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)


# ----------------------------------------------------------------- scraping
def fetch_listing(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise ValueError("Paste a full https:// link.")
    if not any(d in p.netloc.lower() for d in ALLOWED_HOSTS):
        raise ValueError("Only 2dehands.be and 2ememain.be links are supported.")
    if "/v/" not in p.path.lower():
        raise ValueError("That looks like a search page. Paste one individual listing.")

    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")

    def og(k):
        t = s.find("meta", property=k)
        return t.get("content", "").strip() if t else ""

    title, desc, prices, images = og("og:title"), og("og:description"), [], []
    if not title and s.title:
        title = s.title.get_text(" ", strip=True)

    for t in s.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(t.string or t.get_text())
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
                        prices.append(q)

    main_img = og("og:image")
    if main_img:
        images.append(main_img)
    for im in s.find_all("img", src=True):
        src = im["src"]
        if src.startswith("http") and any(k in src for k in ("image", "media", "img")):
            if src not in images:
                images.append(src)
        if len(images) >= 6:
            break

    text = s.get_text("\n", strip=True)
    for m in re.findall(r"€\s*(\d[\d.\s]*(?:,\d{1,2})?)", text):
        q = parse_euro(m)
        if q and q >= 5:
            prices.append(q)

    low = text.lower()
    ltype = "auction" if ("bieden" in low or "bod" in low) else "fixed"
    loc = ""
    m = re.search(r"(?:Ophalen|Locatie|Plaats)[:\s]+([A-ZÀ-Ü][\wÀ-ü\-\' ]{2,30})", text)
    if m:
        loc = m.group(1).strip()

    return {"url": url, "title": title, "description": desc, "images": images[:6],
            "prices": list(dict.fromkeys(prices))[:12], "text": text[:14000],
            "listing_type": ltype, "location": loc}


def search_listings(query="", min_p=None, max_p=None, limit=45, sort_new=True, site="2dehands.be"):
    """Scrape the live golf category/search results page."""
    base = f"https://www.{site}"
    url = base + CATEGORY_PATH
    if query.strip():
        url += f"q/{quote_plus(query.strip())}/"
    params = []
    if sort_new:
        params.append("sortBy=SORT_INDEX&sortOrder=DECREASING")
    if params:
        url += "?" + "&".join(params)

    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")

    out, seen = [], set()
    for a in s.find_all("a", href=True):
        href = a["href"]
        if "/v/" not in href:
            continue
        u = (href if href.startswith("http") else base + href).split("?")[0]
        if u in seen:
            continue

        blk, n = None, a
        for _ in range(4):
            n = n.parent
            if n is None:
                break
            g = n.get_text(" ", strip=True)
            if "€" in g or "ieden" in g:
                blk = n
                break
        txt = blk.get_text(" ", strip=True) if blk else a.get_text(" ", strip=True)

        title = a.get_text(" ", strip=True)
        if len(title) < 5 and blk:
            h = blk.find(["h2", "h3"])
            title = h.get_text(" ", strip=True) if h else title
        if len(title) < 5:
            continue

        m = re.search(r"€\s*([\d.\s]*\d(?:,\d{1,2})?)", txt)
        price = parse_euro(m.group(1)) if m else None
        bidding = price is None and "ieden" in txt.lower()

        if price is not None:
            if min_p and price < min_p:
                continue
            if max_p and price > max_p:
                continue

        thumb = ""
        if blk:
            im = blk.find("img", src=True)
            if im and im["src"].startswith("http"):
                thumb = im["src"]

        seen.add(u)
        out.append({"title": title[:140], "price": price, "bidding": bidding,
                    "url": u, "blurb": txt[:220], "thumb": thumb})
        if len(out) >= limit:
            break
    return out


# ----------------------------------------------------------------- AI schemas
IDENT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_golf_equipment": {"type": "boolean"},
        "brand": {"type": "string"},
        "model": {"type": "string"},
        "category": {"type": "string"},
        "generation_year": {"type": "string"},
        "specs": {"type": "string"},
        "set_composition": {"type": "string"},
        "condition": {"type": "string"},
        "condition_grade": {"type": "string"},
        "price_eur": {"type": "number"},
        "confidence": {"type": "number"},
        "risks": {"type": "array", "items": {"type": "string"}},
        "checks": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["is_golf_equipment", "brand", "model", "category", "generation_year", "specs",
                 "set_composition", "condition", "condition_grade", "price_eur", "confidence",
                 "risks", "checks", "questions"],
    "additionalProperties": False,
}

VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "low_eur": {"type": "number"},
        "high_eur": {"type": "number"},
        "likely_eur": {"type": "number"},
        "confidence": {"type": "number"},
        "liquidity": {"type": "string"},
        "days_to_sell": {"type": "number"},
        "demand_note": {"type": "string"},
        "summary": {"type": "string"},
        "best_channel": {"type": "string"},
        "comps": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "price_eur": {"type": "number"},
                "source": {"type": "string"},
                "market": {"type": "string"},
                "kind": {"type": "string"},
                "match_pct": {"type": "number"},
                "url": {"type": "string"},
            },
            "required": ["title", "price_eur", "source", "market", "kind", "match_pct", "url"],
            "additionalProperties": False}},
        "excluded": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["low_eur", "high_eur", "likely_eur", "confidence", "liquidity", "days_to_sell",
                 "demand_note", "summary", "best_channel", "comps", "excluded"],
    "additionalProperties": False,
}

SCREEN_SCHEMA = {
    "type": "object",
    "properties": {"picks": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "item": {"type": "string"},
            "category": {"type": "string"},
            "price_eur": {"type": "number"},
            "est_resale_eur": {"type": "number"},
            "est_profit_eur": {"type": "number"},
            "score": {"type": "number"},
            "confidence": {"type": "string"},
            "why": {"type": "string"},
        },
        "required": ["url", "item", "category", "price_eur", "est_resale_eur",
                     "est_profit_eur", "score", "confidence", "why"],
        "additionalProperties": False}}},
    "required": ["picks"],
    "additionalProperties": False,
}

NEGOTIATE_SCHEMA = {
    "type": "object",
    "properties": {
        "opening_offer_eur": {"type": "number"},
        "walk_away_eur": {"type": "number"},
        "message_nl": {"type": "string"},
        "message_fr": {"type": "string"},
        "leverage": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["opening_offer_eur", "walk_away_eur", "message_nl", "message_fr", "leverage"],
    "additionalProperties": False,
}


def _json_call(api_key, prompt, schema, name, tools=None, effort=None):
    kw = {"model": MODEL, "input": prompt,
          "text": {"format": {"type": "json_schema", "name": name,
                              "schema": schema, "strict": True}}}
    if tools:
        kw["tools"] = tools
    if effort:
        kw["reasoning"] = {"effort": effort}
    r = client(api_key).responses.create(**kw)
    return json.loads(r.output_text)


# ----------------------------------------------------------------- AI calls
def identify(api_key, x):
    prompt = f"""You are appraising a used golf listing from the Belgian marketplace 2dehands.

Rules:
- Never invent specifications. Use "Unknown" where the listing is silent.
- is_golf_equipment=false if this is not sellable golf equipment (e.g. bulk balls, clothing, tees).
- price_eur: the real asking price, or the current bid for an auction. Listing type is "{x['listing_type']}".
  Euro amounts detected on the page: {x['prices']}. Ignore unrelated amounts. If auction with no visible bid, use 0.
- condition_grade: exactly one of "New", "Like New", "Good", "Fair", "Poor".
- confidence 0-100 for your identification.
- risks: scam, counterfeit, hidden-damage or misdescription concerns. Empty list if genuinely none.
- checks: concrete physical checks before paying (serial number, face wear, shaft integrity, headcover, completeness).
- questions: up to 3 sharp questions to ask the seller before travelling.

TITLE: {x['title']}
LOCATION: {x['location'] or 'Unknown'}
DESCRIPTION: {x['description']}
PAGE TEXT: {x['text'][:9000]}"""
    return _json_call(api_key, prompt, IDENT_SCHEMA, "identification")


def value(api_key, eq, location=""):
    prompt = f"""Research the CURRENT second-hand market value for this used golf equipment and
return a valuation for a private seller based in Antwerp, Belgium.

ITEM: {eq['brand']} {eq['model']} ({eq['category']})
Generation/year: {eq['generation_year']}
Specs: {eq['specs']}
Set: {eq['set_composition']}
Condition: {eq['condition_grade']} - {eq['condition']}
Seller location: {location or 'Belgium'}

Evidence hierarchy (weight in this order):
1. Belgium private listings (2dehands.be, 2ememain.be)
2. Netherlands private listings (Marktplaats.nl)
3. Established European used-golf retailers (Golfbidder, Golf Avenue EU, second-hand pro shops)
4. eBay / international - supporting evidence only

Hard rules:
- Never use new retail price as a resale comp.
- Never invent a URL or a price. If you cannot verify a source, put it in "excluded" instead.
- Distinguish asking price, current bid and sold price in the "kind" field.
- likely_eur = realistic achievable private-sale price in Belgium. It MUST sit between low_eur and high_eur.
  It is not the highest asking price you found.
- confidence 0-100 = strength of the evidence. Thin or contradictory evidence means a low number
  and a wider low..high range. Do not fake precision.
- liquidity: exactly "high", "medium" or "low". days_to_sell = realistic days to sell privately in Belgium.
- best_channel: where this sells best (e.g. "2dehands local pickup", "eBay NL", "golf forum").
- summary: max 2 sentences, plain English, no hedging filler.
- comps: up to 6, real verifiable URLs only, with match_pct = specification similarity."""
    return _json_call(api_key, prompt, VALUE_SCHEMA, "valuation",
                      tools=[{"type": "web_search", "search_context_size": "high"}])


def screen(api_key, rows, target_profit, costs, max_budget):
    listings = json.dumps([{"title": r["title"], "price": r["price"],
                            "bidding": r["bidding"], "url": r["url"]} for r in rows],
                          ensure_ascii=False)
    prompt = f"""You are triaging live 2dehands golf listings for a professional flipper in Antwerp.

Economics: max spend €{max_budget:.0f} per item, costs about €{costs:.0f} per flip,
minimum acceptable profit €{target_profit:.0f}.

Judge each listing from its title and price using your knowledge of used golf pricing in Europe.
Do not search the web - this is a fast first-pass filter.

Hard rules:
- Return ONLY listings where plausible profit >= €{target_profit:.0f} after costs.
- Exclude: bulk golf balls, tees, gloves, clothing, shoes, bags under €30, trolleys under €40,
  junior/beginner starter sets, unbranded or pre-2005 clubs, broken items, and anything you
  cannot identify as a specific branded club or set.
- Be sceptical. A very low price on a vague listing usually means a worn or fake club, not a bargain.
  If the title is too vague to identify the model, skip it.
- est_resale_eur = realistic Belgian private-sale price for that exact item in average used condition.
- est_profit_eur = est_resale_eur - price_eur - {costs:.0f}
- score 0-100 = attractiveness of the flip (margin, liquidity, certainty combined).
- confidence: "high", "medium" or "low" - how sure you are the title identifies the real item.
- why: max 12 words, concrete.
- Copy each url EXACTLY from the input. Never modify or invent a url.
- Return at most 10 picks, best first. An empty list is a valid and expected answer.

LISTINGS:
{listings}"""
    return _json_call(api_key, prompt, SCREEN_SCHEMA, "screening")["picks"]


def negotiate(api_key, eq, econ, price):
    prompt = f"""Write a negotiation plan for buying this used golf item privately in Belgium.

Item: {eq['brand']} {eq['model']} ({eq['category']}), condition {eq['condition_grade']}
Seller asking: €{price:.0f}
My realistic resale estimate: €{econ['likely']:.0f}
My absolute maximum purchase price: €{econ['ceiling']:.0f}
Known risks: {', '.join(eq['risks']) or 'none noted'}

Rules:
- opening_offer_eur: a credible opening offer, clearly below my ceiling, not insultingly low.
- walk_away_eur: never above €{econ['ceiling']:.0f}.
- message_nl: short, polite, natural Belgian Dutch. Friendly, specific about the item,
  mentions collection in person, makes the offer concrete. No emoji, no exaggerated politeness.
- message_fr: the same message in Belgian French.
- leverage: up to 4 short factual negotiation points (wear, missing headcover, newer model out, thin demand)."""
    return _json_call(api_key, prompt, NEGOTIATE_SCHEMA, "negotiation")


# ----------------------------------------------------------------- deal maths
def economics(v, price, costs, target_profit, min_roi):
    low = max(0.0, float(v["low_eur"]))
    high = max(low, float(v["high_eur"]))
    raw = float(v.get("likely_eur") or 0)
    likely = clamp(raw if raw > 0 else (low + high) / 2, low, high)

    conf = clamp(v.get("confidence", 50), 0, 100)
    liq = str(v.get("liquidity", "medium")).lower()
    liq_add = {"high": 0.0, "medium": 0.03, "low": 0.07}.get(liq, 0.03)
    buf_rate = (0.20 - 0.12 * conf / 100) + liq_add
    buffer = round(likely * buf_rate)

    ceiling = max(0.0, likely - costs - buffer - target_profit)
    profit = likely - costs - buffer - float(price or 0)
    roi = (profit / price * 100) if price else 0.0

    if not price:
        verdict, why = "SET CEILING", f"No price visible. Never bid above €{ceiling:.0f}."
    elif price <= ceiling and roi >= min_roi:
        verdict, why = "BUY", f"€{profit:.0f} profit at {roi:.0f}% ROI, inside your ceiling."
    elif price <= ceiling * 1.12:
        verdict, why = "NEGOTIATE", f"Needs about €{max(0, price - ceiling):.0f} off to clear your ceiling."
    else:
        verdict, why = "PASS", f"€{price - ceiling:.0f} above your maximum buy price."

    return {"low": low, "high": high, "likely": likely, "conf": conf, "buffer": buffer,
            "buf_rate": buf_rate * 100, "ceiling": ceiling, "profit": profit, "roi": roi,
            "verdict": verdict, "why": why, "spread": high - low}

# ----------------------------------------------------------------- multi-market connectors (V0.7)
def _market_url_for_search(site, query):
    from urllib.parse import quote_plus
    q = quote_plus(query.strip()) if query.strip() else ""
    if site == "2dehands.be":
        return f"https://www.2dehands.be/l/sport-en-fitness/golf/q/{q}/" if q else "https://www.2dehands.be/l/sport-en-fitness/golf/"
    if site == "2ememain.be":
        return f"https://www.2ememain.be/l/sport-en-fitness/golf/q/{q}/" if q else "https://www.2ememain.be/l/sport-en-fitness/golf/"
    if site == "marktplaats.nl":
        return f"https://www.marktplaats.nl/l/sport-en-fitness/golf/q/{q}/" if q else "https://www.marktplaats.nl/l/sport-en-fitness/golf/"
    return ""


def search_marketplace_html(query="", min_p=None, max_p=None, limit=30, site="2dehands.be"):
    """Lightweight prototype connector for public search pages. Uses the same normalized schema."""
    base = f"https://www.{site}"
    url = _market_url_for_search(site, query)
    if not url:
        return []
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")
    out, seen = [], set()
    for a in s.find_all("a", href=True):
        href = a["href"]
        if site in ("2dehands.be", "2ememain.be") and "/v/" not in href:
            continue
        if site == "marktplaats.nl" and "/v/" not in href and "/a/" not in href:
            continue
        u = href if href.startswith("http") else base + href
        u = u.split("?")[0]
        if u in seen:
            continue
        parent = a
        txt = a.get_text(" ", strip=True)
        for _ in range(5):
            parent = parent.parent
            if parent is None:
                break
            t = parent.get_text(" ", strip=True)
            if "€" in t or "Bieden" in t or "bieden" in t:
                txt = t
                break
        title = a.get_text(" ", strip=True)
        if len(title) < 5:
            continue
        m = re.search(r"€\s*([\d.\s]*\d(?:,\d{1,2})?)", txt)
        price = parse_euro(m.group(1)) if m else None
        bidding = price is None and any(x in txt.lower() for x in ("bieden", "bod"))
        if price is not None:
            if min_p is not None and price < min_p: continue
            if max_p is not None and price > max_p: continue
        thumb = ""
        if parent:
            im = parent.find("img", src=True)
            if im and im["src"].startswith("http"): thumb = im["src"]
        seen.add(u)
        out.append({"title": title[:140], "price": price, "bidding": bidding, "url": u,
                    "blurb": txt[:220], "thumb": thumb, "market": site})
        if len(out) >= limit:
            break
    return out


def search_ebay(query="", min_p=None, max_p=None, limit=30, marketplace="EBAY_BE"):
    """eBay Browse API connector. Requires EBAY_CLIENT_ID/EBAY_CLIENT_SECRET in secrets."""
    cid, secret = os.getenv("EBAY_CLIENT_ID"), os.getenv("EBAY_CLIENT_SECRET")
    if not cid or not secret:
        return [], "eBay API credentials not configured"
    token_r = requests.post("https://api.sandbox.ebay.com/identity/v1/oauth2/token",
        auth=(cid, secret), data={"grant_type":"client_credentials","scope":"https://api.ebay.com/oauth/api_scope"},
        headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=20)
    # Production credentials should use the production token endpoint.
    if token_r.status_code != 200:
        token_r = requests.post("https://api.ebay.com/identity/v1/oauth2/token",
            auth=(cid, secret), data={"grant_type":"client_credentials","scope":"https://api.ebay.com/oauth/api_scope"},
            headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=20)
    token_r.raise_for_status()
    token = token_r.json()["access_token"]
    params = {"q": query or "golf", "limit": min(limit, 200), "offset": 0}
    filters = ["conditions:{USED}"]
    if min_p is not None or max_p is not None:
        filters.append(f"price:[{min_p or 0}..{max_p or 100000}]")
    params["filter"] = ",".join(filters)
    headers = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": marketplace}
    r = requests.get("https://api.ebay.com/buy/browse/v1/item_summary/search", params=params,
                     headers=headers, timeout=25)
    r.raise_for_status()
    items = r.json().get("itemSummaries", [])
    out = []
    for it in items:
        price = parse_euro((it.get("price") or {}).get("value"))
        out.append({"title": it.get("title", "")[:140], "price": price,
                    "bidding": "AUCTION" in str(it.get("buyingOptions", [])),
                    "url": it.get("itemWebUrl", ""), "blurb": it.get("shortDescription", "")[:220],
                    "thumb": (it.get("image") or {}).get("imageUrl", ""), "market": "eBay Belgium"})
    return out, None


def search_markets(query="", min_p=None, max_p=None, limit_each=20, markets=None):
    markets = markets or ["2dehands.be", "marktplaats.nl"]
    rows, errors = [], []
    for site in markets:
        try:
            if site == "eBay Belgium":
                got, err = search_ebay(query, min_p, max_p, limit_each)
                rows.extend(got)
                if err: errors.append(err)
            else:
                rows.extend(search_marketplace_html(query, min_p, max_p, limit_each, site))
        except Exception as e:
            errors.append(f"{site}: {type(e).__name__}: {e}")
    return rows, errors
