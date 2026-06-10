# AutomatizacionV1 — Contexto del Proyecto

## Resumen
Sistema de automatización de consultas de antecedentes en fuentes gubernamentales colombianas
(Procuraduría, Policía Nacional, Contraloría - Responsabilidad Fiscal) a partir de reportes PDF
generados por la plataforma Inspektor.

**Estado:** V1.0 MVP Técnico — en desarrollo  
**Desarrollador:** Franklin Rojas Moreno  
**Director:** Edward Enrique Paniagua  

## Objetivo
Reemplazar el proceso manual de ~20 min/tercero descargando y organizando automáticamente
los 3 certificados de antecedentes por cada persona identificada en los PDFs de entrada.

## Tecnologías
- **Python 3.11+**
- **Playwright** (automatización web)
- **pdfplumber** (extracción de texto de PDFs)
- **openpyxl / pandas** (reporte Excel)
- **logging** nativo (logs estructurados)
- **config.json** (configuración centralizada)

## Arquitectura — Patrones aplicados
- **Strategy Pattern**: cada fuente gubernamental implementa `BaseConsultor` con su propia lógica
- **Template Method**: flujo de consulta compartido (navegar → ingresar datos → CAPTCHA → descargar)
- **Repository Pattern**: `OrganizadorArchivos` abstrae operaciones de filesystem
- **Singleton**: `ConfigManager` y `LoggerManager` instancia única por ejecución
- **Chain of Responsibility**: pipeline de reintentos con backoff
- **Value Object**: `TerceroData` (dataclass inmutable con nombre + cédula)

## Estructura del proyecto
```
AutomatizacionV1/
├── config/config.json          # rutas, reintentos, timeout, headless
├── input/pdfs/                 # PDFs de Inspektor colocados por el operador
├── downloads/                  # descargas temporales del navegador
├── output/CONSULTAS_AUTOMATIZADAS/  # carpetas organizadas por tercero
├── logs/
│   ├── ejecucion.log
│   ├── errores.log
│   └── resumen.csv
├── reports/resultado_consultas.xlsx
├── src/
│   ├── models/
│   │   └── tercero.py          # TerceroData dataclass + ExecutionResult
│   ├── core/
│   │   ├── base_consultor.py   # Strategy base abstracta
│   │   └── retry_handler.py    # lógica de reintentos con backoff
│   ├── consultores/
│   │   ├── procuraduria.py     # consulta Procuraduría (CAPTCHA auto)
│   │   ├── policia.py          # consulta Policía (reCAPTCHA manual)
│   │   └── fiscal.py           # consulta Contraloría (reCAPTCHA manual)
│   ├── services/
│   │   ├── extractor_pdf.py    # extrae nombre + documento del PDF Inspektor
│   │   ├── captcha_solver.py   # resuelve CAPTCHA de texto (Procuraduría)
│   │   ├── organizador.py      # crea carpetas y mueve archivos
│   │   ├── renombrador.py      # convención estándar de nombres
│   │   ├── notificador.py      # alertas correo / Teams
│   │   └── reporte_excel.py    # genera resultado_consultas.xlsx
│   ├── infrastructure/
│   │   ├── config_manager.py   # carga y valida config.json (Singleton)
│   │   └── logger_manager.py   # logging centralizado (Singleton)
│   └── main.py                 # orquestador principal
├── tests/                      # pruebas unitarias por módulo
└── docs/                       # documentos del proyecto
```

## Convención de nombres de archivos de salida
- Procuraduría: `PRO [Nombre completo] CC [Cédula].pdf`
- Policía: `POL [Nombre completo] CC [Cédula].pdf`
- Responsabilidad Fiscal: `RFIS [Nombre completo] CC [Cédula].pdf`
- Carpeta del tercero: `[Nombre completo] CC [Cédula]`

## Fluentes gubernamentales
| Fuente | URL | CAPTCHA | Estrategia |
|--------|-----|---------|------------|
| Procuraduría | https://www.procuraduria.gov.co/Pages/Consulta-de-Antecedentes.aspx | Texto matemático/geográfico | Auto (IA) |
| Policía | https://antecedentes.policia.gov.co:7005/WebJudicial/index.xhtml | reCAPTCHA | Manual (operador) |
| Contraloría | https://www.contraloria.gov.co/control-fiscal/responsabilidad-fiscal/certificado-de-antecedentes-fiscales | reCAPTCHA | Manual (operador) |

## Reglas de negocio críticas
- Máximo 5 reintentos por fuente antes de marcar como FALLIDA
- Una fuente caída NO detiene el proceso — continúa con las demás
- Estados en log: EXITOSO / AUTOMATICO / EN_ESPERA / REINTENTANDO / FALLIDO / FALLIDO_TOTAL / ERROR_PDF
- Reporte Excel se genera al finalizar TODOS los terceros, incluso si hay fallos

## Estándares de código
- PEP8 estricto, líneas máximo 88 caracteres (Black-compatible)
- Type hints en todas las funciones
- Dataclasses para modelos de datos
- Docstrings solo cuando el comportamiento no es obvio
- No comentarios que describan QUÉ hace el código — solo el POR QUÉ
- Excepciones específicas, nunca `except Exception` a secas sin re-raise o log

## Config centralizada (config.json)
Todos los parámetros configurables están en `config/config.json`. Nunca hardcodear
rutas, timeouts o flags en el código fuente.
