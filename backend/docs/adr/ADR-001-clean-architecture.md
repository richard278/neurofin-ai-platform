# ADR-001 — Uso de Clean Architecture

**Fecha:** 2026-07-02

**Estado:** Aceptado

**Proyecto:** NeuroFin AI Platform

---

# Contexto

NeuroFin AI Platform nace como un proyecto de inteligencia artificial financiera con aspiración de crecer más allá de un prototipo académico.

El sistema debe iniciar como MVP para portafolio profesional, pero su diseño debe permitir una evolución futura hacia una plataforma SaaS con múltiples módulos: forecasting, análisis de mercado, modelos de Machine Learning, reportes, portafolios, usuarios y capacidades de IA generativa.

Para lograr esa evolución, el proyecto necesita una arquitectura que evite mezclar reglas de negocio con frameworks, librerías, bases de datos o proveedores cloud.

---

# Decisión

Se adopta Clean Architecture como arquitectura base del backend.

La aplicación se organiza en capas:

* Domain.
* Application.
* Infrastructure.
* Presentation.
* Core.

La capa de dominio contendrá entidades, contratos y reglas centrales. La capa de aplicación coordinará casos de uso. La capa de infraestructura implementará detalles técnicos. La capa de presentación expondrá la API mediante FastAPI.

---

# Justificación

Clean Architecture permite:

* Separar el dominio del framework web.
* Sustituir implementaciones sin reescribir reglas de negocio.
* Probar casos de uso con menor acoplamiento.
* Integrar nuevos modelos de Machine Learning bajo contratos estables.
* Cambiar almacenamiento en memoria por PostgreSQL en fases futuras.
* Migrar a Azure sin contaminar el dominio con SDKs cloud.
* Presentar el proyecto como evidencia de arquitectura profesional.

---

# Consecuencias positivas

* El backend queda preparado para crecimiento modular.
* Los casos de uso son más claros.
* Las dependencias externas quedan encapsuladas.
* El proyecto es más legible para reclutadores técnicos.
* La arquitectura favorece pruebas automatizadas.
* La evolución a SaaS será más ordenada.

---

# Consecuencias negativas

* La estructura inicial es más extensa que un prototipo simple.
* Requiere disciplina para no saltarse capas.
* Algunas funciones pequeñas pueden parecer sobrearquitecturadas durante el MVP.

---

# Alternativas consideradas

## Estructura plana FastAPI

Se consideró colocar rutas, lógica y modelos en pocos archivos.

Ventaja:

* Mayor velocidad inicial.

Desventajas:

* Difícil de escalar.
* Mezcla responsabilidades.
* Menor valor profesional como portafolio.
* Mayor riesgo de deuda técnica.

---

## Arquitectura por módulos sin capas claras

Se consideró organizar por módulos funcionales sin Clean Architecture estricta.

Ventaja:

* Flexibilidad inicial.

Desventajas:

* Las reglas de negocio pueden mezclarse con infraestructura.
* Menos claridad para evolucionar a SaaS.
* Mayor dificultad para pruebas unitarias.

---

# Regla arquitectónica

El dominio no debe depender de:

* FastAPI.
* Pydantic.
* SQLAlchemy.
* Azure SDK.
* Pandas.
* Scikit-Learn.
* Servicios externos.

Las dependencias deben apuntar hacia el centro del sistema.

---

# Estado en el MVP

El backend actual ya refleja esta decisión mediante:

```text
app/domain
app/application
app/infrastructure
app/presentation
app/core
```

El caso de uso `GenerateForecastUseCase` depende de contratos del dominio y no de detalles de FastAPI.

---

# Criterio de éxito

La decisión será exitosa si el proyecto permite:

* Cambiar el modelo baseline por otro modelo sin alterar la API principal.
* Cambiar el repositorio en memoria por PostgreSQL sin alterar el dominio.
* Agregar Azure sin modificar entidades centrales.
* Mantener pruebas automatizadas simples.

---

# Conclusión

Clean Architecture es adecuada para NeuroFin AI Platform porque alinea el MVP inicial con una visión profesional de largo plazo. Aunque agrega estructura desde el inicio, esa estructura comunica madurez técnica y prepara el camino hacia una futura plataforma SaaS.
