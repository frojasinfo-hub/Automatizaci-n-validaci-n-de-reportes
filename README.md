# AutomatizaciónV1 — Risk Consulting Global Group

Sistema de automatización para consulta de antecedentes en fuentes gubernamentales colombianas. Procesa reportes PDF generados por la plataforma **Inspektor** y descarga automáticamente los certificados de Procuraduría, Policía Nacional y Contraloría (Responsabilidad Fiscal) por cada tercero identificado.

---

## Descripción

El proceso manual de consulta de antecedentes toma aproximadamente **20 minutos por tercero**. Este sistema lo automatiza completo: extrae los datos de los PDFs de entrada, navega las fuentes gubernamentales, resuelve CAPTCHAs (automático en Procuraduría, asistido en Policía y Contraloría), descarga los certificados y los organiza en carpetas con nomenclatura estándar.

### Fuentes consultadas

| Fuente | CAPTCHA |
|--------|---------|
| Procuraduría General de la Nación | Automático (IA) |
| Policía Nacional — Antecedentes Judiciales | Manual (operador) |
| Contraloría — Responsabilidad Fiscal | Manual (operador) |

### Convención de nombres de certificados

```
PRO  [Nombre completo] CC [Cédula].pdf   ← Procuraduría
POL  [Nombre completo] CC [Cédula].pdf   ← Policía
RFIS [Nombre completo] CC [Cédula].pdf   ← Responsabilidad Fiscal
```

---

## Requisitos

- **Python 3.11+**
- **Google Chrome** (para Playwright)
- Windows 10/11 o Linux (Ubuntu 20.04+)

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/frojasinfo-hub/Automatizaci-n-validaci-n-de-reportes.git
cd Automatizaci-n-validaci-n-de-reportes
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Instalar navegadores de Playwright

```bash
playwright install chromium
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env si se requiere cambiar puertos o carpetas
```

### 5. Revisar configuración

Editar `config/config.json` para ajustar timeouts, reintentos y modo headless según el entorno.

---

## Uso

### Windows — inicio rápido

Ejecutar `start.bat` con doble clic o desde la terminal:

```bat
start.bat
```

Esto instala las dependencias, levanta la **API REST** en `http://localhost:8000` y el **Dashboard** en `http://localhost:8501`, y abre el dashboard automáticamente en el navegador.

### Linux / Servidor

```bash
chmod +x start.sh
./start.sh
```

### Proceso de consulta manual

1. Colocar los PDFs de Inspektor en `input/pdfs/`
2. Acceder al dashboard en `http://localhost:8501`
3. Iniciar el proceso desde la interfaz
4. Para las fuentes con reCAPTCHA (Policía y Contraloría), el sistema esperará que el operador resuelva el CAPTCHA manualmente en el navegador
5. Los certificados quedan organizados en `output/CONSULTAS_AUTOMATIZADAS/`
6. El reporte Excel se genera en `reports/resultado_consultas.xlsx`

---

## Estructura de carpetas

```
AutomatizacionV1/
├── config/config.json              # Parámetros: rutas, timeouts, headless, reintentos
├── input/pdfs/                     # PDFs de Inspektor (colocar aquí antes de ejecutar)
│   └── procesados/                 # PDFs ya procesados (movidos automáticamente)
├── output/CONSULTAS_AUTOMATIZADAS/ # Certificados organizados por tercero
├── logs/                           # ejecucion.log, errores.log, resumen.csv
├── reports/                        # resultado_consultas.xlsx
├── downloads/                      # Descargas temporales del navegador
├── api/app.py                      # API REST (FastAPI)
├── dashboard.py                    # Dashboard de monitoreo (Streamlit)
├── src/
│   ├── consultores/                # Procuraduría, Policía, Contraloría
│   ├── services/                   # Extractor PDF, organizador, reportes
│   ├── core/                       # Base consultor, reintentos
│   ├── models/                     # TerceroData, ExecutionResult
│   ├── infrastructure/             # ConfigManager, LoggerManager
│   └── main.py                     # Orquestador principal
└── tests/                          # Pruebas unitarias
```

---

## API REST

Una vez levantado el servidor, la documentación interactiva está disponible en:

```
http://localhost:8000/docs
```

---

## Usuarios y roles

| Rol | Responsabilidad |
|-----|----------------|
| **Operador** | Coloca PDFs en `input/pdfs/`, inicia el proceso, resuelve CAPTCHAs manuales |
| **Revisor** | Accede al dashboard para monitorear el estado y descargar reportes |
| **Administrador** | Configura `config/config.json` y gestiona el servidor |

---

## Estados del proceso

| Estado | Descripción |
|--------|-------------|
| `EXITOSO` | Certificado descargado y organizado correctamente |
| `AUTOMATICO` | CAPTCHA resuelto automáticamente |
| `EN_ESPERA` | Esperando resolución manual de CAPTCHA |
| `REINTENTANDO` | Reintento automático en curso |
| `FALLIDO` | Falló después de los reintentos configurados |
| `ERROR_PDF` | No se pudo extraer información del PDF de entrada |

---

## Créditos

Desarrollado para **Risk Consulting Global Group**

- Desarrollador: Franklin Rojas Moreno
- Director: Edward Enrique Paniagua

---

*Sistema en desarrollo activo — V1.0 MVP Técnico*
