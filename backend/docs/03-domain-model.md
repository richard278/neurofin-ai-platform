# NeuroFin AI Platform

# Documento 03 — Domain Model

**Versión:** 1.0.0

**Estado:** Diseño del Dominio

**Autor:** Richard Milian

**Proyecto:** NeuroFin AI Platform

---

# Propósito

Este documento define el modelo de dominio de NeuroFin AI Platform.

El objetivo es representar los conceptos fundamentales del negocio financiero mediante un lenguaje común (Ubiquitous Language) independiente de cualquier tecnología o framework.

El dominio es el núcleo de la plataforma y debe permanecer estable incluso si cambian FastAPI, Azure, la base de datos o el frontend.

---

# Filosofía del dominio

NeuroFin AI Platform parte de una idea simple: los datos financieros representan conocimiento en potencia.

La plataforma transforma:

Datos

↓

Información

↓

Conocimiento

↓

Predicciones

↓

Apoyo a la toma de decisiones.

---

# Lenguaje Ubicuo (Ubiquitous Language)

Todo el proyecto utilizará la misma terminología.

## Asset

Representa un activo financiero.

Ejemplos:

* Acción
* ETF
* Índice
* Criptomoneda
* Materia prima

Ejemplos reales:

* AAPL
* MSFT
* NVDA
* BTC-USD
* EURUSD

---

## Market Data

Información histórica obtenida desde proveedores financieros.

Incluye:

* Open
* High
* Low
* Close
* Volume

---

## Time Series

Secuencia cronológica de datos financieros.

Constituye la entrada principal para los modelos predictivos.

---

## Technical Indicator

Resultado matemático calculado sobre una serie temporal.

Ejemplos:

* SMA
* EMA
* RSI
* MACD
* ATR
* Bollinger Bands

---

## Forecast

Predicción generada por un modelo.

Una predicción siempre estará asociada a:

* un activo
* un horizonte temporal
* un modelo
* una fecha de generación

---

## Prediction Model

Algoritmo responsable de producir una predicción.

Ejemplos:

* Linear Regression
* Prophet
* XGBoost
* LSTM
* Transformer

---

## Forecast Horizon

Cantidad de períodos futuros que el modelo intentará estimar.

Ejemplos:

* 7 días
* 30 días
* 90 días

---

## Portfolio

Colección de activos administrados por un usuario.

Será incorporado durante la Enterprise Edition.

---

## Risk Profile

Representa la tolerancia al riesgo asociada a un portafolio.

---

## Sentiment Analysis

Resultado del análisis de noticias financieras y opinión del mercado.

---

# Entidades Principales

## Asset

Representa un instrumento financiero.

Atributos:

* id
* symbol
* name
* asset_type
* exchange
* currency

---

## HistoricalPrice

Representa una observación histórica del mercado.

Atributos:

* asset_id
* date
* open
* high
* low
* close
* volume

---

## Forecast

Representa una predicción generada por un modelo.

Atributos:

* forecast_id
* asset_id
* model_id
* created_at
* horizon
* predicted_values

---

## PredictionModel

Describe un algoritmo predictivo.

Atributos:

* model_id
* name
* version
* algorithm
* training_date
* metrics

---

## TechnicalIndicator

Resultado calculado para un activo.

Atributos:

* indicator_id
* asset_id
* indicator_type
* value
* calculated_at

---

# Objetos de Valor (Value Objects)

## Money

Representa un valor monetario.

Propiedades:

* amount
* currency

---

## ForecastPeriod

Representa el horizonte temporal de una predicción.

Ejemplos:

* Daily
* Weekly
* Monthly

---

## Symbol

Representa el identificador único de un activo financiero.

Ejemplos:

* AAPL
* TSLA
* BTC-USD

---

## Percentage

Representa valores porcentuales.

Ejemplos:

* Accuracy
* Volatility
* Return

---

# Agregados (Aggregates)

## Asset Aggregate

Compuesto por:

* Asset
* HistoricalPrice
* TechnicalIndicator

---

## Forecast Aggregate

Compuesto por:

* Forecast
* PredictionModel

---

# Servicios de Dominio

## Market Service

Responsable de obtener información financiera.

---

## Forecast Service

Responsable de generar predicciones.

---

## Indicator Service

Responsable de calcular indicadores técnicos.

---

## AI Service

Responsable de integrar Inteligencia Artificial.

---

## Risk Service

Responsable del análisis de riesgo.

---

# Repositorios

La capa de dominio únicamente define contratos.

## Asset Repository

Operaciones:

* Obtener activo.
* Buscar activos.
* Guardar activo.

---

## HistoricalPrice Repository

Operaciones:

* Obtener histórico.
* Guardar histórico.

---

## Forecast Repository

Operaciones:

* Guardar predicción.
* Consultar historial.

---

# Relaciones del dominio

```text
Asset
│
├── Historical Prices
│
├── Technical Indicators
│
└── Forecasts
       │
       └── Prediction Model
```

---

# Evolución del dominio

## MVP Profesional

* Asset
* HistoricalPrice
* Forecast
* PredictionModel
* TechnicalIndicator

---

## Enterprise Edition

Se incorporarán:

* Portfolio
* User
* Alert
* News
* Sentiment
* Risk Profile
* Economic Indicator
* AI Agent
* Recommendation

---

# Principios del Dominio

El dominio será independiente de:

* FastAPI
* SQLAlchemy
* PostgreSQL
* Azure
* React
* Docker

Las reglas del negocio permanecerán inalterables incluso cuando cambien las tecnologías utilizadas por la plataforma.

---

# Objetivo de largo plazo

Construir un modelo de dominio robusto, expresivo y preparado para evolucionar durante los próximos años, permitiendo incorporar nuevas capacidades de Inteligencia Artificial sin alterar las reglas fundamentales del negocio financiero.

El dominio es el activo más valioso de NeuroFin AI Platform y será la referencia para todas las decisiones de diseño, implementación y evolución futura.
