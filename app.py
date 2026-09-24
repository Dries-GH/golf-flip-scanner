
import os
from datetime import date, datetime

import pandas as pd
import requests
import streamlit as st

import flip_engine as E
import flip_store as DB

st.set_page_config(page_title="Flip It — Market Scanner", page_icon="↗",
                   layout="wide", initial_sidebar_state="expanded")
DB.init()

# ============================================================ design system
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');

:root{
  --ink:#14201C; --ink2:#3B4A44; --muted:#7A8781; --faint:#A8B2AC;
  --bg:#FBFAF7; --surface:#FFFFFF; --line:#E6EAE4; --line2:#F0F3EE;
  --green:#1E4B3B; --green2:#2E6B50; --greenbg:#EDF5EF;
  --amber:#B57324; --amberbg:#FDF4E7;
  --red:#A93F3C; --redbg:#FBEEED;
  --blue:#2C5A78; --bluebg:#EDF3F7;
}

/* kill streamlit chrome */
#MainMenu, footer, header[data-testid="stHeader"] {display:none!important;}
div[data-testid="stToolbar"]{display:none!important;}
div[data-testid="stDecoration"]{display:none!important;}

html,body,[class*="css"],.stApp{font-family:'Inter',-apple-system,sans-serif;}
.stApp{background:var(--bg);}
.block-container{max-width:1240px;padding:1.6rem 2rem 5rem;}

h1,h2,h3,h4{color:var(--ink)!important;letter-spacing:-.02em;font-weight:700;}

/* ---------- force light form controls (fixes dark-theme collision) ---------- */
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input{
  background:var(--surface)!important; color:var(--ink)!important;
  border:1px solid #D7DED8!important; border-radius:9px!important;
  font-size:13.5px!important; box-shadow:none!important;
}
.stTextInput input:focus, .stNumberInput input:focus{
  border-color:var(--green2)!important; box-shadow:0 0 0 3px rgba(46,107,80,.12)!important;
}
.stTextInput input::placeholder{color:var(--faint)!important;}
div[data-testid="stWidgetLabel"] p, label p{
  color:var(--ink2)!important; font-size:11px!important; font-weight:600!important;
  text-transform:uppercase; letter-spacing:.07em;
}
div[data-testid="stNumberInput"] button{
  background:var(--line2)!important; border:1px solid #D7DED8!important; color:var(--ink2)!important;
}
div[data-baseweb="select"]>div{
  background:var(--surface)!important; border:1px solid #D7DED8!important;
  border-radius:9px!important; color:var(--ink)!important; font-size:13.5px!important;
}
div[data-testid="stSelectbox"] svg{fill:var(--muted)!important;}

/* segmented control / radio as pills */
div[role="radiogroup"]{gap:6px!important; flex-wrap:wrap;}
div[role="radiogroup"] label{
  background:var(--surface)!important; border:1px solid #D9E0DA!important;
  border-radius:999px!important; padding:6px 14px!important; margin:0!important;
  font-size:12.5px!important; font-weight:600!important; color:var(--ink2)!important;
  cursor:pointer; transition:.12s;
}
div[role="radiogroup"] label:hover{border-color:var(--green2)!important;}
div[role="radiogroup"] label[data-checked="true"], div[role="radiogroup"] label:has(input:checked){
  background:var(--green)!important; border-color:var(--green)!important; color:#fff!important;
}
div[role="radiogroup"] label > div:first-child{display:none!important;}
div[role="radiogroup"] label p{color:inherit!important;text-transform:none!important;
  font-size:12.5px!important;letter-spacing:0!important;}

/* buttons */
div[data-testid="stButton"] button{
  border-radius:9px!important; font-weight:600!important; font-size:13.5px!important;
  min-height:42px; border:1px solid #D7DED8!important; background:var(--surface)!important;
  color:var(--ink)!important; transition:.12s;
}
div[data-testid="stButton"] button:hover{border-color:var(--green2)!important;}
button[kind="primary"]{
  background:var(--green)!important; border-color:var(--green)!important; color:#fff!important;
}
button[kind="primary"]:hover{background:#163A2D!important;}

/* tabs */
div[data-baseweb="tab-list"]{
  gap:2px; background:transparent; border-bottom:1px solid var(--line); margin-bottom:22px;
}
button[data-baseweb="tab"]{
  background:transparent!important; border:none!important; padding:10px 16px!important;
  font-size:13.5px!important; font-weight:600!important; color:var(--muted)!important;
}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--green)!important;}
div[data-baseweb="tab-highlight"]{background:var(--green)!important;height:2px!important;}

/* sidebar */
section[data-testid="stSidebar"]{background:#F5F6F2!important;border-right:1px solid var(--line);}
section[data-testid="stSidebar"] .block-container{padding-top:1.5rem;}
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label p{color:var(--ink2)!important;}

/* ---------- components ---------- */
.topbar{display:flex;align-items:center;justify-content:space-between;
  padding-bottom:16px;border-bottom:1px solid var(--line);margin-bottom:22px;}
.logo{display:flex;align-items:center;gap:11px;}
.logo-m{width:34px;height:34px;border-radius:9px;background:var(--green);color:#fff;
  display:flex;align-items:center;justify-content:center;font-size:17px;}
.logo-t{font-family:'Fraunces',serif;font-size:20px;font-weight:700;color:var(--ink);letter-spacing:-.01em;}
.logo-s{font-size:11px;color:var(--muted);margin-top:-2px;}

.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:6px;}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:13px 15px;}
.kpi-l{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);}
.kpi-v{font-size:22px;font-weight:700;color:var(--ink);margin-top:5px;letter-spacing:-.02em;
  font-variant-numeric:tabular-nums;}
.kpi-n{font-size:11px;color:var(--faint);margin-top:1px;}
.kpi-v.pos{color:var(--green2);} .kpi-v.neg{color:var(--red);}

.panel{background:var(--surface);border:1px solid var(--line);border-radius:13px;
  padding:18px 20px;margin-bottom:14px;}
.panel-h{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.09em;
  color:var(--muted);margin-bottom:13px;padding-bottom:9px;border-bottom:1px solid var(--line2);}

.verdict{border-radius:13px;padding:17px 20px;margin-bottom:14px;display:flex;
  align-items:center;justify-content:space-between;gap:18px;}
.v-BUY{background:var(--greenbg);border:1px solid #C9E2D1;}
.v-NEGOTIATE{background:var(--amberbg);border:1px solid #F0DCBB;}
.v-PASS{background:var(--redbg);border:1px solid #EFCFCD;}
.v-SETCEILING{background:var(--bluebg);border:1px solid #CCDFEA;}
.v-tag{font-family:'Fraunces',serif;font-size:27px;font-weight:700;letter-spacing:-.02em;line-height:1;}
.v-BUY .v-tag{color:var(--green);} .v-NEGOTIATE .v-tag{color:var(--amber);}
.v-PASS .v-tag{color:var(--red);} .v-SETCEILING .v-tag{color:var(--blue);}
.v-why{font-size:13px;color:var(--ink2);margin-top:5px;}
.v-right{text-align:right;flex-shrink:0;}
.v-big{font-size:25px;font-weight:700;color:var(--ink);letter-spacing:-.02em;font-variant-numeric:tabular-nums;}
.v-sm{font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;font-weight:600;}

.spec{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--line2);font-size:13px;}
.spec:last-child{border:none;}
.spec-k{color:var(--muted);} .spec-v{color:var(--ink);font-weight:500;text-align:right;}

.waterfall{display:flex;align-items:flex-end;gap:3px;height:74px;margin:6px 0 10px;}
.wf{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:4px;}
.wf-bar{width:100%;border-radius:4px 4px 0 0;}
.wf-l{font-size:9px;color:var(--muted);text-align:center;line-height:1.2;}
.wf-v{font-size:10.5px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums;}

.deal{background:var(--surface);border:1px solid var(--line);border-radius:11px;
  padding:13px 15px;margin-bottom:8px;transition:.12s;}
.deal:hover{border-color:#C9D3CB;box-shadow:0 2px 10px rgba(20,32,28,.05);}
.deal-t{display:flex;justify-content:space-between;gap:14px;align-items:baseline;}
.deal-n{font-size:14px;font-weight:600;color:var(--ink);}
.deal-p{font-size:16px;font-weight:700;color:var(--ink);white-space:nowrap;font-variant-numeric:tabular-nums;}
.deal-m{font-size:11.5px;color:var(--muted);margin-top:6px;display:flex;align-items:center;
  gap:9px;flex-wrap:wrap;}
.deal-w{font-size:12px;color:var(--ink2);margin-top:6px;font-style:italic;}

.bar{height:4px;background:var(--line2);border-radius:2px;overflow:hidden;width:54px;display:inline-block;
  vertical-align:middle;}
.bar>span{display:block;height:100%;background:var(--green2);}

.tag{display:inline-block;padding:2.5px 8px;border-radius:5px;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:.05em;}
.t-g{background:var(--greenbg);color:var(--green);}
.t-a{background:var(--amberbg);color:var(--amber);}
.t-r{background:var(--redbg);color:var(--red);}
.t-b{background:var(--bluebg);color:var(--blue);}
.t-n{background:var(--line2);color:var(--ink2);}

.comp{padding:11px 0;border-bottom:1px solid var(--line2);}
.comp:last-child{border:none;}
.comp-t{display:flex;justify-content:space-between;gap:12px;align-items:baseline;}
.comp-n{font-size:12.5px;color:var(--ink);font-weight:500;}
.comp-p{font-size:13.5px;font-weight:700;color:var(--ink);white-space:nowrap;font-variant-numeric:tabular-nums;}
.comp-m{font-size:10.5px;color:var(--muted);margin-top:4px;}
.comp-m a{color:var(--green2);text-decoration:none;} .comp-m a:hover{text-decoration:underline;}

.msg{background:#F7F9F6;border:1px solid var(--line);border-left:3px solid var(--green2);
  border-radius:8px;padding:12px 14px;font-size:13px;color:var(--ink2);line-height:1.6;white-space:pre-wrap;}
.empty{text-align:center;padding:46px 20px;color:var(--muted);}
.empty-i{font-size:30px;margin-bottom:10px;opacity:.5;}
.empty-t{font-size:14px;font-weight:600;color:var(--ink2);}
.empty-s{font-size:12.5px;margin-top:5px;}
.hint{font-size:11.5px;color:var(--faint);line-height:1.55;}
div[data-testid="stDataFrame"]{border:1px solid var(--line)!important;border-radius:10px!important;}
</style>
""", unsafe_allow_html=True)

# ============================================================ helpers
def eur(v, dash="—"):
    if v is None:
        return dash
    return "€{:,.0f}".format(float(v)).replace(",", ".")

def api_key():
    try:
        return st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    except Exception:
        return os.getenv("OPENAI_API_KEY", "")

def kpi(label, value, note="", cls=""):
    return (f'<div class="kpi"><div class="kpi-l">{label}</div>'
            f'<div class="kpi-v {cls}">{value}</div><div class="kpi-n">{note}</div></div>')

def spec(k, v):
    return f'<div class="spec"><span class="spec-k">{k}</span><span class="spec-v">{v}</span></div>'

def liq_tag(l):
    return {"high": "t-g", "medium": "t-a", "low": "t-r"}.get(str(l).lower(), "t-n")

@st.cache_data(ttl=1800, show_spinner=False)
def c_fetch(u): return E.fetch_listing(u)

@st.cache_data(ttl=900, show_spinner=False)
def c_search(q, lo, hi, lim): return E.search_listings(q, lo, hi, lim)

@st.cache_data(ttl=900, show_spinner=False)
def c_search_multi(q, lo, hi, lim, markets_tuple):
    return E.search_markets(q, lo, hi, max(1, lim // max(1, len(markets_tuple))), list(markets_tuple))

@st.cache_data(ttl=3600, show_spinner=False)
def c_identify(k, x): return E.identify(k, x)

@st.cache_data(ttl=3600, show_spinner=False)
def c_value(k, eq, loc): return E.value(k, eq, loc)

def waterfall(likely, costs, buffer, target, ceiling):
    segs = [("Resale", likely, "#2E6B50"), ("Costs", -costs, "#B57324"),
            ("Buffer", -buffer, "#A93F3C"), ("Profit", -target, "#2C5A78"),
            ("Max buy", ceiling, "#1E4B3B")]
    mx = max(likely, 1)
    h = "".join(
        f'<div class="wf"><div class="wf-v">{eur(abs(v))}</div>'
        f'<div class="wf-bar" style="height:{max(abs(v)/mx*100,3):.0f}%;background:{c};"></div>'
        f'<div class="wf-l">{n}</div></div>' for n, v, c in segs)
    return f'<div class="waterfall">{h}</div>'

# ============================================================ topbar
K = DB.kpis()
st.markdown(f"""
<div class="topbar">
  <div class="logo"><div class="logo-m">⛳</div>
    <div><div class="logo-t">Flip It</div>
    <div class="logo-s">Marketplace intelligence · Belgium & Netherlands</div></div></div>
  <div style="text-align:right">
    <div class="kpi-l">Realised profit</div>
    <div style="font-size:19px;font-weight:700;color:{'#2E6B50' if K['realized']>=0 else '#A93F3C'};
      font-variant-numeric:tabular-nums;">{eur(K['realized'])}</div>
  </div>
</div>""", unsafe_allow_html=True)

# ============================================================ sidebar
with st.sidebar:
    st.markdown("**Deal parameters**")
    target_profit = st.number_input("Target profit (€)", 0.0, 2000.0, 75.0, 5.0)
    min_roi = st.number_input("Minimum ROI (%)", 0.0, 300.0, 25.0, 5.0)
    costs = st.number_input("Costs per flip (€)", 0.0, 500.0, 35.0, 5.0)
    st.markdown('<div class="hint">Shipping, packaging, travel and selling fees. '
                'Use 0 for local pickup in Antwerp.</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("**Max buy price**")
    st.markdown('<div class="hint">Likely resale − costs − risk buffer − target profit.<br><br>'
                'The risk buffer widens when market evidence is thin or the item is illiquid, '
                'so uncertain deals need a bigger discount.</div>', unsafe_allow_html=True)
    st.divider()
    if api_key():
        st.markdown('<span class="tag t-g">AI connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="tag t-r">No API key</span>', unsafe_allow_html=True)
        st.caption("Add OPENAI_API_KEY in Streamlit Secrets.")

T1, T2, T3, T4 = st.tabs(["Analyse", "Market screen", "Pipeline", "Performance"])

# ============================================================ TAB 1 · ANALYSE
with T1:
    c1, c2 = st.columns([5, 1])
    url = c1.text_input("Listing URL", placeholder="https://www.2dehands.be/v/sport-en-fitness/golf/...",
                        label_visibility="collapsed", key="an_url")
    run = c2.button("Analyse", type="primary", use_container_width=True)

    if run and not url.strip():
        st.warning("Paste a 2dehands listing link first.")
    elif run:
        try:
            with st.spinner("Reading listing…"):
                x = c_fetch(url.strip())
            with st.spinner("Identifying equipment…"):
                eq = c_identify(api_key(), x)

            if not eq["is_golf_equipment"]:
                st.error("This does not look like sellable golf equipment.")
                st.stop()

            with st.spinner("Researching the market…"):
                v = c_value(api_key(), eq, x["location"])

            price = float(eq["price_eur"])
            ec = E.economics(v, price, costs, target_profit, min_roi)
            st.session_state.an = {"x": x, "eq": eq, "v": v, "ec": ec, "price": price}
        except ValueError as err:
            st.warning(str(err))
        except requests.HTTPError as err:
            st.error(f"A marketplace could not be reached ({getattr(err.response,'status_code','?')}).")
        except Exception as err:
            st.error(f"{type(err).__name__}: {err}")

    A = st.session_state.get("an")
    if not A:
        st.markdown('<div class="empty"><div class="empty-i">⛳</div>'
                    '<div class="empty-t">Paste a listing to value it</div>'
                    '<div class="empty-s">Flip It identifies the equipment, researches live European '
                    'market evidence and returns a disciplined maximum buy price.</div></div>',
                    unsafe_allow_html=True)
    else:
        x, eq, v, ec, price = A["x"], A["eq"], A["v"], A["ec"], A["price"]
        vc = ec["verdict"].replace(" ", "")

        st.markdown(f"""<div class="verdict v-{vc}">
          <div><div class="v-tag">{ec['verdict']}</div><div class="v-why">{ec['why']}</div></div>
          <div class="v-right"><div class="v-big">{eur(ec['ceiling'])}</div>
          <div class="v-sm">Max buy price</div></div></div>""", unsafe_allow_html=True)

        st.markdown('<div class="kpi-row">'
            + kpi("Asking", eur(price) if price else "No bid",
                  x["listing_type"].title() + " listing")
            + kpi("Likely resale", eur(ec["likely"]), f"range {eur(ec['low'])}–{eur(ec['high'])}")
            + kpi("Profit at asking", eur(ec["profit"]) if price else "—",
                  f"ROI {ec['roi']:.0f}%" if price else "no price yet",
                  "pos" if ec["profit"] > 0 else "neg")
            + kpi("Evidence", f"{ec['conf']:.0f}%", f"buffer {eur(ec['buffer'])} ({ec['buf_rate']:.0f}%)")
            + kpi("Liquidity", str(v["liquidity"]).title(), f"~{v['days_to_sell']:.0f} days to sell")
            + '</div>', unsafe_allow_html=True)

        L, R = st.columns([3, 2])

        with L:
            st.markdown('<div class="panel"><div class="panel-h">Equipment</div>'
                + spec("Brand / model", f"{eq['brand']} {eq['model']}")
                + spec("Category", eq["category"])
                + spec("Generation", eq["generation_year"])
                + spec("Specification", eq["specs"])
                + spec("Set", eq["set_composition"])
                + spec("Condition", f"{eq['condition_grade']} — {eq['condition']}")
                + spec("Location", x["location"] or "Not stated")
                + spec("ID confidence", f"{eq['confidence']:.0f}%")
                + '</div>', unsafe_allow_html=True)

            st.markdown(f'<div class="panel"><div class="panel-h">Market evidence '
                        f'· {len(v["comps"])} comparables</div>', unsafe_allow_html=True)
            if v["comps"]:
                rows = ""
                for c in sorted(v["comps"], key=lambda z: -z["match_pct"])[:6]:
                    link = (f'<a href="{c["url"]}" target="_blank">view source ↗</a>'
                            if str(c["url"]).startswith("http") else '<span>no link</span>')
                    rows += (f'<div class="comp"><div class="comp-t">'
                             f'<div class="comp-n">{c["title"]}</div>'
                             f'<div class="comp-p">{eur(c["price_eur"])}</div></div>'
                             f'<div class="comp-m"><span class="tag t-n">{c["market"]}</span> '
                             f'{c["source"]} · {c["kind"]} · {c["match_pct"]:.0f}% match · {link}</div></div>')
                st.markdown(rows, unsafe_allow_html=True)
            else:
                st.markdown('<div class="hint">No verifiable comparables were found. '
                            'Treat this valuation as low confidence.</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with R:
            st.markdown('<div class="panel"><div class="panel-h">How the ceiling is built</div>'
                        + waterfall(ec["likely"], costs, ec["buffer"], target_profit, ec["ceiling"])
                        + f'<div class="hint">{eur(ec["likely"])} resale − {eur(costs)} costs '
                          f'− {eur(ec["buffer"])} risk buffer − {eur(target_profit)} target profit '
                          f'= <b>{eur(ec["ceiling"])}</b></div></div>', unsafe_allow_html=True)

            st.markdown(f'<div class="panel"><div class="panel-h">Assessment</div>'
                        f'<div style="font-size:13px;color:var(--ink2);line-height:1.6">{v["summary"]}</div>'
                        f'<div style="margin-top:11px">{spec("Best channel", v["best_channel"])}'
                        f'{spec("Demand", v["demand_note"])}</div></div>', unsafe_allow_html=True)

            if eq["risks"]:
                st.markdown('<div class="panel"><div class="panel-h">Risks</div>'
                    + "".join(f'<div style="font-size:12.5px;color:var(--ink2);padding:4px 0">'
                              f'<span class="tag t-r">!</span> {r}</div>' for r in eq["risks"])
                    + '</div>', unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        if c1.button("★ Add to pipeline", use_container_width=True):
            aid = DB.log_analysis({
                "url": x["url"], "source": "2dehands", "brand": eq["brand"], "model": eq["model"],
                "category": eq["category"], "specs": eq["specs"], "condition": eq["condition_grade"],
                "listing_type": x["listing_type"], "price": price, "low": ec["low"], "high": ec["high"],
                "likely": ec["likely"], "confidence": ec["conf"], "liquidity": v["liquidity"],
                "buffer": ec["buffer"], "ceiling": ec["ceiling"], "profit": ec["profit"],
                "roi": ec["roi"], "verdict": ec["verdict"], "summary": v["summary"]},
                payload={"eq": eq, "v": v})
            _, new = DB.add_to_pipeline(f"{eq['brand']} {eq['model']}", x["url"],
                                        ec["ceiling"], ec["likely"], aid)
            st.success("Added to pipeline." if new else "Already in your pipeline.")

        if c2.button("✉ Negotiation plan", use_container_width=True):
            with st.spinner("Preparing…"):
                try:
                    st.session_state.neg = E.negotiate(api_key(), eq, ec, price)
                except Exception as err:
                    st.error(str(err))

        with c3.popover("Pre-purchase checklist", use_container_width=True):
            for c in eq["checks"]:
                st.checkbox(c, key=f"chk_{hash(c)}")
            if eq["questions"]:
                st.markdown("**Ask the seller**")
                for q in eq["questions"]:
                    st.markdown(f"- {q}")

        N = st.session_state.get("neg")
        if N:
            st.markdown(f'<div class="panel"><div class="panel-h">Negotiation plan</div>'
                        f'<div class="kpi-row">'
                        f'{kpi("Open at", eur(N["opening_offer_eur"]), "credible first offer")}'
                        f'{kpi("Walk away above", eur(N["walk_away_eur"]), "hard limit")}'
                        f'</div>', unsafe_allow_html=True)
            if N["leverage"]:
                st.markdown("".join(f'<div style="font-size:12.5px;color:var(--ink2);padding:3px 0">'
                                    f'· {l}</div>' for l in N["leverage"]), unsafe_allow_html=True)
            a, b = st.columns(2)
            a.markdown(f'<div class="kpi-l" style="margin-bottom:6px">Dutch</div>'
                       f'<div class="msg">{N["message_nl"]}</div>', unsafe_allow_html=True)
            b.markdown(f'<div class="kpi-l" style="margin-bottom:6px">French</div>'
                       f'<div class="msg">{N["message_fr"]}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================ TAB 2 · SCREEN
with T2:
    PRESETS = {"All golf": "", "Drivers": "driver", "Iron sets": "ijzers set",
               "Putters": "putter", "Wedges": "wedge", "Full bags": "golfset",
               "Premium brands": "titleist ping taylormade callaway mizuno"}
    p = st.radio("Preset", list(PRESETS), horizontal=True, label_visibility="collapsed")

    c1, c2, c3 = st.columns([3, 1, 1])
    q = c1.text_input("Search term", value=PRESETS[p], placeholder="e.g. taylormade stealth")
    lo = c2.number_input("Min €", 0.0, 9999.0, 40.0, 10.0)
    hi = c3.number_input("Max €", 0.0, 9999.0, 700.0, 10.0)
    st.markdown("**Markets**")
    market_labels = ["2dehands / 2ememain 🇧🇪", "Marktplaats 🇳🇱", "eBay Belgium 🇧🇪"]
    selected_labels = st.multiselect("", market_labels, default=market_labels[:2], label_visibility="collapsed")
    market_map = {"2dehands / 2ememain 🇧🇪":"2dehands.be", "Marktplaats 🇳🇱":"marktplaats.nl", "eBay Belgium 🇧🇪":"eBay Belgium"}
    selected_markets = tuple(market_map[x] for x in selected_labels)
    go = st.button("Scan selected markets", type="primary", use_container_width=True)

    if go:
        try:
            with st.spinner("Scanning live listings…"):
                rows, source_errors = c_search_multi(q, lo, hi, 60, selected_markets)
            if not rows:
                st.warning("No listings found. Widen the price range or use a broader term.")
                st.session_state.scr = None
            else:
                with st.spinner(f"Triaging {len(rows)} listings…"):
                    picks = E.screen(api_key(), rows, target_profit, costs, hi)
                st.session_state.scr = {"n": len(rows), "picks": picks, "errors": source_errors, "markets": selected_labels}
        except requests.HTTPError as err:
            st.error(f"A marketplace could not be reached ({getattr(err.response,'status_code','?')}).")
        except Exception as err:
            st.error(f"{type(err).__name__}: {err}")

    S = st.session_state.get("scr")
    if S and S.get("errors"):
        st.info("Some sources were unavailable: " + " · ".join(S["errors"][:3]))
    if S is None:
        st.markdown('<div class="empty"><div class="empty-i">🔍</div>'
                    '<div class="empty-t">Screen the market without a link</div>'
                    '<div class="empty-s">Scans live selected marketplaces and surfaces only those '
                    'plausibly underpriced against your economics.</div></div>', unsafe_allow_html=True)
    elif not S["picks"]:
        st.markdown(f'<div class="empty"><div class="empty-i">○</div>'
                    f'<div class="empty-t">Nothing clears your economics</div>'
                    f'<div class="empty-s">{S["n"]} listings screened, none with a plausible '
                    f'{eur(target_profit)}+ margin. This is a normal and healthy result.</div></div>',
                    unsafe_allow_html=True)
    else:
        picks = sorted(S["picks"], key=lambda z: -z["score"])
        tot = sum(p["est_profit_eur"] for p in picks)
        st.markdown('<div class="kpi-row">'
            + kpi("Screened", S["n"], "live listings")
            + kpi("Opportunities", len(picks), f"{len(picks)/S['n']*100:.0f}% hit rate")
            + kpi("Combined upside", eur(tot), "if all realised", "pos")
            + kpi("Best score", f"{picks[0]['score']:.0f}", picks[0]["item"][:26])
            + '</div>', unsafe_allow_html=True)

        for i, d in enumerate(picks):
            cf = {"high": "t-g", "medium": "t-a", "low": "t-r"}.get(str(d["confidence"]).lower(), "t-n")
            st.markdown(f"""<div class="deal"><div class="deal-t">
              <div class="deal-n">{d['item']}</div><div class="deal-p">{eur(d['price_eur'])}</div></div>
              <div class="deal-m">
                <span class="bar"><span style="width:{min(d['score'],100):.0f}%"></span></span>
                <b>{d['score']:.0f}</b>
                <span class="tag {cf}">{d['confidence']}</span>
                <span class="tag t-n">{d['category']}</span>
                resale {eur(d['est_resale_eur'])} · margin <b style="color:#2E6B50">
                {eur(d['est_profit_eur'])}</b>
                <a href="{d['url']}" target="_blank" style="color:#2E6B50;text-decoration:none">open ↗</a>
              </div><div class="deal-w">{d['why']}</div></div>""", unsafe_allow_html=True)

            a, b = st.columns([1, 6])
            if a.button("Watch", key=f"w{i}", use_container_width=True):
                _, new = DB.add_to_pipeline(d["item"], d["url"], d["price_eur"], d["est_resale_eur"])
                st.toast("Added to pipeline" if new else "Already watching")

        st.markdown('<div class="hint" style="margin-top:14px">Screening is a first-pass filter from '
                    'titles and prices only — no web research. Run promising listings through '
                    '<b>Analyse</b> for verified market evidence before committing.</div>',
                    unsafe_allow_html=True)

# ============================================================ TAB 3 · PIPELINE
with T3:
    st.markdown('<div class="kpi-row">'
        + kpi("Watching", K["watching"], "tracked opportunities")
        + kpi("In stock", K["bought_n"], f"{eur(K['capital'])} tied up")
        + kpi("Sold", K["sold_n"], f"{eur(K['revenue'])} revenue")
        + kpi("Realised", eur(K["realized"]), f"ROI {K['roi']:.0f}%",
              "pos" if K["realized"] >= 0 else "neg")
        + '</div>', unsafe_allow_html=True)

    view = st.radio("Stage", ["Watching", "Bought", "Sold", "All"], horizontal=True,
                    label_visibility="collapsed")
    items = DB.pipeline(None if view == "All" else view.lower())

    if not items:
        st.markdown('<div class="empty"><div class="empty-i">◷</div>'
                    '<div class="empty-t">Nothing here yet</div>'
                    '<div class="empty-s">Add deals from Analyse or Market screen to track them '
                    'from watch through to sale.</div></div>', unsafe_allow_html=True)
    else:
        for it in items:
            stage = {"watching": "t-b", "bought": "t-a", "sold": "t-g", "dropped": "t-n"}[it["status"]]
            with st.container():
                st.markdown(f"""<div class="deal"><div class="deal-t">
                  <div class="deal-n">{it['item']}</div>
                  <div class="deal-p">{eur(it['sold_price'] or it['buy_price'] or it['ceiling'])}</div>
                  </div><div class="deal-m"><span class="tag {stage}">{it['status']}</span>
                  est. resale {eur(it['est_resale'])} · ceiling {eur(it['ceiling'])}
                  <a href="{it['url']}" target="_blank" style="color:#2E6B50;text-decoration:none">open ↗</a>
                  </div></div>""", unsafe_allow_html=True)

                with st.expander("Update"):
                    if it["status"] == "watching":
                        a, b, c = st.columns(3)
                        bp = a.number_input("Bought for (€)", 0.0, 9999.0,
                                            float(it["ceiling"] or 0), 5.0, key=f"bp{it['id']}")
                        bd = b.date_input("Date", value=date.today(), key=f"bd{it['id']}")
                        c.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
                        if c.button("Mark bought", key=f"mb{it['id']}", use_container_width=True):
                            DB.update_pipeline(it["id"], status="bought", buy_price=bp,
                                               buy_date=bd.isoformat())
                            st.rerun()
                        if st.button("Drop", key=f"dr{it['id']}"):
                            DB.update_pipeline(it["id"], status="dropped")
                            st.rerun()
                    elif it["status"] == "bought":
                        a, b, c, d = st.columns(4)
                        sp = a.number_input("Sold for (€)", 0.0, 9999.0,
                                            float(it["est_resale"] or 0), 5.0, key=f"sp{it['id']}")
                        sc = b.number_input("Selling costs (€)", 0.0, 999.0, 0.0, 5.0, key=f"sc{it['id']}")
                        sd = c.date_input("Date", value=date.today(), key=f"sd{it['id']}")
                        d.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
                        if d.button("Mark sold", key=f"ms{it['id']}", use_container_width=True):
                            DB.update_pipeline(it["id"], status="sold", sold_price=sp, costs=sc,
                                               sold_date=sd.isoformat())
                            st.rerun()
                    else:
                        m = (it["sold_price"] or 0) - (it["buy_price"] or 0) - (it["costs"] or 0)
                        st.markdown(f"Bought {eur(it['buy_price'])} → sold {eur(it['sold_price'])} "
                                    f"· **margin {eur(m)}**")
                        if st.button("Delete", key=f"del{it['id']}"):
                            DB.delete_pipeline(it["id"])
                            st.rerun()

# ============================================================ TAB 4 · PERFORMANCE
with T4:
    err = K["est_error"]
    st.markdown('<div class="kpi-row">'
        + kpi("Analyses run", K["analyses"], "listings valued")
        + kpi("Estimate error", f"{err:.0f}%" if err is not None else "—",
              "sold vs predicted", "pos" if (err is not None and err < 15) else "")
        + kpi("Avg hold", f"{K['hold_days']:.0f}d" if K["hold_days"] is not None else "—",
              "buy to sale")
        + kpi("Realised ROI", f"{K['roi']:.0f}%", f"on {eur(K['capital'] + 0)} deployed",
              "pos" if K["roi"] >= 0 else "neg")
        + '</div>', unsafe_allow_html=True)

    st.markdown('<div class="hint">Estimate error is the heart of this tool: it compares what '
                'Flip It predicted an item would sell for against what you actually got. '
                'Under 15% means the valuations are trustworthy. Consistently higher means you should '
                'raise your target profit to compensate.</div>', unsafe_allow_html=True)

    sold = DB.pipeline("sold")
    if sold:
        st.markdown('<div class="panel"><div class="panel-h">Predicted vs realised</div>',
                    unsafe_allow_html=True)
        df = pd.DataFrame([{ "Item": s["item"], "Predicted": s["est_resale"],
                             "Sold": s["sold_price"],
                             "Delta": (s["sold_price"] or 0) - (s["est_resale"] or 0),
                             "Margin": (s["sold_price"] or 0) - (s["buy_price"] or 0) - (s["costs"] or 0)}
                           for s in sold])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)
        if len(df) > 1:
            st.markdown('<div class="panel"><div class="panel-h">Margin by deal</div>',
                        unsafe_allow_html=True)
            st.bar_chart(df.set_index("Item")["Margin"], color="#2E6B50", height=230)
            st.markdown('</div>', unsafe_allow_html=True)

    an = DB.analyses(300)
    if an:
        adf = pd.DataFrame(an)
        st.markdown('<div class="panel"><div class="panel-h">Verdict distribution</div>',
                    unsafe_allow_html=True)
        st.bar_chart(adf["verdict"].value_counts(), color="#1E4B3B", height=200)
        st.markdown('</div>', unsafe_allow_html=True)
        st.download_button("Export analysis log (CSV)",
                           adf.to_csv(index=False).encode(), "flipgolf_analyses.csv",
                           "text/csv")
    else:
        st.markdown('<div class="empty"><div class="empty-i">◔</div>'
                    '<div class="empty-t">No history yet</div>'
                    '<div class="empty-s">Analyse listings and record outcomes to calibrate '
                    'the valuation engine against your real results.</div></div>',
                    unsafe_allow_html=True)
