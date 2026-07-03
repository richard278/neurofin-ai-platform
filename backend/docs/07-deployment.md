# NeuroFin AI Platform

# Documento 07 — Deployment y Entornos

**Versión:** 1.0.0

**Estado:** Guía de despliegue inicial

**Autor:** Richard Milian

**Proyecto:** NeuroFin AI Platform

---

# Propósito

Este documento define la estrategia de ejecución, publicación y evolución de entornos para NeuroFin AI Platform.

El objetivo principal es permitir que el proyecto pueda ejecutarse localmente como MVP profesional para portafolio, y que posteriormente pueda desplegarse en un entorno cloud sin alterar su arquitectura base.

---

# Estrategia general

La estrategia de deployment se divide en tres niveles:

1. Ejecución local para desarrollo y demostración.
2. Contenerización con Docker para portabilidad.
3. Publicación cloud para demo pública y evolución SaaS.

El MVP inicial no requiere infraestructura compleja. Para reclutadores, el valor principal será demostrar que la API puede instalarse, ejecutarse, probarse y entenderse con facilidad.

---

# Entornos previstos

## Development

Entorno local de desarrollo.

Uso:

* Programación diaria.
* Ejecución de pruebas.
* Revisión de Swagger.
* Validación de arquitectura.

Configuración esperada:

```text
APP_ENV=development
API_PREFIX=/api/v1
```

---

## Staging

Entorno intermedio de validación.

Uso futuro:

* Pruebas antes de producción.
* Validación con frontend.
* Pruebas con datos de mercado reales.
* Validación de seguridad y CORS.

Estado:

🔵 Evolución posterior al MVP.

---

## Production

Entorno productivo.

Uso futuro:

* Usuarios reales.
* Autenticación.
* Persistencia.
* Observabilidad.
* Escalabilidad.

Estado:

🔵 Evolución SaaS.

---

# Ejecución local del backend

Desde la carpeta `backend`:

```bash
python -m venv .venv
```

Activación en Windows:

```bash
.venv\Scripts\activate
```

Activación en Linux/macOS:

```bash
source .venv/bin/activate
```

Instalación:

```bash
pip install -e .[dev]
```

Ejecución:

```bash
uvicorn app.main:app --reload
```

URL local esperada:

```text
http://127.0.0.1:8000
```

Documentación Swagger:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

---

# Pruebas automatizadas

El backend debe validarse con:

```bash
pytest -q
```

Pruebas actuales esperadas:

* Health check.
* Generación de forecast.
* Validación de entrada inválida.

El estado saludable del MVP requiere que todas las pruebas pasen antes de publicar cambios.

---

# Endpoints mínimos para demo

El MVP inicial debe poder demostrar:

```text
GET /api/v1/health
POST /api/v1/forecast
```

Ejemplo de payload para forecast:

```json
{
  "symbol": "MSFT",
  "historical_values": [100.0, 101.2, 102.5, 103.3],
  "horizon": 3
}
```

Respuesta esperada:

```json
{
  "symbol": "MSFT",
  "horizon": 3,
  "points": [
    { "step": 1, "value": 101.75 },
    { "step": 2, "value": 101.75 },
    { "step": 3, "value": 101.75 }
  ]
}
```

---

# Dockerización prevista

La contenerización permitirá ejecutar la API de forma portable.

Archivo sugerido:

```text
backend/Dockerfile
```

Estructura conceptual:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY tests ./tests

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Este Dockerfile es una referencia de diseño; podrá agregarse cuando el MVP requiera publicación mediante contenedores.

---

# Docker Compose previsto

Para una fase posterior, se podrá usar `docker-compose.yml` con:

* API FastAPI.
* PostgreSQL.
* Redis.
* Servicio de frontend.
* Worker de procesamiento.

Estructura futura:

```text
services:
  api:
  postgres:
  redis:
  frontend:
  worker:
```

Estado:

🔵 Evolución SaaS.

---

# Publicación inicial recomendada

Para portafolio y reclutadores, la secuencia recomendada es:

1. Repositorio GitHub limpio.
2. README claro con propósito, stack y comandos.
3. Backend ejecutable localmente.
4. Pruebas automatizadas pasando.
5. Swagger disponible.
6. Capturas o video corto de demo.
7. Publicación cloud opcional.

Esta secuencia evita sobredimensionar el proyecto antes de tener un MVP presentable.

---

# Opciones de despliegue cloud

## Opción A — Azure App Service

Recomendada para una primera publicación sencilla.

Ventajas:

* Menor complejidad inicial.
* Compatible con aplicaciones Python.
* Variables de entorno desde portal Azure.
* Ideal para demo pública.

Uso sugerido:

🟡 Demo pública inicial.

---

## Opción B — Azure Container Apps

Recomendada para una evolución más profesional basada en contenedores.

Ventajas:

* Escalabilidad administrada.
* Separación de servicios.
* Mejor alineación con arquitectura SaaS.
* Compatible con workers y microservicios futuros.

Uso sugerido:

🔵 SaaS / arquitectura avanzada.

---

## Opción C — Render, Railway o servicios similares

Pueden utilizarse temporalmente si se busca una demo rápida y de bajo costo.

Ventajas:

* Simplicidad.
* Rápida publicación.
* Útil para una demo rápida.

Restricción:

No representan la visión cloud final basada en Azure.

---

# Checklist de despliegue MVP

Antes de publicar la demo:

* Verificar que `.env` no esté versionado.
* Confirmar que `.env.example` esté actualizado.
* Ejecutar `pytest -q`.
* Revisar Swagger.
* Confirmar que CORS esté configurado.
* Verificar que no exista `.venv` dentro del repositorio.
* Validar que `README.md` explique instalación y ejecución.
* Agregar capturas o guía de demo para reclutadores.

---

# Archivos que no deben subirse a GitHub

No deben versionarse:

```text
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
*.pyc
.DS_Store
```

La exclusión del entorno virtual es importante porque reduce el tamaño del repositorio y evita problemas de portabilidad entre sistemas operativos.

---

# Deployment futuro con CI/CD

En una fase posterior se podrá incorporar GitHub Actions.

Flujo recomendado:

```text
Push / Pull Request
        ↓
Install dependencies
        ↓
Run linting
        ↓
Run tests
        ↓
Build Docker image
        ↓
Deploy to staging
        ↓
Manual approval
        ↓
Deploy to production
```

Estado:

🔵 Evolución posterior al MVP.

---

# Observabilidad futura

Para producción se recomienda integrar:

* Logs estructurados.
* Application Insights.
* Métricas de latencia.
* Métricas de errores.
* Métricas de uso por endpoint.
* Alertas ante fallos.

La observabilidad será fundamental cuando el proyecto evolucione a SaaS.

---

# Consideraciones para SaaS

Antes de escalar a SaaS será necesario agregar:

* Autenticación.
* Gestión de usuarios.
* Planes de suscripción.
* Persistencia PostgreSQL.
* Rate limiting.
* Auditoría.
* Tareas asíncronas.
* Registro de predicciones.
* Separación por tenant o cliente.

Estos elementos no son obligatorios para el MVP inicial.

---

# Conclusión

El deployment de NeuroFin AI Platform debe avanzar de forma progresiva.

La primera meta es que el proyecto sea fácil de ejecutar y demostrar localmente. La segunda meta es publicar una demo accesible para reclutadores. La tercera meta es evolucionar hacia una arquitectura SaaS con servicios administrados, observabilidad, seguridad y escalabilidad.
