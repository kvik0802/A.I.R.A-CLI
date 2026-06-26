# gnomAD Database

Query population allele frequencies and gene constraint metrics from gnomAD.

## Usage
```python
import requests, json

gene = 'BRCA1'
r = requests.get(f'https://gnomad.broadinstitute.org/api/', json={
    'query': '{gene(gene: "' + gene + '") {name symbol constraint {mis z syn z lof z}}}'
})
data = r.json().get('data', {}).get('gene', {})
constraint = data.get('constraint', {})
print(f"{data.get('symbol')}: missense Z={constraint.get('mis', 'N/A')}, LoF Z={constraint.get('lof', 'N/A')}")

# Population frequencies
r2 = requests.get(f'https://gnomad.broadinstitute.org/api/', json={
    'query': '{gene(gene: "' + gene + '") {populations {id ac an af}}}'
})
pops = r2.json().get('data', {}).get('gene', {}).get('populations', [])
for p in pops:
    print(f"  {p['id']}: AF={p.get('af', 'N/A')}")
```

## Data Available
- Allele frequencies by population
- Gene constraint (missense Z, LoF Z)
- Variant co-occurrence
- Region-level constraint
