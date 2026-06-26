# PubMed Database

Search PubMed for scientific literature, fetch abstracts, and link to biological databases.

## Quick Start
```python
import requests, json

def search_pubmed(query, max_results=5):
    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
    r = requests.get(f'{base}esearch.fcgi', params={'db': 'pubmed', 'term': query, 'retmax': max_results, 'format': 'json'})
    ids = r.json().get('esearchresult', {}).get('idlist', [])
    if not ids: return []
    r2 = requests.get(f'{base}esummary.fcgi', params={'db': 'pubmed', 'id': ','.join(ids), 'format': 'json'})
    results = r2.json().get('result', {})
    return [{'pmid': uid, 'title': results[uid].get('title', ''), 'source': results[uid].get('source', '')} for uid in ids]

# Example
for paper in search_pubmed('CRISPR gene therapy 2025'):
    print(f"{paper['pmid']}: {paper['title']}")
```

## Functions
- `search_pubmed` - Free-text query
- `fetch_abstracts` - Get full abstracts by PMIDs
- `find_linked_data` - Cross-reference with gene/protein databases
