# ARMS AI — Portfolio Architecture

## 1. Propósito

El módulo `backend.portfolio` administra posiciones, snapshots,
reportes de rendimiento y análisis cuantitativo de riesgo.

Sus objetivos son:

- representar portafolios de forma inmutable;
- calcular métricas financieras reproducibles;
- analizar exposición, concentración y diversificación;
- ejecutar pruebas de estrés y escenarios;
- exportar resultados a JSON, CSV y HTML;
- servir como base para optimización y gestión automática.

---

## 2. Principios de diseño

1. Objetos de dominio inmutables.
2. Validación explícita de entradas.
3. Separación entre modelos, análisis y exportadores.
4. Resultados deterministas y fáciles de probar.
5. Dependencias dirigidas desde capas externas hacia el dominio.
6. Sin dependencias de interfaces, brokers o proveedores externos.
7. Compatibilidad futura con ARMS OS y arquitectura por eventos.
8. Cada módulo debe tener pruebas unitarias independientes.

---

## 3. Capas

### 3.1 Domain Models

Representan el estado del portafolio.

- `PortfolioPosition`
- `Portfolio`
- `PortfolioSnapshot`

### 3.2 Performance Reporting

Analiza la evolución histórica.

- `PortfolioReport`

### 3.3 Allocation and Exposure Analytics

Analiza cómo está distribuido el capital.

- `PortfolioExposureReport`
- `PortfolioAssetAllocation`
- `PortfolioConcentrationReport`

### 3.4 Risk Analytics

Calcula métricas de riesgo.

- `PortfolioVaRReport`
- `PortfolioCVaRReport`
- `PortfolioCorrelationMatrix`
- `PortfolioDiversificationReport`
- `PortfolioRiskContribution`

### 3.5 Scenario Analytics

Evalúa escenarios hipotéticos.

- `PortfolioStressTest`
- `PortfolioScenarioAnalysis`

### 3.6 Reporting and Interfaces

Presenta resultados fuera del dominio.

- `PortfolioJsonExporter`
- `PortfolioCsvExporter`
- `PortfolioDashboardExporter`
- `run_portfolio`

---

## 4. Flujo principal

```text
PortfolioPosition
        │
        ▼
    Portfolio
        │
        ▼
PortfolioSnapshot
        │
        ▼
 PortfolioReport
        │
        ├── JSON Exporter
        ├── CSV Exporter
        ├── HTML Dashboard
        └── CLI
