import os,re,json
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Golf Flip Scanner",page_icon="⛳")
st.title("⛳ Golf Flip Scanner")
st.caption("Paste a 2dehands / 2ememain golf listing and get an AI-powered flip analysis.")
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
    if not any(x in p.netloc.lower() for x in ("2dehands.be","2ememain.be")):raise ValueError("Please use a 2dehands.be or 2ememain.be listing URL.")
    r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 (compatible; GolfFlipScanner/0.2)","Accept-Language":"nl-BE,nl;q=0.9,en;q=0.8"},timeout=20)
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
                title=title or str(o.get("name",""));desc=desc or str(o.get("description",""))
                offers=o.get("offers",[])
                for x in (offers if isinstance(offers,list) else [offers]):
                    if isinstance(x,dict):
                        q=parse_euro(x.get("price"))
                        if q and q>0:cands.append(q)
    text=soup.get_text("\n",strip=True)
    for m in re.findall(r"(?:€\s*|EUR\s*)(\d[\d.\s]*(?:,\d{1,2})?)",text,re.I):
        q=parse_euro(m)
        if q and q>=5:cands.append(q)
    return {"url":url,"title":title,"description":desc,"price_candidates":list(dict.fromkeys(cands))[:20],"page_text":text[:14000]}

def analyze(x):
    key=secret("OPENAI_API_KEY")
    if not key:raise RuntimeError("OPENAI_API_KEY is not configured in Streamlit Secrets.")
    schema={"type":"object","properties":{
        "equipment":{"type":"object"},"identification_confidence":{"type":"number"},
        "asking_price_eur":{"type":"number"},"estimated_resale_low_eur":{"type":"number"},
        "estimated_resale_high_eur":{"type":"number"},"conservative_resale_eur":{"type":"number"},
        "estimated_costs_eur":{"type":"number"},"risk_buffer_eur":{"type":"number"},
        "liquidity":{"type":"string"},"key_reason":{"type":"string"},
        "risks":{"type":"array","items":{"type":"string"}},
        "missing_information":{"type":"array","items":{"type":"string"}},
        "valuation_note":{"type":"string"}},
        "required":["equipment","identification_confidence","asking_price_eur","estimated_resale_low_eur","estimated_resale_high_eur","conservative_resale_eur","estimated_costs_eur","risk_buffer_eur","liquidity","key_reason","risks","missing_information","valuation_note"],
        "additionalProperties":False}
    prompt="""You are a conservative used-golf resale analyst. Identify the equipment and create an INITIAL valuation.
Never invent specifications. asking_price_eur MUST be the actual listing asking price, never 0 unless genuinely zero.
Price candidates are clues. Distinguish asking prices from realistic resale value. Without comparable data, explicitly call the valuation an initial estimate. identification_confidence is 0-100.

Listing URL:
%s

Title:
%s

Price candidates:
%s

Description:
%s

Page text:
%s
"""%(x["url"],x["title"],x["price_candidates"],x["description"],x["page_text"])
    client=OpenAI(api_key=key)
    r=client.responses.create(model="gpt-5.6-luna",input=prompt,text={"format":{"type":"json_schema","name":"golf_flip_analysis","schema":schema,"strict":True}})
    return json.loads(r.output_text)

def eur(v):
    return "—" if v is None else "€{:,.0f}".format(float(v)).replace(",",".")

url=st.text_input("2dehands listing URL",placeholder="https://www.2dehands.be/v/...")
if st.button("Analyze deal",type="primary",use_container_width=True):
    if not url.strip():st.warning("Paste a listing URL first.");st.stop()
    try:
        with st.spinner("Retrieving listing…"):x=fetch_listing(url.strip())
        with st.expander("Listing retrieved",expanded=True):
            st.write("**Title:**",x["title"] or "Not detected")
            st.write("**Detected price candidates:**",[eur(v) for v in x["price_candidates"]])
            st.write("**Description:**",x["description"] or "Not detected")
        with st.spinner("AI is identifying the equipment…"):r=analyze(x)
        ask=float(r["asking_price_eur"]);resale=float(r["conservative_resale_eur"])
        costs=max(0,float(r["estimated_costs_eur"]));risk=max(0,float(r["risk_buffer_eur"]))
        maxbuy=max(0,resale-costs-risk-TARGET_PROFIT);profit=resale-costs-risk-ask
        roi=(profit/ask*100) if ask>0 else 0
        decision="BUY" if ask<=maxbuy else ("NEGOTIATE" if ask<=maxbuy*(1+NEGOTIATE_BUFFER) else "PASS")
        offer=min(maxbuy,ask*.9)
        st.divider();st.subheader("⛳ Flip Analysis")
        a,b,c=st.columns(3);a.metric("Asking",eur(ask));b.metric("Conservative resale",eur(resale));c.metric("Maximum buy",eur(maxbuy))
        a,b,c=st.columns(3);a.metric("Expected profit",eur(profit));b.metric("ROI",f"{roi:.0f}%");c.metric("Confidence",f"{float(r['identification_confidence']):.0f}%")
        st.markdown("## %s %s"%({"BUY":"🟢","NEGOTIATE":"🟠","PASS":"🔴"}[decision],decision))
        st.write(r["key_reason"]);st.write("**Suggested offer:**",eur(offer));st.write("**Liquidity:**",r["liquidity"])
        st.write("**Equipment**");st.json(r["equipment"])
        st.write("**Estimated resale range:**",f"{eur(r['estimated_resale_low_eur'])}–{eur(r['estimated_resale_high_eur'])}")
        st.caption(r["valuation_note"])
        with st.expander("Risks and missing information"):
            for v in r["risks"]:st.write("•",v)
            for v in r["missing_information"]:st.write("• Missing:",v)
        st.info("V0.2 fixes the broken JSON output and performs the deal calculation in the app. Live comparable-price research is next.")
    except requests.HTTPError as e:st.error(f"2dehands could not be retrieved ({e.response.status_code}).")
    except Exception as e:st.error(str(e))
