# Flip It — Marketplace Intelligence

Flip It scans selected second-hand marketplaces and surfaces potentially underpriced golf equipment.

## V0.7
- 2dehands / 2ememain connector
- Marktplaats connector
- optional eBay Belgium Browse API connector
- normalized listing format across markets
- multi-market screening from one search
- existing listing analysis and valuation workflow retained

### Optional eBay credentials
Add these Streamlit secrets if you want the eBay connector enabled:
- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

Without them, eBay simply reports as unavailable; the other connectors continue to work.

## Important
The marketplace connectors are a prototype. Before commercial deployment, confirm marketplace API access, terms, rate limits and any required approvals. Prefer official APIs over scraping where available.
