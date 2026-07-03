# ADR-005 — Integración futura con Azure AI

**Fecha:** 2026-07-02

**Estado:** Propuesto para evolución futura

**Proyecto:** NeuroFin AI Platform

---

# Contexto

NeuroFin AI Platform busca evolucionar desde una API de forecasting financiero hacia una plataforma de inteligencia artificial aplicada al análisis financiero.

La visión de largo plazo incluye capacidades como explicación de predicciones, interpretación de indicadores, resumen de noticias financieras, generación de reportes y agentes conversacionales especializados.

Microsoft Azure ofrece servicios relevantes para esta evolución, especialmente Azure AI Foundry, Azure OpenAI y Azure Machine Learning.

---

# Decisión

Se define Azure AI como línea estratégica de evolución, pero no como dependencia obligatoria del MVP inicial.

La plataforma mantendrá una arquitectura preparada para integrar Azure AI en fases futuras, evitando acoplar el dominio a servicios cloud desde el inicio.

---

# Justificación

Esta decisión permite equilibrar dos objetivos:

1. Construir un MVP simple, funcional y presentable.
2. Mantener una visión profesional de escalabilidad e integración cloud.

Azure AI será valioso cuando existan suficientes datos, casos de uso y usuarios que justifiquen capacidades avanzadas.

---

# Servicios considerados

## Azure AI Foundry

Uso futuro:

* Construcción de agentes.
* Orquestación de capacidades de IA.
* Evaluación de prompts.
* Integración de modelos fundacionales.

---

## Azure OpenAI

Uso futuro:

* Explicación de predicciones.
* Resumen de noticias financieras.
* Generación de análisis ejecutivo.
* Chat educativo financiero.

---

## Azure Machine Learning

Uso futuro:

* Registro de modelos.
* Experimentación.
* Tracking de métricas.
* Versionado de modelos.
* Reentrenamiento controlado.

---

# Casos de uso futuros

## Explicación de predicciones

El sistema podrá explicar por qué un modelo proyecta determinado comportamiento.

Ejemplo:

```text
El modelo detectó una tendencia ascendente moderada, pero con alta volatilidad reciente.
```

---

## Reporte financiero automatizado

El sistema podrá generar un resumen ejecutivo basado en datos de mercado, indicadores y resultados de modelos.

---

## Asistente financiero educativo

El usuario podrá consultar conceptos como:

* Volatilidad.
* Riesgo.
* Tendencia.
* Media móvil.
* Señales técnicas.
* Interpretación de forecast.

---

## Análisis de sentimiento

La plataforma podrá procesar noticias financieras y producir indicadores de sentimiento.

---

# Principios de integración

La integración con Azure AI deberá cumplir:

* No acoplar el dominio a Azure.
* Encapsular clientes Azure en infraestructura.
* Usar contratos internos para servicios de explicación.
* Mantener trazabilidad de respuestas generadas por IA.
* Evitar recomendaciones financieras absolutas.
* Registrar prompts, versiones y resultados cuando aplique.

---

# Diseño conceptual

```text
Presentation
  └── /api/v1/explain
Application
  └── ExplainForecastUseCase
Domain
  └── ForecastExplanationService
Infrastructure
  └── AzureOpenAIForecastExplanationService
```

El caso de uso dependerá de un contrato, no directamente del SDK de Azure.

---

# Riesgos

## Costo operativo

Los servicios de IA generativa pueden generar costos variables.

Mitigación:

* Usar IA generativa solo en funciones justificadas.
* Implementar límites por usuario.
* Cachear explicaciones cuando sea razonable.

---

## Alucinaciones

Los modelos generativos pueden producir explicaciones incorrectas.

Mitigación:

* Restringir prompts con datos estructurados.
* Mostrar advertencias.
* Evitar consejos financieros definitivos.
* Validar salidas críticas.

---

## Seguridad

La integración puede exponer datos sensibles si no se diseña correctamente.

Mitigación:

* Usar Key Vault.
* Separar entornos.
* No enviar información innecesaria al modelo.
* Controlar acceso por usuario.

---

# Relación con certificación Microsoft

La futura integración con Azure AI puede apoyar el desarrollo de competencias asociadas a:

* Azure AI Engineer.
* Azure AI Foundry.
* Azure OpenAI.
* Diseño de soluciones inteligentes.
* Desarrollo de aplicaciones con IA generativa.

El proyecto puede servir como laboratorio profesional para aplicar conceptos de certificación en un caso real.

---

# Estado en el MVP

Azure AI no se implementará en el MVP inicial.

El MVP se enfocará en:

* API funcional.
* Forecast baseline.
* Clean Architecture.
* Pruebas automatizadas.
* Documentación profesional.

La integración Azure AI queda documentada como ruta futura.

---

# Criterio de activación

Azure AI deberá integrarse cuando se cumpla al menos una de estas condiciones:

* Exista un frontend funcional que consuma explicaciones.
* Existan datos reales o históricos suficientes.
* Exista un caso de uso claro de análisis en lenguaje natural.
* El backend tenga autenticación y control de uso.
* Se requiera una demo avanzada para certificación o SaaS.

---

# Criterio de éxito

La integración será exitosa si:

* Mejora la comprensión del usuario.
* No sustituye la validación cuantitativa.
* Mantiene control de costos.
* Respeta la arquitectura.
* Aporta valor real al producto.

---

# Conclusión

Azure AI representa una evolución estratégica para NeuroFin AI Platform, pero no debe apresurarse durante el MVP. La prioridad inicial es construir una base sólida. Una vez validada la plataforma, Azure AI permitirá transformar el sistema en una experiencia más inteligente, educativa y escalable.
