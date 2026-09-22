import os,re,json
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title='Golf Flip Scanner',page_icon='⛳')
st.title('⛳ Golf Flip Scanner')
st.caption('Paste an individual 2dehands / 2ememain golf listing and get an AI-powered flip analysis.')
TARGET_PROFIT=75.0

def secret(n):
    try:return st.secrets.get(n,os.getenv(n,''))
    except:return os.getenv(n,'')

def euro(v):
    if v is None:return None
    s=re.sub(r'[^\d,.\-]','',str(v))
    if not s:return None
    if ',' in s and '.' in s:s=s.replace('.','').replace(',','.') if s.rfind(',')>s.rfind('.') else s.replace(',','')
    elif ',' in s:s=s.replace(',','.')
    try:return float(s)
    except:return None

def eur(v):return '—' if v is None else '€{:,.0f}'.format(float(v)).replace(',','.')

def fetch(url):
    p=urlparse(url)
    if p.scheme not in ('http','https'):raise ValueError('Please enter a full URL starting with https://')
    if not any(x in p.netloc.lower() for x in ('2dehands.be','2ememain.be')):raise ValueError('Please use a 2dehands.be or 2ememain.be URL.')
    if '/v/' not in p.path.lower():raise ValueError('This looks like a category/search page. Please paste the URL of one individual golf listing.')
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (compatible; GolfFlipScanner/0.3)','Accept-Language':'nl-BE,nl;q=0.9,en;q=0.8'},timeout=20);r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser');title='';desc='';prices=[]
    t=soup.find('meta',property='og:title')
    if t:title=t.get('content','').strip()
    if not title and soup.title:title=soup.title.get_text(' ',strip=True)
    t=soup.find('meta',property='og:description')
    if t:desc=t.get('content','').strip()
    for t in soup.find_all('script',type='application/ld+json'):
        try:d=json.loads(t.string or t.get_text())
        except:continue
        for o in (d if isinstance(d,list) else [d]):
            if isinstance(o,dict):
                title=title or str(o.get('name',''));desc=desc or str(o.get('description',''))
                offers=o.get('offers',[]);offers=offers if isinstance(offers,list) else [offers]
                for q in offers:
                    if isinstance(q,dict):
                        p=euro(q.get('price'))
                        if p and p>0:prices.append(p)
    text=soup.get_text('\n',strip=True)
    for m in re.findall(r'(?:€\s*|EUR\s*)(\d[\d.\s]*(?:,\d{1,2})?)',text,re.I):
        p=euro(m)
        if p and p>=5:prices.append(p)
    return {'url':url,'title':title,'description':desc,'prices':list(dict.fromkeys(prices))[:30],'text':text[:16000]}

def analyze(x):
    key=secret('OPENAI_API_KEY')
    if not key:raise RuntimeError('OPENAI_API_KEY is not configured in Streamlit Secrets.')
    eq={'type':'object','properties':{k:{'type':'string'} for k in ['brand','model','category','generation','set_composition','shaft','flex','loft','handedness','condition','notes']},'required':['brand','model','category','generation','set_composition','shaft','flex','loft','handedness','condition','notes'],'additionalProperties':False}
    schema={'type':'object','properties':{
      'equipment':eq,'identification_confidence':{'type':'number'},'asking_price_eur':{'type':'number'},
      'estimated_resale_low_eur':{'type':'number'},'estimated_resale_high_eur':{'type':'number'},'conservative_resale_eur':{'type':'number'},
      'estimated_costs_eur':{'type':'number'},'risk_buffer_eur':{'type':'number'},'liquidity':{'type':'string'},'key_reason':{'type':'string'},
      'risks':{'type':'array','items':{'type':'string'}},'missing_information':{'type':'array','items':{'type':'string'}},'valuation_note':{'type':'string'}},
      'required':['equipment','identification_confidence','asking_price_eur','estimated_resale_low_eur','estimated_resale_high_eur','conservative_resale_eur','estimated_costs_eur','risk_buffer_eur','liquidity','key_reason','risks','missing_information','valuation_note'],'additionalProperties':False}
    prompt='''You are a conservative used-golf resale analyst. Identify the equipment and create an INITIAL valuation. Never invent specifications; use Unknown. asking_price_eur MUST be the actual asking price of this individual listing. Page prices may be unrelated. If actual asking price cannot be established, use 0 and explain. Without comparable market data, call valuation an initial estimate. identification_confidence is 0-100.\n\nURL: %s\nTITLE: %s\nPRICE CANDIDATES: %s\nDESCRIPTION: %s\nPAGE TEXT: %s'''%(x['url'],x['title'],x['prices'],x['description'],x['text'])
    c=OpenAI(api_key=key)
    r=c.responses.create(model='gpt-5.6-luna',input=prompt,text={'format':{'type':'json_schema','name':'golf_flip_analysis','schema':schema,'strict':True}})
    return json.loads(r.output_text)

url=st.text_input('2dehands listing URL',placeholder='https://www.2dehands.be/v/sport-en-fitness/golf/...')
if st.button('Analyze deal',type='primary',use_container_width=True):
    try:
        if not url.strip():raise ValueError('Paste an individual listing URL first.')
        with st.spinner('Retrieving listing…'):x=fetch(url.strip())
        with st.expander('Listing retrieved',expanded=True):
            st.write('**Title:**',x['title'] or 'Not detected');st.write('**Detected price candidates:**',[eur(v) for v in x['prices']]);st.write('**Description:**',x['description'] or 'Not detected')
        with st.spinner('AI is identifying the equipment…'):r=analyze(x)
        ask=float(r['asking_price_eur'])
        if ask<=0:st.error('The app could not reliably determine the listing asking price yet.');st.stop()
        resale=float(r['conservative_resale_eur']);costs=max(0,float(r['estimated_costs_eur']));risk=max(0,float(r['risk_buffer_eur']))
        maxbuy=max(0,resale-costs-risk-TARGET_PROFIT);profit=resale-costs-risk-ask;roi=profit/ask*100
        decision='BUY' if ask<=maxbuy else ('NEGOTIATE' if ask<=maxbuy*1.1 else 'PASS');offer=min(maxbuy,ask*.9)
        st.divider();st.subheader('⛳ Flip Analysis');a,b,c=st.columns(3);a.metric('Asking',eur(ask));b.metric('Conservative resale',eur(resale));c.metric('Maximum buy',eur(maxbuy));a,b,c=st.columns(3);a.metric('Expected profit',eur(profit));b.metric('ROI',f'{roi:.0f}%');c.metric('Confidence',f"{float(r['identification_confidence']):.0f}%")
        st.markdown('## %s %s'%({'BUY':'🟢','NEGOTIATE':'🟠','PASS':'🔴'}[decision],decision));st.write(r['key_reason']);st.write('**Suggested offer:**',eur(offer));st.write('**Liquidity:**',r['liquidity']);st.write('**Equipment identified**');st.json(r['equipment']);st.write('**Initial estimated resale range:**',f"{eur(r['estimated_resale_low_eur'])}–{eur(r['estimated_resale_high_eur'])}");st.caption(r['valuation_note'])
        with st.expander('Risks and missing information'):
            for v in r['risks']:st.write('•',v)
            for v in r['missing_information']:st.write('• Missing:',v)
        st.info('V0.3 fixes the structured AI output and rejects category pages. Live comparable-price research is next.')
    except ValueError as e:st.warning(str(e))
    except requests.HTTPError as e:st.error(f'2dehands could not be retrieved ({e.response.status_code}).')
    except Exception as e:st.error(str(e))
