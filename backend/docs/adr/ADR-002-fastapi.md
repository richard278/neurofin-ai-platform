# ADR-002 — Uso de FastAPI como framework backend

**Fecha:** 2026-07-02

**Estado:** Aceptado

**Proyecto:** NeuroFin AI Platform

---

# Contexto

NeuroFin AI Platform requiere una API moderna para exponer servicios de predicción financiera, análisis de mercado e inteligencia artificial.

El backend debe ser compatible con Python, Machine Learning, validación fuerte de datos, documentación automática y despliegue cloud.

El proyecto también debe presentarse con un estándar familiar para reclutadores de Estados Unidos, donde FastAPI, Python, APIs REST y cloud son competencias muy valoradas.

---

# Decisión

Se adopta FastAPI como framework principal para el backend REST.

FastAPI se utilizará en la capa de presentación para:

* Definir rutas HTTP.
* Validar requests mediante Pydantic.
* Generar documentación OpenAPI.
* Exponer Swagger UI.
* Integrar dependencias de aplicación.
* Servir como interfaz entre clientes y casos de uso.

---

# Justificación

FastAPI es adecuado para NeuroFin porque:

* Está diseñado para Python moderno.
* Se integra naturalmente con Pydantic.
* Genera documentación automática.
* Tiene buen rendimiento.
* Es compatible con desarrollo de APIs de Machine Learning.
* Permite una experiencia clara en demos técnicas.
* Puede desplegarse en contenedores y plataformas cloud.

---

# Consecuencias positivas

* API clara y documentada automáticamente.
* Menor fricción para probar endpoints desde Swagger.
* Validación robusta de entrada.
* Buena integración con pruebas mediante TestClient.
* Compatibilidad directa con modelos Python.
* Excelente presentación para un portafolio profesional.

---

# Consecuencias negativas

* Requiere disciplina para no colocar lógica de negocio dentro de routers.
* El equipo debe comprender Pydantic y tipado en Python.
* Para producción se requiere configurar correctamente servidor ASGI, CORS, seguridad y observabilidad.

---

# Alternativas consideradas

## Flask

Ventaja:

* Simplicidad y amplia adopción.

Desventajas:

* Menos estructura por defecto.
* Documentación OpenAPI requiere más configuración.
* Menor alineación con tipado moderno.

---

## Django REST Framework

Ventaja:

* Ecosistema maduro y completo.

Desventajas:

* Más pesado para un backend API-first de Machine Learning.
* Menor simplicidad para un MVP enfocado en servicios predictivos.
* Puede introducir complejidad innecesaria al inicio.

---

## Node.js / Express

Ventaja:

* Popular en APIs web.

Desventajas:

* Menor integración directa con librerías científicas de Python.
* Requeriría separar más temprano la capa de Machine Learning.

---

# Regla de implementación

Los routers de FastAPI no deben contener reglas de negocio complejas.

Los routers deben:

* Recibir request.
* Validar esquema.
* Invocar caso de uso.
* Transformar respuesta.
* Manejar errores HTTP.

Los casos de uso deben vivir en la capa `application`.

---

# Estado en el MVP

El backend actual expone:

```text
GET /api/v1/health
POST /api/v1/forecast
```

El endpoint de forecast utiliza:

* `ForecastRequest`.
* `GenerateForecastUseCase`.
* `ForecastResponse`.

Esta estructura ya respeta la separación entre presentación y aplicación.

---

# Criterio de éxito

FastAPI será una elección exitosa si permite:

* Ejecutar una demo técnica clara.
* Mantener endpoints versionados.
* Generar documentación automática.
* Validar datos de entrada.
* Integrar modelos futuros sin romper la API.
* Desplegar la aplicación en cloud.

---

# Conclusión

FastAPI es la opción correcta para el backend de NeuroFin AI Platform porque combina productividad, documentación automática, tipado moderno y una integración natural con Machine Learning en Python. Esta decisión fortalece el MVP como portafolio y deja abierta una evolución ordenada hacia una plataforma SaaS.
