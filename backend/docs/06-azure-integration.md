# NeuroFin AI Platform

# Documento 06 — Integración con Microsoft Azure

**Versión:** 1.0.0

**Estado:** Diseño de integración cloud

**Autor:** Richard Milian

**Proyecto:** NeuroFin AI Platform

---

# Propósito

Este documento define la estrategia inicial de integración de NeuroFin AI Platform con el ecosistema Microsoft Azure.

La integración cloud no forma parte obligatoria del primer MVP ejecutable local, pero sí forma parte de la visión profesional del proyecto. El objetivo es que la plataforma pueda presentarse como un producto técnicamente preparado para evolucionar desde un portafolio demostrable hacia una solución SaaS escalable.

---

# Enfoque estratégico

NeuroFin AI Platform se desarrollará primero como un MVP profesional, sencillo de ejecutar, explicar y auditar por reclutadores técnicos.

Posteriormente, la plataforma podrá evolucionar hacia una arquitectura cloud usando servicios de Azure para:

* Hospedaje del backend.
* Persistencia de datos.
* Procesamiento de modelos.
* Almacenamiento de artefactos de Machine Learning.
* Observabilidad.
* Seguridad.
* Integración con Azure AI Foundry y Azure OpenAI.

La prioridad inicial no será usar todos los servicios cloud, sino diseñar el sistema de forma que pueda migrar a ellos sin reescrituras profundas.

---

# Principios de integración Azure

La adopción de Azure seguirá estos principios:

* Primero arquitectura, luego infraestructura.
* Primero MVP funcional, luego escalabilidad.
* Primero costos controlados, luego servicios administrados.
* Separación entre código de negocio y proveedores externos.
* Uso de variables de entorno para configuración.
* Evitar dependencias cloud dentro del dominio.
* Mantener la API portable entre entorno local, contenedores y Azure.

---

# Servicios Azure candidatos

## Azure App Service

Servicio candidato para hospedar el backend FastAPI durante una primera publicación profesional.

Uso previsto:

* Desplegar la API REST.
* Exponer documentación Swagger.
* Configurar variables de entorno.
* Ejecutar la aplicación mediante Uvicorn/Gunicorn.

Estado:

🟡 Fase posterior al MVP local.

---

## Azure Container Apps

Servicio candidato para una evolución más robusta basada en contenedores.

Uso previsto:

* Ejecutar backend como contenedor Docker.
* Escalar de forma administrada.
* Separar servicios futuros como API, workers y procesos de entrenamiento.

Estado:

🔵 Evolución SaaS.

---

## Azure Database for PostgreSQL

Servicio candidato para persistencia relacional.

Uso previsto:

* Usuarios.
* Activos financieros.
* históricos de mercado.
* Resultados de predicción.
* Portafolios.
* Auditoría de operaciones.

Estado:

🔵 Evolución SaaS.

---

## Azure Cache for Redis

Servicio candidato para cache y optimización de consultas.

Uso previsto:

* Cachear datos de mercado consultados con frecuencia.
* Reducir llamadas repetidas a proveedores externos.
* Guardar resultados temporales de predicciones.
* Mejorar tiempos de respuesta.

Estado:

🔵 Evolución SaaS.

---

## Azure Blob Storage

Servicio candidato para almacenamiento de archivos y artefactos.

Uso previsto:

* Datasets procesados.
* Modelos entrenados.
* Reportes exportados.
* Evidencias de experimentos.
* Logs históricos no transaccionales.

Estado:

🔵 Evolución SaaS.

---

## Azure Key Vault

Servicio candidato para manejo seguro de secretos.

Uso previsto:

* API keys de proveedores financieros.
* Secretos de base de datos.
* Cadenas de conexión.
* Llaves de servicios de IA.

Estado:

🔵 Producción / SaaS.

---

## Azure Application Insights

Servicio candidato para observabilidad.

Uso previsto:

* Telemetría de la API.
* Monitoreo de errores.
* Tiempos de respuesta.
* Alertas operativas.
* Diagnóstico de rendimiento.

Estado:

🟡 Publicación cloud inicial.

---

## Azure Machine Learning

Servicio candidato para gestión del ciclo de vida de modelos.

Uso previsto:

* Registro de modelos.
* Experimentación.
* Entrenamiento reproducible.
* Comparación de métricas.
* Versionado de modelos.

Estado:

🔵 Evolución avanzada.

---

## Azure AI Foundry

Servicio candidato para construir capacidades de inteligencia artificial generativa y agentes.

Uso previsto:

* Agente financiero educativo.
* Explicación de predicciones.
* Interpretación de indicadores.
* Orquestación de prompts.
* Integración con Azure OpenAI.

Estado:

🔵 Evolución avanzada / Enterprise Edition.

---

## Azure OpenAI

Servicio candidato para capacidades de lenguaje natural.

Uso previsto:

* Resumen de noticias financieras.
* Explicación de modelos.
* Generación de reportes ejecutivos.
* Chat financiero asistido.
* Interpretación educativa para usuarios no técnicos.

Estado:

🔵 Evolución avanzada / Enterprise Edition.

---

# Mapa de madurez cloud

## Fase 1 — MVP local para portafolio

Objetivo:

Demostrar arquitectura, API funcional, pruebas y documentación profesional.

Servicios Azure requeridos:

Ninguno obligatorio.

Entorno:

* Localhost.
* FastAPI.
* Swagger.
* Pytest.
* Repositorio GitHub.

Resultado esperado:

Proyecto presentable a reclutadores como evidencia de capacidad backend, diseño de arquitectura y pensamiento de producto.

---

## Fase 2 — Demo cloud básica

Objetivo:

Publicar la API para que pueda ser consultada desde navegador o herramientas como Postman.

Servicios sugeridos:

* Azure App Service o Azure Container Apps.
* Application Insights.
* Variables de entorno.

Resultado esperado:

URL pública de demostración con `/health`, `/forecast` y documentación OpenAPI.

---

## Fase 3 — Persistencia y datos reales

Objetivo:

Persistir activos, históricos y resultados.

Servicios sugeridos:

* Azure Database for PostgreSQL.
* Azure Blob Storage.
* Redis opcional.

Resultado esperado:

Base de datos real para histórico financiero y resultados de modelos.

---

## Fase 4 — Machine Learning operacional

Objetivo:

Profesionalizar el ciclo de vida de modelos.

Servicios sugeridos:

* Azure Machine Learning.
* Blob Storage.
* Application Insights.

Resultado esperado:

Modelos versionados, métricas comparables y experimentos reproducibles.

---

## Fase 5 — Plataforma SaaS con IA generativa

Objetivo:

Convertir NeuroFin en una plataforma SaaS con usuarios, planes, portafolios y capacidades de IA asistida.

Servicios sugeridos:

* Azure AI Foundry.
* Azure OpenAI.
* Key Vault.
* PostgreSQL.
* Redis.
* Container Apps.
* Monitor.

Resultado esperado:

Plataforma multiusuario, escalable y orientada a producto.

---

# Variables de entorno previstas

El backend ya está preparado para configuración mediante variables de entorno.

Variables actuales:

```text
APP_NAME=NeuroFin Forecast API
APP_ENV=development
APP_VERSION=0.1.0
API_PREFIX=/api/v1
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DEFAULT_FORECAST_HORIZON=12
```

Variables futuras sugeridas:

```text
DATABASE_URL=
REDIS_URL=
MARKET_DATA_PROVIDER=
MARKET_DATA_API_KEY=
AZURE_STORAGE_CONNECTION_STRING=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
APPLICATIONINSIGHTS_CONNECTION_STRING=
```

Las variables sensibles no deberán almacenarse en GitHub.

---

# Separación arquitectónica requerida

La integración con Azure deberá permanecer fuera del dominio.

El dominio no debe importar:

* SDKs de Azure.
* Clientes HTTP concretos.
* Bases de datos.
* Servicios de infraestructura.
* Frameworks de Machine Learning específicos.

Las integraciones externas deberán ubicarse en la capa de infraestructura.

Ejemplo conceptual:

```text
Domain
  └── Contratos
Application
  └── Casos de uso
Infrastructure
  └── AzureBlobModelRegistry
  └── AzureOpenAIExplanationService
  └── PostgreSQLForecastRepository
Presentation
  └── FastAPI routers
```

---

# Relación con certificaciones Microsoft

NeuroFin AI Platform puede servir como proyecto demostrativo para competencias asociadas a:

* Azure AI Engineer.
* Azure Developer.
* AI Fundamentals.
* Diseño de soluciones cloud.
* Desarrollo de APIs modernas.
* Integración de IA generativa en aplicaciones.

El proyecto tiene valor académico y profesional porque conecta software real con servicios cloud de Microsoft.

---

# Consideraciones de seguridad

Para una futura publicación cloud se deberán considerar:

* Autenticación mediante JWT o proveedor de identidad.
* Separación de entornos: development, staging, production.
* Key Vault para secretos.
* HTTPS obligatorio.
* CORS restringido.
* Rate limiting.
* Auditoría de operaciones críticas.
* Control de acceso por usuario y plan.

---

# Consideraciones de costo

Durante la fase MVP se priorizará el costo cero o mínimo.

La adopción de servicios Azure deberá realizarse de forma gradual, activando únicamente los servicios necesarios para cada fase.

Criterio recomendado:

* MVP local antes de cloud.
* Demo pública antes de infraestructura compleja.
* Servicios administrados solo cuando el producto lo justifique.
* IA generativa únicamente cuando exista un caso de uso claro.

---

# Resultado esperado

Al completar la integración progresiva con Azure, NeuroFin AI Platform deberá demostrar:

* Preparación cloud.
* Separación correcta de responsabilidades.
* Capacidad de despliegue profesional.
* Fundamento para escalar a SaaS.
* Conexión estratégica con certificaciones Microsoft.
* Valor claro para portafolio técnico internacional.

---

# Conclusión

Azure no debe verse como un requisito inicial que complique el MVP, sino como una ruta natural de evolución.

El primer objetivo es construir una base sólida y demostrable. El segundo objetivo es publicar la solución. El tercer objetivo es escalarla como plataforma SaaS apoyada por datos, modelos predictivos e inteligencia artificial generativa.
