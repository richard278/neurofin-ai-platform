# NeuroFin AI Platform

# Documento 04 — API Design

**Versión:** 1.0.0

**Estado:** Diseño de API

**Autor:** Richard Milian

**Proyecto:** NeuroFin AI Platform

---

# Propósito

Este documento define el diseño inicial de la API REST de NeuroFin AI Platform.

La API será la interfaz principal entre el frontend web, otros clientes externos y los servicios internos de análisis financiero, predicción e inteligencia artificial.

---

# Principios de diseño

La API se construirá bajo los siguientes principios:

* API First.
* Versionado explícito.
* Contratos claros.
* Respuestas predecibles.
* Validación mediante Pydantic.
* Separación entre dominio y presentación.
* Manejo uniforme de errores.
* Documentación automática mediante OpenAPI.
* Compatibilidad futura con Azure y otros clientes web.

---

# Versionado

Todas las rutas públicas estarán versionadas.

```text
/api/v1
```

Ejemplo:

```text
GET /api/v1/health
GET /api/v1/market/AAPL
POST /api/v1/forecast
```

El versionado permitirá evolucionar la plataforma sin romper integraciones existentes.

---

# Convenciones generales

## Formato de datos

La API utilizará JSON como formato principal de intercambio.

## Nombres de campos

Los nombres de campos usarán `snake_case` en el backend.

Ejemplo:

```json
{
  "asset_symbol": "AAPL",
  "forecast_horizon": 30
}
```

## Fechas

Las fechas se representarán en formato ISO 8601.

```text
YYYY-MM-DD
YYYY-MM-DDTHH:MM:SSZ
```

## Moneda

Los valores monetarios deberán indicar moneda cuando aplique.

```json
{
  "amount": 185.42,
  "currency": "USD"
}
```

---

# Estructura estándar de respuesta

Para el MVP, la API podrá utilizar respuestas directas para mantener simplicidad.

Ejemplo:

```json
{
  "symbol": "AAPL",
  "close": 185.42,
  "currency": "USD"
}
```

En una fase posterior se podrá adoptar un envoltorio estándar:

```json
{
  "success": true,
  "data": {},
  "message": "Request processed successfully"
}
```

---

# Manejo de errores

Los errores deberán ser claros, consistentes y útiles para el cliente.

Ejemplo:

```json
{
  "detail": "Asset not found"
}
```

Errores comunes:

```text
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
422 Validation Error
500 Internal Server Error
```

---

# Endpoints del MVP Profesional

## Health

### GET /api/v1/health

Verifica el estado general de la API.

Respuesta esperada:

```json
{
  "status": "ok",
  "app_name": "NeuroFin AI Platform",
  "version": "0.1.0",
  "environment": "development"
}
```

---

# Market Data

## GET /api/v1/market/{symbol}

Obtiene información básica de mercado para un activo financiero.

Parámetros:

```text
symbol: string
```

Ejemplo:

```text
GET /api/v1/market/AAPL
```

Respuesta esperada:

```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "currency": "USD",
  "last_close": 185.42,
  "provider": "Yahoo Finance"
}
```

---

## GET /api/v1/market/{symbol}/history

Obtiene precios históricos de un activo.

Query parameters:

```text
period: string
interval: string
```

Ejemplo:

```text
GET /api/v1/market/AAPL/history?period=6mo&interval=1d
```

Respuesta esperada:

```json
{
  "symbol": "AAPL",
  "period": "6mo",
  "interval": "1d",
  "prices": [
    {
      "date": "2026-01-01",
      "open": 180.1,
      "high": 186.5,
      "low": 179.2,
      "close": 185.42,
      "volume": 98234000
    }
  ]
}
```

---

# Technical Indicators

## GET /api/v1/indicators/{symbol}

Calcula indicadores técnicos para un activo.

Query parameters:

```text
period: string
interval: string
indicators: string
```

Ejemplo:

```text
GET /api/v1/indicators/AAPL?period=6mo&interval=1d&indicators=sma,ema,rsi
```

Respuesta esperada:

```json
{
  "symbol": "AAPL",
  "indicators": {
    "sma": 183.24,
    "ema": 184.01,
    "rsi": 57.8
  }
}
```

---

# Forecast

## POST /api/v1/forecast

Genera una predicción financiera.

Request body:

```json
{
  "symbol": "AAPL",
  "horizon": 30,
  "model": "linear_regression"
}
```

Respuesta esperada:

```json
{
  "symbol": "AAPL",
  "model": "linear_regression",
  "horizon": 30,
  "generated_at": "2026-06-28T10:00:00Z",
  "predictions": [
    {
      "step": 1,
      "date": "2026-06-29",
      "predicted_close": 186.11
    }
  ],
  "metrics": {
    "mae": 2.14,
    "rmse": 3.02
  }
}
```

---

## GET /api/v1/forecast/{symbol}/history

Consulta el historial de predicciones generadas para un activo.

Ejemplo:

```text
GET /api/v1/forecast/AAPL/history
```

Respuesta esperada:

```json
{
  "symbol": "AAPL",
  "forecasts": [
    {
      "forecast_id": "f_001",
      "model": "linear_regression",
      "horizon": 30,
      "generated_at": "2026-06-28T10:00:00Z"
    }
  ]
}
```

---

# Modelos Pydantic iniciales

## MarketPriceResponse

```python
class MarketPriceResponse(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
```

## ForecastRequest

```python
class ForecastRequest(BaseModel):
    symbol: str
    horizon: int = Field(default=30, ge=1, le=365)
    model: str = Field(default="linear_regression")
```

## ForecastPointResponse

```python
class ForecastPointResponse(BaseModel):
    step: int
    date: date
    predicted_close: float
```

## ForecastResponse

```python
class ForecastResponse(BaseModel):
    symbol: str
    model: str
    horizon: int
    generated_at: datetime
    predictions: list[ForecastPointResponse]
    metrics: dict[str, float]
```

---

# Recursos futuros

Los siguientes recursos quedan fuera del MVP inicial, pero serán considerados en la Enterprise Edition:

```text
/users
/portfolio
/risk
/news
/sentiment
/agents
/recommendations
/economic-indicators
```

---

# Seguridad

Para el MVP local, la API podrá ejecutarse sin autenticación.

Para versiones posteriores se incorporará:

* JWT.
* OAuth2.
* Azure Entra ID.
* API Keys.
* Rate limiting.
* Seguridad de secretos mediante Azure Key Vault.

---

# Observabilidad

La API deberá evolucionar hacia:

* Logging estructurado.
* Métricas.
* Trazabilidad.
* Monitoreo en Azure.

Servicios futuros:

* Azure Monitor.
* Application Insights.

---

# Criterios de aceptación del diseño API

La API será considerada lista para el MVP cuando:

* Todos los endpoints principales estén versionados.
* OpenAPI documente automáticamente los contratos.
* Las respuestas sean consistentes.
* Las validaciones se realicen con Pydantic.
* Los errores sean claros.
* Existan pruebas básicas para los endpoints principales.
* El diseño permita incorporar nuevos módulos sin romper compatibilidad.

---

# Conclusión

El diseño de la API de NeuroFin AI Platform busca equilibrar simplicidad, claridad y capacidad de crecimiento.

El MVP Profesional iniciará con endpoints enfocados en salud del sistema, datos financieros, indicadores técnicos y predicción.

A partir de esta base, la plataforma podrá evolucionar hacia capacidades avanzadas de Machine Learning, Azure AI, análisis de sentimiento, portafolios y agentes inteligentes.
