# ADR-004 — Estrategia progresiva de Machine Learning

**Fecha:** 2026-07-02

**Estado:** Aceptado

**Proyecto:** NeuroFin AI Platform

---

# Contexto

NeuroFin AI Platform tiene como objetivo aplicar inteligencia artificial y análisis financiero para generar predicciones, indicadores y explicaciones útiles.

Sin embargo, los mercados financieros son complejos, ruidosos y difíciles de predecir. Por ello, el proyecto no debe iniciar directamente con modelos avanzados sin antes establecer líneas base, métricas y contratos claros.

El MVP necesita ser comprensible para reclutadores y defendible técnicamente. La evolución futura puede incorporar modelos más sofisticados conforme la plataforma madure.

---

# Decisión

Se adopta una estrategia progresiva de Machine Learning.

El proyecto iniciará con un modelo baseline sencillo y evolucionará hacia modelos estadísticos, Machine Learning clásico, Deep Learning e IA generativa.

El modelo inicial será un predictor simple basado en promedio móvil o media histórica, implementado detrás de un contrato de dominio.

---

# Justificación

Una estrategia progresiva permite:

* Validar la arquitectura antes de complejizar el modelo.
* Tener una API funcional desde el inicio.
* Construir pruebas simples.
* Comparar modelos futuros contra una línea base.
* Evitar promesas exageradas de predicción financiera.
* Mantener una narrativa profesional y realista.

---

# Fases de evolución

## Fase 1 — Baseline

Modelo:

* Media histórica.
* Promedio móvil simple.

Objetivo:

* Validar el flujo completo request → caso de uso → modelo → respuesta.

Estado:

✅ MVP inicial.

---

## Fase 2 — Modelos estadísticos

Modelos candidatos:

* Regresión lineal.
* Suavizamiento exponencial.
* ARIMA.
* Prophet.

Objetivo:

* Mejorar capacidad predictiva manteniendo interpretabilidad.

Estado:

🟡 MVP avanzado.

---

## Fase 3 — Machine Learning clásico

Modelos candidatos:

* Random Forest.
* Gradient Boosting.
* XGBoost.
* LightGBM.
* Support Vector Regression.

Objetivo:

* Capturar relaciones no lineales.

Estado:

🔵 Evolución profesional.

---

## Fase 4 — Deep Learning

Modelos candidatos:

* LSTM.
* GRU.
* Transformers para series temporales.
* Temporal Fusion Transformer.

Objetivo:

* Modelar dependencias temporales complejas.

Estado:

🔵 Enterprise / investigación avanzada.

---

## Fase 5 — IA generativa

Tecnologías candidatas:

* Azure OpenAI.
* Azure AI Foundry.
* Semantic Kernel.

Objetivo:

* Explicar resultados en lenguaje natural.
* Generar reportes.
* Crear asistente financiero educativo.

Estado:

🔵 SaaS avanzado.

---

# Regla arquitectónica

Los modelos predictivos deben implementarse detrás de contratos.

Contrato conceptual:

```text
ForecastService
  └── predict(input) -> ForecastResult
```

La API no debe depender de un modelo concreto.

Esto permitirá sustituir:

```text
SimpleMovingAverageForecaster
```

por:

```text
LinearRegressionForecaster
ArimaForecaster
XGBoostForecaster
LstmForecaster
```

sin cambiar el contrato principal del caso de uso.

---

# Métricas futuras

Para evaluar modelos futuros se podrán usar:

* MAE.
* RMSE.
* MAPE.
* Directional Accuracy.
* Backtesting.
* Comparación contra baseline.

Ningún modelo deberá considerarse superior sin medición objetiva.

---

# Riesgos

## Riesgo de sobrepromesa

La predicción financiera no garantiza resultados de inversión.

Mitigación:

* Presentar el proyecto como educativo, analítico y experimental.
* Evitar lenguaje de recomendación financiera definitiva.

---

## Riesgo de sobreajuste

Modelos complejos pueden ajustarse demasiado a datos históricos.

Mitigación:

* Separar entrenamiento y prueba.
* Usar backtesting.
* Comparar contra baseline.

---

## Riesgo de baja calidad de datos

Datos incompletos o inconsistentes afectan los modelos.

Mitigación:

* Validar datos.
* Registrar fuente.
* Normalizar series.
* Manejar valores faltantes.

---

# Estado en el MVP

El backend actual implementa:

```text
SimpleMovingAverageForecaster
```

Este modelo calcula la media de los valores históricos y proyecta ese valor para el horizonte solicitado.

Aunque es simple, cumple un propósito arquitectónico importante:

* Demuestra el contrato de predicción.
* Permite probar el flujo completo.
* Sirve como línea base.
* Mantiene el MVP entendible.

---

# Criterio de éxito

La estrategia será exitosa si:

* El MVP funciona sin complejidad innecesaria.
* Cada modelo futuro puede compararse contra baseline.
* La API no cambia innecesariamente al cambiar el modelo.
* La documentación explica claramente límites y alcance.
* El proyecto comunica madurez técnica y responsabilidad.

---

# Conclusión

NeuroFin AI Platform no debe iniciar intentando predecir mercados con modelos complejos sin fundamento. Debe iniciar con una arquitectura sólida, un baseline funcional y una ruta clara de evolución. Esta decisión fortalece tanto el MVP para portafolio como la futura plataforma SaaS.
