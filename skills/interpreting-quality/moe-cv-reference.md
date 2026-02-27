# MOE/CV Reference Guide

## Core Formulas

### Standard Error from MOE
```
SE = MOE / 1.645
```
Census Bureau MOE is at 90% confidence level.

### Coefficient of Variation
```
CV = (SE / Estimate) × 100
```

### Converting to 95% confidence
```
MOE_95 = MOE_90 × (1.960 / 1.645)
```

## MOE Sentinel Values

The Census Bureau uses negative values as sentinel codes in MOE fields:

| Value | Meaning | How to display |
|-------|---------|----------------|
| -222222222 | Median falls in upper open-ended interval | "Top bracket ($250,000+)" |
| -333333333 | Median falls in lower open-ended interval | "Bottom bracket" |
| -666666666 | Estimate is a controlled count, no sampling error | "Exact count (no MOE)" |
| -888888888 | Estimate is zero by definition | "Zero (by definition)" |
| -999999999 | Not available | "MOE not available" |

**When you encounter a sentinel**: Do not calculate CV. Display the meaning instead.

## Derived Estimates

### Sum of estimates
```
SE_sum = sqrt(SE_1² + SE_2² + ... + SE_n²)
MOE_sum = SE_sum × 1.645
```

### Proportion (p = X / Y)
```
SE_proportion = sqrt(SE_X² - (p² × SE_Y²)) / Y
```
If radicand is negative (can happen with Census data):
```
SE_proportion = sqrt(SE_X² + (p² × SE_Y²)) / Y
```

### Ratio (R = X / Y where X is NOT a subset of Y)
```
SE_ratio = sqrt(SE_X² + (R² × SE_Y²)) / Y
```

### Product
```
SE_product = sqrt(A² × SE_B² + B² × SE_A²)
```

## Statistical Significance Testing

### Comparing two estimates
```
Z = |Est_1 - Est_2| / sqrt(SE_1² + SE_2²)

Z > 1.645 → Significant at 90% confidence
Z > 1.960 → Significant at 95% confidence
```

### Comparing to zero
```
Z = |Estimate| / SE

Z > 1.645 → Significantly different from zero
```

## Special Cases for PR

### Small municipios
Many municipios in PR have populations under 20,000. ACS 5-Year estimates for these municipios often have high CVs for detailed variables (specific age groups, rare occupations, etc.).

**Mitigation strategies**:
- Aggregate adjacent municipios
- Use broader variable categories
- Use municipio-level instead of barrio-level
- Accept and communicate the uncertainty

### Barrio-level data
Barrios are county subdivisions. Many have very small populations (under 5,000). Expect high CVs for most variables at this level.

**Rule of thumb**: At barrio level, only population counts and broad demographic categories tend to be reliable.

### Zero estimates with non-zero MOE
This can happen when the sample showed zero instances but the MOE reflects sampling uncertainty. Report as "estimated zero (±MOE)" with a note that the true value may be small but non-zero.

## CV Thresholds in Context

The 15%/30% thresholds are guidelines from the Census Bureau. In practice:

| Use case | Acceptable CV |
|----------|--------------|
| Official reporting, policy decisions | < 15% only |
| General analysis, trends | < 30% with caveats |
| Exploratory, directional only | Any, with clear warnings |
| Academic research | Varies by journal standards |

For FPR work, default to the Census Bureau standard (15%/30%) and always disclose quality.
