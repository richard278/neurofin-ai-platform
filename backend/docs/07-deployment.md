NeuroFin AI Platform

Documento 07 — Deployment y Entornos

Versión: 1.0.0

Estado: Ejecución local y opciones para una futura demo pública.

Autor: Richard Milian

Proyecto: NeuroFin AI Platform

Propósito

Este documento define la estrategia de ejecución, publicación y evolución de entornos para NeuroFin AI Platform.

El objetivo principal es permitir que el proyecto pueda ejecutarse localmente como MVP profesional para portafolio, y que posteriormente pueda desplegarse en un entorno cloud sin alterar su arquitectura base.

Estrategia general

La estrategia de deployment se divide en tres niveles:

Ejecución local para desarrollo y demostración.

PostgreSQL local mediante Compose; contenerización completa de la aplicación pendiente.

Publicación cloud para demo pública y evolución SaaS.

El MVP inicial no requiere infraestructura compleja. Para reclutadores, el valor principal será demostrar que la API puede instalarse, ejecutarse, probarse y entenderse con facilidad.

Entornos previstos

Development

Entorno local de desarrollo.

Uso:

Programación diaria.

Ejecución de pruebas.

Revisión de Swagger.

Validación de arquitectura.

Configuración esperada:

APP_ENV=development
API_PREFIX=/api/v1

Staging

Entorno intermedio de validación.

Uso futuro:

Pruebas antes de producción.

Validación con frontend.

Pruebas con datos de mercado reales.

Validación de seguridad y CORS.

Estado:

🔵 Evolución posterior al MVP.

Production

Entorno productivo.

Uso futuro:

Usuarios reales.

Autenticación.

Persistencia.

Observabilidad.

Escalabilidad.

Estado:

🔵 Evolución SaaS.

Ejecución local del backend

Desde la carpeta backend:

python -m venv .venv

Activación en Windows:

.venv\Scripts\activate

Activación en Linux/macOS:

source .venv/bin/activate

Instalación:

pip install -e .[dev]

Ejecución:

uvicorn app.main:app --reload

URL local esperada:

http://127.0.0.1:8000

Documentación Swagger:

http://127.0.0.1:8000/docs

ReDoc:

http://127.0.0.1:8000/redoc

Pruebas automatizadas

El backend debe validarse con:

pytest -q

Pruebas actuales esperadas:

Health check.

Forecast con valores proporcionados y con proveedor de mercado simulado en pruebas.

Validación de entrada inválida.

El estado saludable del MVP requiere que todas las pruebas pasen antes de publicar cambios.

Endpoints mínimos para demo

El MVP inicial debe poder demostrar:

GET /api/v1/health
POST /api/v1/forecast
POST /api/v1/forecast/market-data

La ruta de mercado necesita TWELVE_DATA_API_KEY en el servidor; devuelve HTTP 503 si falta. El frontend actual consume la ruta de valores aportados. Ejemplo de payload para forecast manual:

{
  "symbol": "MSFT",
  "historical_values": [100.0, 101.2, 102.5, 103.3],
  "horizon": 3
}

Respuesta esperada:

{
  "symbol": "MSFT",
  "horizon": 3,
  "points": [
    { "step": 1, "value": 101.75 },
    { "step": 2, "value": 101.75 },
    { "step": 3, "value": 101.75 }
  ]
}

Dockerización prevista

La contenerización permitirá ejecutar la API de forma portable.

Archivo sugerido:

backend/Dockerfile

Estructura conceptual:

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY tests ./tests

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

Este Dockerfile es una referencia de diseño; podrá agregarse cuando el MVP requiera publicación mediante contenedores.

Docker Compose previsto

Ya existe infra/postgres/compose.yml para PostgreSQL local. Un Compose para la aplicación completa podría incluir:

API FastAPI.

PostgreSQL.

Redis.

Servicio de frontend.

Worker de procesamiento.

Estructura futura:

services:
  api:
  postgres:
  redis:
  frontend:
  worker:

Estado:

🔵 Evolución SaaS.

Publicación inicial recomendada

Para portafolio y reclutadores, la secuencia recomendada es:

Repositorio GitHub limpio.

README claro con propósito, stack y comandos.

Backend ejecutable localmente.

Pruebas automatizadas pasando.

Swagger disponible.

Capturas o video corto de demo.

Evaluar publicación cloud cuando la demo sea reproducible; la plataforma queda por decidir.

Esta secuencia evita sobredimensionar el proyecto antes de tener un MVP presentable.

Selección de infraestructura para la demo

El primer despliegue público deberá reproducir el flujo funcional con el menor costo y carga operativa razonables. La decisión se tomará después de verificar requisitos del cliente React, del servicio FastAPI y, si un flujo público lo necesita, de PostgreSQL administrado.

Componente

Capacidad requerida

Opciones por evaluar

Cliente React

Build estático, HTTPS y URL pública

Hosting estático administrado.

API FastAPI

Proceso Python, variables de entorno, tráfico HTTPS y logs

Servicio web administrado o contenedor.

PostgreSQL

Persistencia duradera y conexión segura cuando se expongan flujos de identidad

Servicio PostgreSQL administrado.

Render, Railway, Azure y otros proveedores pueden satisfacer partes de este esquema. Su elección depende de límites gratuitos, costo mensual, tiempo de arranque, disponibilidad, configuración de secretos, conectividad y experiencia de quien evalúa la demo. La evaluación de Azure detalla una opción posible; ADR-006 registra la independencia del alojamiento.

No se anuncia una demo pública hasta haber verificado build, rutas, CORS, claves, comportamiento de la base de datos necesaria y respuesta tras inactividad en el proveedor elegido.

Checklist de despliegue MVP

Antes de publicar la demo:

Verificar que .env no esté versionado.

Confirmar que .env.example esté actualizado.

Ejecutar pytest -q.

Revisar Swagger.

Confirmar que CORS permita únicamente los orígenes reales de la demo.

Verificar que no exista .venv dentro del repositorio.

Validar que README.md explique instalación y ejecución.

Agregar capturas o guía de demo para reclutadores.

Archivos que no deben subirse a GitHub

No deben versionarse:

.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
*.pyc
.DS_Store

La exclusión del entorno virtual es importante porque reduce el tamaño del repositorio y evita problemas de portabilidad entre sistemas operativos.

Deployment futuro con CI/CD

En una fase posterior se podrá incorporar GitHub Actions.

Flujo recomendado:

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

Estado:

🔵 Evolución posterior al MVP.

Observabilidad futura

Para producción se recomienda integrar:

Logs estructurados.

Telemetría del proveedor seleccionado, si aporta valor.

Métricas de latencia.

Métricas de errores.

Métricas de uso por endpoint.

Alertas ante fallos.

La observabilidad será fundamental cuando el proyecto evolucione a SaaS.

Consideraciones para SaaS

Antes de escalar a SaaS será necesario agregar:

Exponer y validar el flujo público de autenticación y gestión de usuarios sobre los componentes internos actuales.

Planes de suscripción.

Conectar los flujos públicos que requieran PostgreSQL; sus componentes para identidad y sesiones ya existen.

Rate limiting.

Auditoría.

Tareas asíncronas.

Registro de predicciones.

Separación por tenant o cliente.

Estos elementos no son obligatorios para el MVP inicial.

Conclusión

El deployment de NeuroFin AI Platform debe avanzar de forma progresiva.

La primera meta es que el proyecto sea fácil de ejecutar y demostrar localmente. La segunda meta es publicar una demo accesible para reclutadores. La tercera meta es evolucionar hacia una arquitectura SaaS con servicios administrados, observabilidad, seguridad y escalabilidad.