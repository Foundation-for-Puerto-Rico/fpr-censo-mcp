# Geographic Hierarchy of Puerto Rico in the Census API

## FIPS Structure

Puerto Rico's state FIPS code is `72`. All geographic codes are nested under this.

## Levels

### State (Puerto Rico)
- **Census term**: `state`
- **FIPS**: `72`
- **API for clause**: `state:72`
- **Population**: ~3.2M (2022 ACS)

### Municipio (County equivalent)
- **Census term**: `county`
- **FIPS range**: `001` to `153` (odd numbers only, 78 total)
- **API for clause**: `county:{FIPS}` with `in state:72`
- **All municipios**: `county:*` with `in state:72`
- **Data file**: `data/municipios_pr.json`

### Barrio (County subdivision)
- **Census term**: `county subdivision`
- **API for clause**: `county subdivision:{FIPS}` with `in state:72+county:{muni_fips}`
- **All barrios in a municipio**: `county subdivision:*` with `in state:72+county:{muni_fips}`
- **Data file**: `data/barrios_pr.json`

### Census Tract
- **Census term**: `tract`
- **API for clause**: `tract:{code}` with `in state:72+county:{muni_fips}`
- **All tracts in a municipio**: `tract:*` with `in state:72+county:{muni_fips}`

### Block Group
- **Census term**: `block group`
- **API for clause**: `block group:{code}` with `in state:72+county:{muni_fips}+tract:{tract_code}`
- **Finest level in ACS 5-Year**

### Block
- **Census term**: `block`
- **Only available in Decennial Census** (dec/pl)

## Common API Patterns

```
# All municipios
for=county:*&in=state:72

# Specific municipio (Vega Baja = 145)
for=county:145&in=state:72

# All barrios in a municipio
for=county+subdivision:*&in=state:72+county:145

# All tracts in a municipio
for=tract:*&in=state:72+county:145

# Puerto Rico total
for=state:72
```

## Name Matching

The MCP server handles name resolution automatically. Users can type:
- "Vega Baja" → resolves to county:145
- "Bayamón" → resolves to county:021
- "San Juan" → resolves to county:127

For barrios, specify the municipio context:
- "barrios de Vega Baja" → all county subdivisions in county:145
