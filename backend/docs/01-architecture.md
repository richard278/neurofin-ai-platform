# NeuroFin AI Platform

# Documento 01 — Arquitectura del Sistema

**Versión:** 1.0.0

**Estado:** Arquitectura Base

**Autor:** Richard Milian

---

# Propósito

Este documento define la arquitectura base de NeuroFin AI Platform.

Su objetivo es proporcionar una estructura técnica escalable, modular y mantenible para soportar el crecimiento de la plataforma durante las siguientes etapas de desarrollo.

La arquitectura ha sido diseñada siguiendo principios de Clean Architecture, separación de responsabilidades y diseño orientado al dominio.

---

# Principios arquitectónicos

La plataforma se construirá bajo los siguientes principios:

* Clean Architecture
* SOLID
* Domain Driven Design (evolutivo)
* API First
* Modularidad
* Escalabilidad
* Testabilidad
* Bajo acoplamiento
* Alta cohesión
* Configuración desacoplada

---

# Arquitectura General

```
                     React Native
                           │
                           │ HTTPS
                           ▼
                   NeuroFin API
                     (FastAPI)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
 Forecast Service   Market Service   AI Service
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                   Domain Layer
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   Machine Learning   Econometrics   Sentiment Analysis
                           │
                           ▼
                    Data Providers
                           │
        ┌──────────────┬──────────────┬──────────────┐
        │              │              │
        ▼              ▼              ▼
 Yahoo Finance   Alpha Vantage   Polygon.io
                           │
                           ▼
                    PostgreSQL
                           │
                           ▼
                        Azure
```

---

# Arquitectura por capas

## Presentation Layer

Responsable de exponer la API REST.

Componentes:

* Routers
* Endpoints
* Request Validation
* Response Models

---

## Application Layer

Orquesta los casos de uso.

Componentes:

* Services
* Commands
* Queries
* DTOs

---

## Domain Layer

Representa el corazón del sistema.

Aquí viven:

* Entidades
* Objetos de Valor
* Reglas de negocio
* Interfaces
* Casos de uso

Esta capa nunca dependerá de FastAPI ni de la base de datos.

---

## Infrastructure Layer

Implementa las dependencias externas.

Incluye:

* PostgreSQL
* Redis
* Azure
* APIs financieras
* Sistema de archivos
* Machine Learning

---

# Organización del proyecto

```
backend
│
├── app
│   ├── api
│   │     └── v1
│   │
│   ├── application
│   │
│   ├── domain
│   │
│   ├── infrastructure
│   │
│   ├── services
│   │
│   ├── repositories
│   │
│   ├── ml
│   │
│   ├── ai
│   │
│   ├── indicators
│   │
│   ├── econometrics
│   │
│   ├── sentiment
│   │
│   ├── datasets
│   │
│   ├── core
│   │
│   ├── schemas
│   │
│   └── main.py
│
├── docs
├── notebooks
├── tests
└── pyproject.toml
```

---

# Dominios principales

La plataforma estará dividida en dominios funcionales.

## Forecast

Predicción de precios.

---

## Market

Obtención de datos financieros.

---

## Indicators

Indicadores técnicos.

---

## Econometrics

Modelos econométricos.

---

## AI

Integración con modelos generativos.

---

## Machine Learning

Entrenamiento de modelos predictivos.

---

## Sentiment

Procesamiento de noticias financieras.

---

## Portfolio

Optimización de inversiones.

---

## Risk

Modelos de evaluación de riesgo.

---

# Flujo de datos

```
Cliente

↓

API REST

↓

Router

↓

Service

↓

Repository

↓

Proveedor Financiero

↓

Procesamiento

↓

Machine Learning

↓

Respuesta JSON
```

---

# Integración con Azure

La arquitectura ha sido diseñada para incorporar progresivamente:

* Azure AI Foundry
* Azure OpenAI
* Azure Machine Learning
* Azure Storage
* Azure SQL Database
* Azure Container Apps
* Azure Key Vault
* Azure Monitor

Sin modificar el núcleo del dominio.

---

# Integración con GitHub

El flujo de desarrollo utilizará:

* GitHub Copilot
* GitHub Actions
* Pull Requests
* Code Review
* Automatización CI/CD

---

# Escalabilidad

La arquitectura permitirá incorporar nuevos módulos sin afectar los existentes.

Cada módulo será independiente y podrá evolucionar de forma aislada.

---

# Objetivo arquitectónico

Construir una plataforma preparada para crecer durante varios años, donde la incorporación de nuevas capacidades de Inteligencia Artificial no requiera rediseñar la arquitectura existente.

La arquitectura será considerada un activo estratégico del proyecto y evolucionará de manera controlada mediante decisiones documentadas (ADR).

---

# Próximos documentos

02-roadmap.md

03-domain-model.md

04-api-design.md

05-machine-learning.md

06-azure-integration.md

07-deployment.md
