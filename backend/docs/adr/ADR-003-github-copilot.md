# ADR-003 — Uso de GitHub Copilot como asistente de desarrollo

**Fecha:** 2026-07-02

**Estado:** Aceptado

**Proyecto:** NeuroFin AI Platform

---

# Contexto

NeuroFin AI Platform se desarrolla como un proyecto profesional de aprendizaje, portafolio e investigación aplicada.

El proyecto busca demostrar no solo capacidad de programación, sino también criterio de arquitectura, documentación, pruebas y uso responsable de herramientas modernas de inteligencia artificial para ingeniería de software.

GitHub Copilot puede acelerar tareas de implementación, documentación, pruebas y refactorización, pero no debe reemplazar el criterio técnico del ingeniero.

---

# Decisión

Se adopta GitHub Copilot como asistente de desarrollo, no como autoridad arquitectónica.

Copilot podrá utilizarse para:

* Sugerir código repetitivo.
* Crear pruebas iniciales.
* Redactar documentación técnica preliminar.
* Proponer refactorizaciones.
* Acelerar creación de schemas, DTOs y casos simples.
* Explicar errores y apoyar depuración.

Las decisiones finales seguirán siendo responsabilidad del desarrollador.

---

# Justificación

El uso de Copilot está alineado con la industria moderna, especialmente en flujos de trabajo de desarrollo asistido por IA.

Para reclutadores, el valor no está en decir que el código fue asistido por IA, sino en demostrar que el ingeniero sabe:

* Diseñar arquitectura.
* Revisar sugerencias.
* Mantener consistencia.
* Escribir pruebas.
* Documentar decisiones.
* Controlar calidad.

---

# Principios de uso

El uso de Copilot seguirá estos principios:

* La arquitectura se decide antes de pedir código.
* El código sugerido debe revisarse antes de aceptarse.
* No se aceptará código que rompa la separación de capas.
* Toda funcionalidad crítica debe tener pruebas.
* Las sugerencias deben adaptarse al estilo del proyecto.
* No se deben introducir secretos, API keys o información sensible.
* La documentación debe representar el estado real del sistema.

---

# Consecuencias positivas

* Mayor velocidad de desarrollo.
* Mejor soporte para pruebas y documentación.
* Mayor productividad en código repetitivo.
* Apoyo para explorar alternativas técnicas.
* Entrenamiento práctico en flujos modernos con IA.

---

# Consecuencias negativas

* Riesgo de aceptar código incorrecto sin revisión.
* Posible inconsistencia de estilo.
* Posible sobreingeniería generada por sugerencias automáticas.
* Riesgo de documentación que no refleje el estado real del código.

---

# Controles de calidad

Para reducir riesgos, todo aporte asistido por IA deberá pasar por:

* Revisión manual.
* Pruebas automatizadas.
* Validación arquitectónica.
* Comparación contra documentación existente.
* Commits claros.

---

# Uso recomendado por tipo de tarea

## Código de aplicación

Permitido con revisión estricta.

Ejemplos:

* Casos de uso.
* Schemas.
* Repositorios.
* Servicios de infraestructura.

---

## Pruebas

Altamente recomendado.

Ejemplos:

* Pruebas de endpoints.
* Pruebas de validación.
* Casos borde.

---

## Documentación

Permitido como borrador, pero debe ajustarse a la realidad del proyecto.

---

## Seguridad

Uso restringido.

Las decisiones de seguridad deben validarse cuidadosamente y no depender solo de sugerencias automáticas.

---

# Relación con el MVP

En el MVP inicial, Copilot puede apoyar en:

* Mantener documentación clara.
* Expandir pruebas.
* Crear ejemplos de requests.
* Preparar refactorizaciones pequeñas.
* Acelerar endpoints adicionales.

No debe utilizarse para introducir funcionalidades SaaS prematuras que compliquen el alcance inicial.

---

# Relación con SaaS futuro

En una evolución SaaS, Copilot puede apoyar en:

* Autenticación.
* Integración con base de datos.
* Jobs asíncronos.
* Observabilidad.
* Integración cloud.
* Generación de documentación para APIs internas.

Cada decisión deberá formalizarse con ADR cuando afecte la arquitectura.

---

# Criterio de éxito

El uso de Copilot será exitoso si:

* Aumenta productividad sin sacrificar calidad.
* No rompe Clean Architecture.
* No introduce dependencias innecesarias.
* Ayuda a documentar y probar mejor.
* Fortalece la capacidad profesional del proyecto.

---

# Conclusión

GitHub Copilot será utilizado como copiloto técnico, no como piloto principal. NeuroFin AI Platform debe demostrar que el desarrollador sabe usar IA con criterio profesional, manteniendo control sobre arquitectura, calidad y dirección del producto.
