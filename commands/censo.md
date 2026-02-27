---
name: censo
description: Consulta datos del Census Bureau para Puerto Rico
arguments:
  - name: query
    description: "Pregunta o consulta en lenguaje natural (ej: 'población de Bayamón', 'comparar ingreso Guaynabo vs Caguas')"
    required: true
---

El usuario quiere datos del Census Bureau para Puerto Rico: `$ARGUMENTS.query`

Usa la skill `querying-census-data` para determinar qué herramienta del MCP usar y cómo construir la consulta. Luego usa la skill `interpreting-quality` para evaluar la confiabilidad de los resultados antes de presentarlos.

## Routing de la consulta

Analiza la consulta del usuario y determina qué tool del MCP Census es el más apropiado:

| Intención del usuario | Tool MCP a usar |
|----------------------|-----------------|
| Dato puntual de un lugar (ej: "población de Vega Baja") | `censo_consultar` o `censo_perfil` |
| Perfil completo de un lugar (ej: "perfil económico de Manatí") | `censo_perfil` con perfil específico |
| Resumen general de un lugar | `censo_perfil` sin perfil (resumen ejecutivo) |
| Comparar lugares (ej: "comparar Guaynabo vs Caguas") | `censo_comparar` |
| Tendencia histórica (ej: "población de PR desde 2010") | `censo_serie_temporal` |
| Contextualizar un dato (ej: "cómo se compara Bayamón con PR") | `censo_contexto` |
| Buscar qué variables existen (ej: "qué datos hay de vivienda") | `censo_buscar_variables` |
| Qué municipios/barrios hay | `censo_listar_municipios` o `censo_listar_barrios` |

## Protocolo

1. Si es la primera consulta de la sesión, llama `censo_estado` para verificar configuración.
2. Ejecuta el tool MCP apropiado según el routing.
3. Aplica la skill `interpreting-quality` a los resultados para evaluar confiabilidad.
4. Presenta los resultados al usuario con contexto en español.
