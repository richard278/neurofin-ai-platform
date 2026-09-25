# ADR-006 — Selección de despliegue independiente del proveedor

**Fecha:** 2026-09-25

**Estado:** Aceptado como dirección arquitectónica; proveedor de demo pendiente de selección

## Contexto

La visión inicial daba prioridad a Azure y contemplaba aprovechar beneficios estudiantiles. Esa vía no quedó disponible de forma fiable por las condiciones de soporte y convenio. El MVP ya cuenta con una API de forecasting SMA, un adaptador de Twelve Data, un cliente React y fundamentos internos de autenticación y PostgreSQL. El objetivo inmediato es una demostración profesional reproducible.

## Decisión

NeuroFin mantendrá el dominio y los casos de uso independientes del proveedor de alojamiento. La demo podrá usar servicios adecuados para un frontend estático, FastAPI y PostgreSQL cuando un flujo público necesite persistencia. La elección concreta se realizará en una microiteración de despliegue, comparando costo, estabilidad, inicio de la aplicación, gestión de secretos y experiencia de quien evalúa la demo.

Azure sigue siendo una opción posible para etapas futuras y para casos de uso de IA que lo justifiquen; no es requisito del MVP ni condición para una release de portafolio. Tampoco hay servicios de Azure AI implementados en el estado actual.

## Consecuencias

- La documentación pública distinguirá funcionalidad implementada, diseño propuesto y registros históricos.
- La configuración sensible del proveedor de datos y de la base de datos permanecerá fuera de Git.
- El proveedor de datos de mercado seguirá encapsulado detrás de `MarketDataProvider`.
- Una demo publicada deberá validar sus rutas, CORS, secretos, persistencia necesaria y límites del plan de alojamiento antes de anunciarse como disponible.
- `06-azure-integration.md` y `ADR-005-azure-ai.md` conservan el contexto de la alternativa Azure, con esta decisión como referencia actual para el despliegue.
