# AlphaFold Database Fetch & Analyze

Fetch protein structures from AlphaFold DB and analyze pLDDT scores.

## Usage
```
python -c "
import requests, json
uniprot_id = 'P68871'  # Example: Beta-globin
url = f'https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}'
r = requests.get(url, headers={'Accept': 'application/json'})
data = r.json()
print(f'Protein: {data[0][\"uniprotDescription\"]}')
print(f'pLDDT: {data[0][\"plddt\"]:.1f}')
print(f'Download: {data[0][\"cifUrl\"]}')
"
```

## Key Functions
- Fetch structure by UniProt ID
- Parse pLDDT confidence scores
- Download CIF/PDB files
- Domain architecture analysis
