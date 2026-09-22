import os,re,json
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Golf Flip Scanner",page_icon="⛳")
st.title("⛳ Golf Flip Scanner")
st.caption("Paste an individual 2dehands / 2ememain golf listing and get an AI-powered flip analysis.")

TARGET_PROFIT=75.0
NEGOTIATE_BUFFER=0.10

def secret(name):
    try:return st.secrets.get(name,os.getenv(name,""))
    except Exception:return os.getenv(name,"")

def parse_euro(v):
    if v is None:return None
    s=re.sub(r"[^\d,.\-]","",str(v))
    if not s:return None
    if "," in s and "." in s:
        s=s.replace(".","").replace(",",".") if s.rfind(",")>s.rfind(".") else s.replace(",","")
    elif "," in s:s=s.replace(",",".")
    try:return float(s)
    except:return None

def fetch_listing(url):
    p=urlparse(url)
    if p.scheme not in ("http","https"):raise ValueError("Please enter a full https:// URL.")
    if not any(x in p.netloc.lower() for x in ("2dehands.be","2ememain.be")):raise ValueError("Please use a 2dehands.be or 2ememain.be URL.")
    if "/v/" not in p.path.lower():raise ValueError("Please paste the URL of one individual listing, not a category/search page.")

    r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 (compatible; GolfFlipScanner/0.4)","Accept-Language":"nl-BE,nl;q=0.9,en;q=0.8"},timeout=20)
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    title="";desc="";cands=[]
    t=soup.find("meta",property="og:title")
    if t:title=t.get("content","").strip()
    if not title and soup.title:title=soup.title.get_text(" ",strip=True)
    t=soup.find("meta",property="og:description")
    if t:desc=t.get("content","").strip()

    for t in soup.find_all("script",type="application/ld+json"):
        try:d=json.loads(t.string or t.get_text())
        except:continue
        for o in (d if isinstance(d,list) else [d]):
            if isinstance(o,dict):
                title=title or str(o.get("name",""))
                desc=desc or str(o.get("description",""))
                offers=o.get("offers",[])
                for x in (offers if isinstance(offers,list) else [offers]):
                    if isinstance(x,dict):
                        q=parse_euro(x.get("price"))
                        if q and q>0:cands.append(q)

    text=soup.get_text("\n",strip=True)

    # Extract euro values. Keep them as candidates; AI uses surrounding page context.
    for m in re.findall(r"(?:€\s*|EUR\s*)(\d[\d.\s]*(?:,\d{1,2})?)",text,re.I):
        q=parse_euro(m)
        if q and q>=5:cands.append(q)
    cands=list(dict.fromkeys(cands))

    # 2dehands explicitly displays "Bieden" on auction/bid listings.
    lower=text.lower()
    listing_type="auction" if "bieden" in lower else "fixed_price"
    return {"url":url,"title":title,"description":desc,"price_candidates":cands[:30],"page_text":text[:16000],"listing_type":listing_type}

def ai_analyze(x):
    key=secret("OPENAI_API_KEY")
    if not key:raise RuntimeError("OPENAI_API_KEY is not configured in Streamlit Secrets.")

    equipment_schema={"type":"object","properties":{
        "brand":{"type":"string"},"model":{"type":"string"},"category":{"type":"string"},
        "generation":{"type":"string"},"set_composition":{"type":"string"},
        "shaft":{"type":"string"},"flex":{"type":"string"},"loft":{"type":"string"},
        "handedness":{"type":"string"},"condition":{"type":"string"},"notes":{"type":"string"}},
        "required":["brand","model","category","generation","set_composition","shaft","flex","loft","handedness","condition","notes"],
        "additionalProperties":False}

    schema={"type":"object","properties":{
        "equipment":{"type":"object","properties":equipment_schema["properties"],"required":equipment_schema["required"],"additionalProperties":False},
        "identification_confidence":{"type":"number"},
        "asking_price_eur":{"type":"number"},
        "current_bid_eur":{"type":"number"},
        "estimated_resale_low_eur":{"type":"number"},
        "estimated_resale_high_eur":{"type":"number"},
        "conservative_resale_eur":{"type":"number"},
        "estimated_costs_eur":{"type":"number"},
        "risk_buffer_eur":{"type":"number"},
        "liquidity":{"type":"string"},
        "key_reason":{"type":"string"},
        "risks":{"type":"array","items":{"type":"string"}},
        "missing_information":{"type":"array","items":{"type":"string"}},
        "valuation_note":{"type":"string"}},
        "required":["equipment","identification_confidence","asking_price_eur","current_bid_eur","estimated_resale_low_eur","estimated_resale_high_eur","conservative_resale_eur","estimated_costs_eur","risk_buffer_eur","liquidity","key_reason","risks","missing_information","valuation_note"],
        "additionalProperties":False}

    prompt="""You are a conservative used-golf-equipment resale analyst.

Identify the equipment and create an INITIAL valuation.

Important:
- Never invent missing specifications. Use "Unknown".
- This listing is classified as: %s.
- If it is an auction/bidding listing, there may be NO asking price. In that case asking_price_eur must be 0.
- current_bid_eur must be 0 if no current bid is explicitly visible.
- Do not mistake unrelated euro amounts on the page for the listing price.
- Distinguish asking prices from realistic resale value.
- Unless comparable market data is supplied, explicitly call the valuation an initial estimate.
- identification_confidence is 0-100.

Listing URL:
%s

Title:
%s

Description:
%s

Price candidates found on page:
%s

Page text:
%s
"""%(x["listing_type"],x["url"],x["title"],x["description"],x["price_candidates"],x["page_text"])

    client=OpenAI(api_key=key)
    r=client.responses.create(model="gpt-5.6-luna",input=prompt,text={"format":{"type":"json_schema","name":"golf_flip_analysis","schema":schema,"strict":True}})
    return json.loads(r.output_text)

def eur(v):
    return "—" if v is None else "€{:,.0f}".format(float(v)).replace(",",".")

url=st.text_input("2dehands listing URL",placeholder="https://www.2dehands.be/v/sport-en-fitness/golf/...")

if st.button("Analyze deal",type="primary",use_container_width=True):
    if not url.strip():st.warning("Paste an individual listing URL first.");st.stop()
    try:
        with st.spinner("Retrieving listing…"):x=fetch_listing(url.strip())

        with st.expander("Listing retrieved",expanded=True):
            st.write("**Title:**",x["title"] or "Not detected")
            st.write("**Listing type:**", "Bidding / auction" if x["listing_type"]=="auction" else "Fixed price")
            st.write("**Detected price candidates:**",[eur(v) for v in x["price_candidates"]])
            st.write("**Description:**",x["description"] or "Not detected")

        with st.spinner("AI is identifying the equipment…"):r=ai_analyze(x)

        resale=float(r["conservative_resale_eur"])
        costs=max(0,float(r["estimated_costs_eur"]))
        risk=max(0,float(r["risk_buffer_eur"]))
        max_buy=max(0,resale-costs-risk-TARGET_PROFIT)
        ask=float(r["asking_price_eur"])
        bid=float(r["current_bid_eur"])

        st.divider();st.subheader("⛳ Flip Analysis")

        if x["listing_type"]=="auction":
            a,b,c=st.columns(3)
            a.metric("Current bid",eur(bid) if bid>0 else "Not shown")
            b.metric("Conservative resale",eur(resale))
            c.metric("Maximum bid",eur(max_buy))
            if bid>0:
                profit=resale-costs-risk-bid
                roi=profit/bid*100 if bid else 0
                decision="BID" if bid<=max_buy else "PASS"
                a,b,c=st.columns(3);a.metric("Profit at current bid",eur(profit));b.metric("ROI",f"{roi:.0f}%");c.metric("Confidence",f"{float(r['identification_confidence']):.0f}%")
                st.markdown("## %s %s"%({"BID":"🟢","PASS":"🔴"}[decision],decision))
            else:
                st.markdown("## 🎯 MAXIMUM BID")
                st.metric("Maximum bid",eur(max_buy))
                st.write("No current bid was visible on the listing. Treat the maximum bid as your ceiling.")
                c1,c2=st.columns(2);c1.metric("Identification confidence",f"{float(r['identification_confidence']):.0f}%");c2.metric("Liquidity",r["liquidity"])
        else:
            if ask<=0:
                st.error("The app could not reliably determine the fixed asking price.")
                st.stop()
            profit=resale-costs-risk-ask
            roi=profit/ask*100 if ask else 0
            decision="BUY" if ask<=max_buy else ("NEGOTIATE" if ask<=max_buy*(1+NEGOTIATE_BUFFER) else "PASS")
            a,b,c=st.columns(3);a.metric("Asking",eur(ask));b.metric("Conservative resale",eur(resale));c.metric("Maximum buy",eur(max_buy))
            a,b,c=st.columns(3);a.metric("Expected profit",eur(profit));b.metric("ROI",f"{roi:.0f}%");c.metric("Confidence",f"{float(r['identification_confidence']):.0f}%")
            st.markdown("## %s %s"%({"BUY":"🟢","NEGOTIATE":"🟠","PASS":"🔴"}[decision]))
            st.write("**Suggested offer:**",eur(min(max_buy,ask*.9)))

        st.write("**Why:**",r["key_reason"])
        st.write("**Liquidity:**",r["liquidity"])
        st.write("**Equipment identified**");st.json(r["equipment"])
        st.write("**Initial estimated resale range:**",f"{eur(r['estimated_resale_low_eur'])}–{eur(r['estimated_resale_high_eur'])}")
        st.caption(r["valuation_note"])
        with st.expander("Risks and missing information"):
            for v in r["risks"]:st.write("•",v)
            for v in r["missing_information"]:st.write("• Missing:",v)

        st.info("V0.4 adds support for 2dehands listings using 'Bieden'. The next major upgrade is live comparable-price research.")
    except ValueError as e:st.warning(str(e))
    except requests.HTTPError as e:st.error(f"2dehands could not be retrieved ({e.response.status_code}).")
    except Exception as e:st.error(str(e))
