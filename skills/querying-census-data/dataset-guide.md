# Census Datasets Guide for Puerto Rico

## ACS 5-Year Estimates (`acs/acs5`)

**The default dataset for most analyses.**

- **Years available**: 2009-2022
- **Coverage**: All geographic levels including block groups
- **Sample**: Aggregates 5 years of survey data for reliability
- **Use when**: You need data for small areas (barrios, tracts) or rare populations
- **Tradeoff**: Less current (2022 data = surveys from 2018-2022)

### Key variable tables
| Prefix | Topic |
|--------|-------|
| B01 | Age, sex, population |
| B02 | Race |
| B03 | Hispanic origin |
| B05 | Citizenship, nativity |
| B06 | Place of birth |
| B07-B08 | Migration, commuting |
| B09-B10 | Children, grandparents |
| B11 | Household type |
| B12 | Marital status |
| B15 | Education |
| B17 | Poverty |
| B19 | Income |
| B23 | Employment |
| B25 | Housing |
| B27 | Health insurance |

## ACS 1-Year Estimates (`acs/acs1`)

- **Years available**: 2005-2022 (gap in 2020 due to COVID)
- **Coverage**: Only areas with 65,000+ population
- **In PR**: Only ~15 largest municipios + PR total
- **Use when**: You need the most recent data for a large municipio
- **Tradeoff**: Not available for small municipios or sub-municipio areas

### Municipios available in ACS 1-Year (approximate)
Bayamón, Caguas, Carolina, Guaynabo, Humacao, Mayagüez, Ponce, San Juan, Toa Baja, Trujillo Alto, Arecibo, Aguadilla (varies by year)

## Decennial Census (`dec/pl`)

- **Years**: 2000, 2010, 2020
- **Coverage**: All levels down to block
- **Variables**: Limited — mainly total population, race, Hispanic origin, housing units, group quarters
- **Use when**: You need exact population counts (not estimates) or block-level data
- **Tradeoff**: Only every 10 years, very limited variables

## Population Estimates (`pep/population`)

- **Years**: Annual between decennial censuses
- **Coverage**: State and county (municipio) only
- **Variables**: Total population, components of change (births, deaths, migration)
- **Use when**: You need the most current population estimate for a municipio
- **Tradeoff**: Municipio level only, limited variables
