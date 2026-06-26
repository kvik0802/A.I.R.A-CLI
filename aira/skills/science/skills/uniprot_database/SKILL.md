# UniProt Database

Fetch protein sequences, functional annotations, and cross-references.

## Usage
```python
import requests, json

def fetch_uniprot(accession):
    r = requests.get(f'https://rest.uniprot.org/uniprotkb/{accession}.json')
    if r.status_code != 200: return None
    data = r.json()
    return {
        'id': data.get('primaryAccession'),
        'name': data.get('uniProtkbId'),
        'protein': data.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value', ''),
        'gene': data.get('genes', [{}])[0].get('geneName', {}).get('value', ''),
        'organism': data.get('organism', {}).get('scientificName', ''),
        'length': data.get('sequence', {}).get('length', 0),
        'function': [c['texts'][0]['value'] for c in data.get('comments', []) if c.get('commentType') == 'FUNCTION'],
    }

# Example
info = fetch_uniprot('P68871')
if info:
    print(f"{info['id']} ({info['gene']}): {info['protein']} - {info['length']}aa")
```

## Available Queries
- Protein sequence retrieval
- Functional annotations (GO terms)
- Cross-references (PDB, AlphaFold, Pfam)
- Variant mapping
