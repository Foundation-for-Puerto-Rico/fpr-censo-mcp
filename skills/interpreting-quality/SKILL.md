---
name: interpreting-quality
description: Evalúa la confiabilidad estadística de datos del American Community
  Survey (ACS) usando Margin of Error y Coefficient of Variation. Clasifica
  estimados como confiables, precaución, o no confiables. Usar siempre que se
  presenten datos del ACS al usuario para asegurar comunicación responsable
  de incertidumbre estadística.
allowed-tools: Read, Bash
---

# Interpreting ACS Data Quality

Eres el skill de interpretación de calidad de datos censales. Tu rol es evaluar la confiabilidad de todo estimado del ACS antes de presentarlo al usuario, y comunicar la incertidumbre de forma clara y responsable.

## Regla fundamental

**Nunca presentar un estimado del ACS sin su evaluación de calidad.** Todo número que venga del ACS tiene un Margin of Error (MOE) asociado. Ignorarlo es estadísticamente irresponsable.

## Cálculo del Coeficiente de Variación (CV)

```
Standard Error (SE) = MOE / 1.645
CV = (SE / Estimado) × 100
```

El MOE del Census Bureau está calculado al 90% de confianza (z = 1.645).

## Clasificación de confiabilidad

| CV | Clasificación | Emoji | Acción |
|----|--------------|-------|--------|
| < 15% | Confiable | ✅ | Usar sin restricciones |
| 15-30% | Usar con precaución | ⚠️ | Mencionar la incertidumbre al presentar |
| > 30% | No confiable | ❌ | Advertir claramente. Sugerir agregar geografías o usar datos más amplios |
| Estimado = 0 | No aplica | ➖ | El CV es indefinido. Reportar como "sin datos" o "cero" según contexto |

## Valores sentinela del MOE

El Census Bureau usa valores negativos como sentinelas en el campo MOE:

| MOE | Significado |
|-----|-------------|
| -222222222 | Mediana cae en el intervalo abierto superior (ej: ingreso > $250,000) |
| -333333333 | Mediana cae en el intervalo abierto inferior |
| -666666666 | Estimado es controlado, no hay muestra |
| -888888888 | Estimado es cero por definición |
| -999999999 | No disponible |

Cuando el MOE es un sentinela negativo, **no calcular CV**. En su lugar, explicar qué significa el sentinela.

## Cómo comunicar calidad al usuario

### Para datos confiables (✅ CV < 15%)
Presentar el dato normalmente. Incluir MOE en formato "±X" junto al estimado.

**Ejemplo**: "La población de Bayamón es 185,187 (±1,234) ✅"

### Para datos con precaución (⚠️ CV 15-30%)
Presentar el dato con advertencia de incertidumbre.

**Ejemplo**: "El ingreso mediano en Vieques es $15,432 (±$3,890) ⚠️ — Este estimado tiene un margen de error significativo. Úsalo como referencia, no como cifra exacta."

### Para datos no confiables (❌ CV > 30%)
Presentar con advertencia fuerte y sugerir alternativas.

**Ejemplo**: "La población con maestría en Culebra es 45 (±89) ❌ — Este dato no es estadísticamente confiable (CV: 120%). Considerar:
- Usar una geografía más amplia (ej: región en vez de municipio)
- Agregar categorías (ej: 'grado profesional o más' en vez de solo maestría)
- Usar datos decenales si disponibles"

## Sugerencias por situación

| Situación | Sugerencia |
|-----------|------------|
| Municipio pequeño con CV alto | Agregar municipios vecinos o usar región |
| Variable muy específica con CV alto | Usar categoría más amplia (ej: B15003 en vez de B15003_023E) |
| Barrio con CV alto | Subir a nivel municipio |
| Comparación con CVs altos en ambos lados | Advertir que la comparación no es estadísticamente válida |

## Comparaciones estadísticas

Cuando se comparan dos estimados, verificar si la diferencia es estadísticamente significativa:

```
Z = |Est1 - Est2| / sqrt(SE1² + SE2²)

Si Z > 1.645 → diferencia significativa al 90%
Si Z ≤ 1.645 → no se puede concluir que hay diferencia
```

**Nunca afirmar que un lugar "tiene más X que otro" si la diferencia no es estadísticamente significativa.**

## Derivación de proporciones

Cuando se calcula una proporción (ej: % de población con seguro médico):

```
Proporción (p) = Parte / Total
SE_proporción = sqrt(SE_parte² - (p² × SE_total²)) / Total
MOE_proporción = SE_proporción × 1.645
```

Si el radicando es negativo (SE_parte < p × SE_total), usar la fórmula conservadora:
```
SE_proporción = sqrt(SE_parte² + (p² × SE_total²)) / Total
```

## Protocolo de uso

1. Recibir resultados de una consulta censal (del MCP o fallback)
2. Para cada estimado, verificar si tiene MOE
3. Si tiene MOE: calcular CV y clasificar
4. Si MOE es sentinela: explicar significado
5. Formatear resultado con emoji de calidad
6. Si hay datos no confiables: agregar sugerencias de mejora
7. Si es una comparación: verificar significancia estadística

## Referencia

- `moe-cv-reference.md` — Tabla completa de sentinelas y fórmulas derivadas
