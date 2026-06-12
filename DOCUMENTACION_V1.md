# DOCUMENTACIÓN TÉCNICA — AutomatizaciónV1

**Risk Consulting Global Group**
Versión: 1.1
Fecha: Junio 2026
Desarrollador: Franklin Rojas Moreno
Director: Edward Enrique Paniagua

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Módulos y Componentes](#3-módulos-y-componentes)
4. [Flujo de Trabajo del Operador](#4-flujo-de-trabajo-del-operador)
5. [Fuentes Consultadas](#5-fuentes-consultadas)
6. [Estructura de Archivos de Salida](#6-estructura-de-archivos-de-salida)
7. [Usuarios y Roles](#7-usuarios-y-roles)
8. [Estados del Sistema](#8-estados-del-sistema)
9. [Instalación y Configuración](#9-instalación-y-configuración)
10. [Limitaciones y Pendientes V2](#10-limitaciones-y-pendientes-v2)

---

## Changelog

### V1.1 — Junio 2026
- **Columnas de hallazgos en Excel:** se añadieron tres columnas de texto libre (cols 6, 8, 10) que muestran el resultado interpretado del certificado de cada fuente.
- **Flujo CAPTCHA sin terminal:** el operador ya no interactúa con la consola CMD. Resuelve el CAPTCHA en el navegador y confirma desde el dashboard con el botón "✅ CAPTCHA Resuelto — Continuar". La señal se transmite vía `captcha_signal.txt`.
- **Dashboard actualizado:** login con usuarios reales, botón "Limpiar cola", validación de PDFs de Inspektor, estado con tarjetas visuales (sin bloque de log técnico).
- **Integración SharePoint/OneDrive:** `output_folder` puede apuntar a una carpeta sincronizada con OneDrive para que los certificados queden disponibles en SharePoint automáticamente. Script `sync_historial.py` para sincronizar el Excel de historial.

---

## 1. Resumen Ejecutivo

### Qué hace el sistema

AutomatizaciónV1 es un sistema de automatización de escritorio que consulta antecedentes en tres fuentes gubernamentales colombianas (**Procuraduría General de la Nación**, **Policía Nacional** y **Contraloría General — Responsabilidad Fiscal**) a partir de reportes PDF generados por la plataforma **Inspektor**.

El sistema extrae automáticamente los datos de identificación de cada tercero (nombre y documento), navega las páginas web oficiales, gestiona los CAPTCHAs, descarga los certificados PDF y los organiza en carpetas con nomenclatura estándar. Al finalizar genera un reporte consolidado en Excel con el estado de cada consulta y el texto del hallazgo por fuente.

### Problema que resuelve

El proceso manual de consulta de antecedentes por un operador humano toma aproximadamente **20 minutos por tercero**. Con múltiples terceros por ejecución, este tiempo se vuelve inmanejable y propenso a errores de organización de archivos y nomenclatura.

### Beneficios medibles

| Indicador | Manual | Automatizado |
|-----------|--------|--------------|
| Tiempo por tercero | ~20 minutos | ~2–4 minutos (resolución CAPTCHA incluida) |
| Error de nomenclatura | Frecuente | Eliminado (estándar forzado) |
| Trazabilidad | Ninguna | Log completo + Excel acumulado |
| Organización de carpetas | Manual | Automática por tercero |
| Reintentos ante fallo | Ninguno | Hasta 5 pasadas automáticas |
| Hallazgo interpretado | Manual | Extraído automáticamente del PDF |

---

## 2. Arquitectura del Sistema

### Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                      USUARIO / OPERADOR                         │
│                  Navegador  ←→  Dashboard                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP (localhost:8501)
┌──────────────────────────▼──────────────────────────────────────┐
│              DASHBOARD  (dashboard.py + login.py)               │
│                       Streamlit  v1.x                           │
│  Páginas: Inicio | Nueva Consulta | Resultados | Historial      │
│           Sistema (solo admin)                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP (localhost:8000)
┌──────────────────────────▼──────────────────────────────────────┐
│                  API REST  (api/app.py)                         │
│                       FastAPI  v0.x                             │
│  Endpoints: /api/files/upload  /api/files/list                  │
│             /api/automation/run  /api/automation/status         │
│             /api/automation/captcha_confirm                     │
│             /api/reports/data  /api/reports/download            │
│             /api/tercero/pdfs  /api/tercero/pdf                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ subprocess (sin consola visible)
┌──────────────────────────▼──────────────────────────────────────┐
│              MOTOR DE AUTOMATIZACIÓN  (src/main.py)             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  ExtractorPDF → TerceroData → BuscadorRUES (NIT)           │ │
│  │       ↓                                                    │ │
│  │  ConsultorProcuraduria  (CAPTCHA manual → PDF)             │ │
│  │  ConsultorPolicia       (reCAPTCHA manual → PDF generado)  │ │
│  │  ConsultorFiscal        (reCAPTCHA manual → PDF descarga)  │ │
│  │       ↓                                                    │ │
│  │  Renombrador → Organizador → ReporteExcel                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│              Playwright (Chromium/Chrome)                       │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
     input/pdfs/        downloads/ (temp)    output/CONSULTAS_
    (PDFs Inspektor)    (descargas           AUTOMATIZADAS/
                         navegador)          + reports/
                                             + logs/
```

### Flujo completo del proceso

```
1. Operador coloca PDFs en input/pdfs/
          ↓
2. Dashboard → "Iniciar Automatización" → POST /api/automation/run
          ↓
3. API lanza subprocess sin ventana de consola (src/main.py)
   y escribe captcha_signal.txt vacío
          ↓
4. main.py carga config.json e inicia navegador Chromium (headless=false)
          ↓
5. Por cada PDF en input/pdfs/:
    a. ExtractorPDF extrae nombre + documento + tipo (CC o NIT)
    b. Si NIT: BuscadorRUES completa el dígito de verificación vía RUES
    c. Verifica en Excel si ya fue procesado (skip) o está PARCIAL (reintento)
    d. Nuevo tercero: consulta las 3 fuentes (CC) o 2 fuentes (NIT)
         - Procuraduría: el sistema pre-rellena el formulario y espera que
           el operador resuelva el CAPTCHA en el navegador y confirme en el dashboard
         - Policía (solo CC): el operador resuelve el reCAPTCHA en el navegador
           y confirme en el dashboard
         - Fiscal: ídem Policía
       Confirmación: operador hace clic en "✅ CAPTCHA Resuelto — Continuar"
       → dashboard llama POST /api/automation/captcha_confirm
       → API escribe "CONFIRMED" en captcha_signal.txt
       → motor lee el archivo y continúa
    e. Archivo descargado → extracción de hallazgo (pdfplumber) → Renombrador
       → Organizador (mueve a carpeta tercero)
    f. Actualiza Excel inmediatamente (crash safety)
    g. Si completo: mueve PDF de entrada a input/pdfs/procesados/
          ↓
6. Pasadas de reintento (hasta 4) para terceros PARCIALES del run actual
          ↓
7. Genera/actualiza reports/resultado_consultas.xlsx final
          ↓
8. Dashboard muestra resultados en tiempo real vía /api/reports/data
```

### Tecnologías utilizadas

| Tecnología | Versión | Uso |
|------------|---------|-----|
| Python | 3.11+ | Lenguaje base |
| Playwright | latest | Automatización del navegador |
| Google Chrome | latest | Navegador de automatización |
| FastAPI | latest | API REST backend |
| Streamlit | latest | Dashboard de monitoreo |
| openpyxl | latest | Generación de reportes Excel |
| pandas | latest | Filtros en historial del dashboard |
| httpx | latest | Cliente HTTP del dashboard |
| pdfplumber | latest | Extracción de texto de PDFs Inspektor y certificados |

---

## 3. Módulos y Componentes

### Backend (`src/`)

#### `src/main.py` — Orquestador principal
Punto de entrada del motor de automatización. Coordina el flujo completo:
- Inicialización de carpetas y logger
- Carga de PDFs de entrada
- Gestión de estados previos (Excel historial)
- Enriquecimiento de NIT via RUES
- Bucle de procesamiento por tercero
- Pasadas de reintento post-loop
- Generación de reporte final

**Lógica de reanudación:** Al iniciar, lee el Excel existente. Si un tercero aparece como `EXITOSO`, se omite. Si aparece como `PARCIAL`, solo reintenta las fuentes fallidas.

#### `src/consultores/`

| Módulo | Fuente | Estrategia CAPTCHA | Tipo de descarga |
|--------|--------|--------------------|------------------|
| `procuraduria.py` | Procuraduría | Manual (operador escribe en el navegador, confirma en dashboard) | `expect_download()` sobre botón Descargar |
| `policia.py` | Policía Nacional | reCAPTCHA manual, confirma en dashboard | `page.pdf()` (PDF generado desde el resultado HTML) |
| `fiscal.py` | Contraloría Fiscal | reCAPTCHA manual, confirma en dashboard | `expect_download()` sobre botón Buscar |

Todos heredan de `src/core/base_consultor.py` (Strategy Pattern), que define el Template Method:
`_navegar()` → `_ingresar_datos()` → `_resolver_captcha()` → `_descargar_certificado()`

**Mecanismo de señal CAPTCHA:** Cada consultor llama a `_esperar_confirmacion_captcha()`, que escribe `captcha_signal.txt` vacío y hace polling cada 0.5 s. El motor continúa cuando lee `"CONFIRMED"` en ese archivo (timeout: 5 minutos). La API escribe `"CONFIRMED"` al recibir `POST /api/automation/captcha_confirm` desde el dashboard.

#### `src/services/`

| Módulo | Responsabilidad |
|--------|----------------|
| `extractor_pdf.py` | Extrae nombre completo y número de documento de los PDFs de Inspektor |
| `organizador.py` | Crea carpetas por tercero y mueve archivos al destino final |
| `renombrador.py` | Aplica la convención de nombres estándar (PRO/POL/RFIS) |
| `reporte_excel.py` | Genera y actualiza `resultado_consultas.xlsx` con historial acumulado y columnas de hallazgo |
| `captcha_solver.py` | Resolución automática de CAPTCHA de texto (reservado para futuro) |
| `notificador.py` | Alertas por correo / Teams (configurable en config.json) |
| `buscador_rues.py` | Consulta RUES para completar dígito de verificación de NIT |
| `validador_nit.py` | Limpia y normaliza formato de NIT |

#### `src/core/`

| Módulo | Responsabilidad |
|--------|----------------|
| `base_consultor.py` | Clase abstracta base (Strategy). Define el flujo Template Method común a todas las fuentes |
| `retry_handler.py` | Lógica de reintentos con backoff configurable. Hasta `retry_attempts` por fuente |

#### `src/models/`

| Módulo | Contenido |
|--------|-----------|
| `tercero.py` | `TerceroData` (dataclass: nombre, documento, tipo), `ResultadoFuente`, `ResultadoTercero`, `EstadoFuente` (enum) |

#### `src/infrastructure/`

| Módulo | Responsabilidad |
|--------|----------------|
| `config_manager.py` | Singleton que carga y expone `config.json`. Provee `Path` resueltos para todas las carpetas |
| `logger_manager.py` | Singleton de logging centralizado. Escribe en `ejecucion.log`, `errores.log` y `resumen.csv` |

---

### API REST (`api/app.py`)

Servidor **FastAPI** en `http://localhost:8000`. Actúa como intermediario entre el Dashboard y el motor de automatización.

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/files/upload` | Sube un PDF a `input/pdfs/` |
| `GET` | `/api/files/list` | Lista PDFs en `input/pdfs/` (nombre + KB) |
| `POST` | `/api/automation/run` | Lanza `src/main.py` como subprocess sin consola visible; inicializa `captcha_signal.txt` |
| `GET` | `/api/automation/status` | Estado del proceso (`idle` / `running` / `done` / `error`) |
| `POST` | `/api/automation/captcha_confirm` | Escribe `"CONFIRMED"` en `captcha_signal.txt` para liberar al motor |
| `GET` | `/api/reports/data` | Retorna todas las filas del Excel como JSON |
| `GET` | `/api/reports/download` | Descarga directa del Excel |
| `GET` | `/api/tercero/pdfs` | Lista PDFs de una carpeta de tercero en `output/CONSULTAS_AUTOMATIZADAS/` |
| `GET` | `/api/tercero/pdf` | Descarga un PDF específico de un tercero |

Documentación interactiva Swagger disponible en `http://localhost:8000/docs`.

**Nota de seguridad:** El endpoint `/api/tercero/pdf` valida que el path solicitado esté dentro de `output/CONSULTAS_AUTOMATIZADAS/` mediante resolución canónica, previniendo path traversal.

---

### Dashboard (`dashboard.py` + `login.py`)

Interfaz web **Streamlit** en `http://localhost:8501`.

#### Pantalla de login (`login.py`)
- Fondo azul oscuro corporativo (`#1B2A4A`)
- Formulario centrado con logo shield
- Autenticación contra diccionario `_USERS` en memoria (ver [Sección 7](#7-usuarios-y-roles))
- Establece `session_state` con usuario, nombre, rol y página inicial

#### Páginas del dashboard

| Página | Ruta | Descripción | Roles con acceso |
|--------|------|-------------|-----------------|
| Inicio | `home` | Métricas resumen (PDFs en cola, exitosos, pendientes, fallidos) + últimas 10 consultas | Todos |
| Nueva Consulta | `nueva_consulta` | Upload de PDFs con validación de nombre Inspektor + botón limpiar cola + inicio de automatización + estado con tarjetas visuales | Todos |
| Resultados | `resultados` | Tabla completa con semáforo de colores + hallazgos por fuente + descarga Excel + documentos por tercero | Todos |
| Historial | `historial` | Tabla filtrable (nombre, tipo doc, estado, fecha) + descarga PDFs por tercero | Supervisor, Admin |
| Sistema | `sistema` | Log en tiempo real + gestión visual de usuarios | Solo Admin |

#### Funcionalidades de la página Nueva Consulta

**Validación de PDFs de Inspektor:** al subir un archivo, el dashboard verifica que el nombre contenga alguna de las palabras clave `reporte`, `consulta`, `inspektor`, `individual` o `servicios`. Si no coincide, muestra una advertencia (`⚠️ Este archivo puede no ser un reporte de Inspektor`) sin bloquear la carga.

**Botón Limpiar cola:** elimina todos los PDFs de `input/pdfs/` con un paso de confirmación para evitar borrados accidentales.

**Estado actual:** muestra una tarjeta visual coloreada según el estado del proceso. No expone el log técnico al operador.

| Estado | Icono | Color | Descripción visible |
|--------|-------|-------|---------------------|
| `idle` | ⏸ | Gris | Sin proceso activo |
| `running` | 🔄 | Azul | Procesando... |
| `done` | ✅ | Verde | Proceso completado |
| `error` | ❌ | Rojo | Ocurrió un error |

**Botón CAPTCHA (solo aparece cuando `status = running`):**

```
🌐 El navegador está abierto. Resuelva el CAPTCHA en el
   navegador y luego confirme aquí.

[✅  CAPTCHA Resuelto — Continuar]
```

Al hacer clic en ese botón, el dashboard llama a `POST /api/automation/captcha_confirm`. La API escribe `"CONFIRMED"` en `captcha_signal.txt`, y el motor continúa el procesamiento.

#### Código de colores en tablas

| Color | Estado(s) |
|-------|-----------|
| Verde (`#C6EFCE`) | EXITOSO, AUTOMATICO |
| Amarillo (`#FFEB9C`) | PARCIAL, EN_ESPERA, REINTENTANDO |
| Naranja (`#FCE4D6`) | NO_ENCONTRADO |
| Rojo (`#FFC7CE`) | FALLIDO, FALLIDO_TOTAL, ERROR_PDF |
| Gris (`#E9ECEF`) | PENDIENTE |

---

### Configuración (`config/config.json`)

Archivo centralizado que controla todos los parámetros del motor. Gestionado por `ConfigManager` (Singleton).

---

## 4. Flujo de Trabajo del Operador

### Paso a paso completo

**Preparación:**

1. Exportar el reporte desde la plataforma Inspektor en formato PDF.
2. Acceder al Dashboard en `http://localhost:8501` (si el sistema ya está corriendo) o ejecutar `start.bat`.
3. Iniciar sesión con usuario y contraseña asignados.

**Carga de archivos:**

4. Ir a la página **Nueva Consulta**.
5. En la sección "1. Cargar PDFs", seleccionar uno o varios PDFs de Inspektor.
6. Hacer clic en **⬆️ Subir archivos**. Aparecerán listados en "Archivos en cola".
   - Si el nombre del PDF no coincide con el formato de Inspektor, aparecerá una advertencia amarilla. Verificar el archivo antes de continuar.
   - Para borrar los archivos en cola antes de iniciar, usar el botón **🗑️ Limpiar cola** (requiere confirmación).

**Inicio del proceso:**

7. En la sección "2. Iniciar proceso", leer el aviso: *"El proceso iniciará en segundo plano. Cuando aparezca el navegador, resuelva el CAPTCHA y haga clic en Confirmar CAPTCHA resuelto."*
8. Hacer clic en **▶ Iniciar Automatización**. El motor arranca en segundo plano; no se abre ninguna ventana de consola. El navegador Chrome sí se abre y es visible.

**Manejo de CAPTCHAs (en el navegador + dashboard):**

> El sistema pausa automáticamente y espera la confirmación del operador en el dashboard. No hay consola ni tecla ENTER — todo se gestiona desde el navegador.

9. **Procuraduría** — Para cada tercero:
   - El motor navega al formulario, pre-rellena tipo y número de documento y espera.
   - En el dashboard aparece la tarjeta azul 🔄 con el aviso de CAPTCHA y el botón **✅ CAPTCHA Resuelto — Continuar**.
   - El operador escribe la respuesta del CAPTCHA en el campo del navegador.
   - Hacer clic en **✅ CAPTCHA Resuelto — Continuar** en el dashboard para que el motor continúe.

10. **Policía Nacional** — Para cada tercero con CC:
    - El motor navega al formulario, acepta los términos automáticamente y espera.
    - El operador completa el reCAPTCHA de Google en el navegador y espera que el botón **CONSULTAR** quede activo.
    - Hacer clic en **✅ CAPTCHA Resuelto — Continuar** en el dashboard.

11. **Contraloría Fiscal** — Para cada tercero:
    - El motor navega al formulario y espera.
    - El operador completa el reCAPTCHA de Google en el navegador.
    - Hacer clic en **✅ CAPTCHA Resuelto — Continuar** en el dashboard.

**Monitoreo:**

12. En el Dashboard, página **Nueva Consulta**, sección "Estado actual", la tarjeta cambia de color según el avance (🔄 procesando → ✅ completado).
13. Activar **"Auto 3s"** para refrescar automáticamente cada 3 segundos.

**Finalización:**

14. Cuando el motor termina, la tarjeta cambia a `✅ Proceso completado`.
15. Ir a la página **Resultados** para ver la tabla con semáforos de color y los hallazgos por fuente.
16. Descargar el Excel con **⬇️ Descargar Excel**.
17. En la sección **Documentos por Tercero**, expandir cada tarjeta para ver y descargar los PDFs individuales.
18. Los certificados organizados también están en `output/CONSULTAS_AUTOMATIZADAS/` (o en SharePoint si `output_folder` apunta a una carpeta sincronizada con OneDrive).

### Qué hacer cuando falla

| Situación | Acción |
|-----------|--------|
| Estado `PARCIAL` en el Excel | Volver a ejecutar — el sistema detecta automáticamente las fuentes incompletas y solo las reintenta |
| Estado `FALLIDO_TOTAL` | Volver a ejecutar — se reprocesa desde cero |
| PDF de Inspektor en `input/pdfs/` tras un error | Es normal — el archivo solo se mueve a `procesados/` cuando el tercero queda completo |
| El Excel está abierto en Excel al guardar | La consola pedirá cerrar el archivo y presionar ENTER |
| `ERROR_PDF` en una fila | El PDF de Inspektor no pudo ser leído. Verificar que no esté protegido o corrupto |
| Navegador cierra solo | Revisar `logs/errores.log` para identificar la causa. Volver a ejecutar |
| Botón CAPTCHA no aparece en el dashboard | Verificar que el proceso esté en estado `running` y que la API esté activa (`http://localhost:8000/docs`) |
| Motor espera CAPTCHA pero no hay reCAPTCHA visible | Hacer clic en el botón igualmente — el motor verificará y continuará si no había CAPTCHA |

---

## 5. Fuentes Consultadas

### Procuraduría General de la Nación

| Campo | Detalle |
|-------|---------|
| URL | `https://apps.procuraduria.gov.co/webcert/inicio.aspx?tpo=2` |
| Campos del formulario | Tipo documento (`select#ddlTipoID`) + Número (`input#txtNumID`) |
| Tipos de documento soportados | CC (valor `"1"`), NIT (valor `"2"`) |
| Tipo de CAPTCHA | CAPTCHA de texto manual (matemático o geográfico) |
| Estrategia | Operador escribe respuesta en el navegador → clic en "✅ CAPTCHA Resuelto — Continuar" en el dashboard |
| Flujo post-CAPTCHA | Clic "Generar" → navega a `verpdf.aspx` → clic "Descargar" → `expect_download()` |
| Resultado | PDF oficial descargado desde el servidor |
| Caso "no encontrado" | El sistema detecta el texto `"NO SE ENCUENTRA REGISTRADO"` y marca `NO_ENCONTRADO` (sin reintentar) |
| Estado en Excel | `AUTOMATICO` (exitoso) o `NO_ENCONTRADO` |

### Policía Nacional — Antecedentes Judiciales

| Campo | Detalle |
|-------|---------|
| URL | `https://antecedentes.policia.gov.co:7005/WebJudicial/index.xhtml` |
| Flujo de navegación | Acepta términos (radio "Acepto" + botón "Enviar") → formulario de datos |
| Campos del formulario | Tipo documento (`select#cedulaTipo`, valor `"cc"`) + Número (`input#cedulaInput`) |
| Tipos de documento soportados | Solo CC (Persona Natural) |
| Tipo de CAPTCHA | reCAPTCHA Google |
| Estrategia | Operador resuelve reCAPTCHA en navegador, espera botón Consultar activo → clic en "✅ CAPTCHA Resuelto — Continuar" en el dashboard |
| Flujo post-CAPTCHA | Clic "Consultar" → espera URL con `formAntecedentes.xhtml` → `page.pdf()` |
| Resultado | PDF generado desde el HTML de resultado (no descargado del servidor) |
| Aplica para | Solo personas con Cédula de Ciudadanía (CC). Los NIT se marcan `NO APLICA` |
| Estado en Excel | `EXITOSO` o `NO APLICA` |

### Contraloría General — Responsabilidad Fiscal

| Campo | Detalle |
|-------|---------|
| URL Persona Natural | `https://cfiscal.contraloria.gov.co/Certificados/CertificadoPersonaNatural.aspx` |
| URL Persona Jurídica | `https://cfiscal.contraloria.gov.co/Certificados/CertificadoPersonaJuridica.aspx` |
| Selección de URL | Automática según `tipo_documento` del tercero (`CC` → Natural, `NIT` → Jurídica) |
| Campos del formulario | Tipo documento (`select#ddlTipoDocumento`, solo CC) + Número (`input#txtNumeroDocumento`) |
| Tipos de documento soportados | CC y NIT |
| Tipo de CAPTCHA | reCAPTCHA Google |
| Estrategia | Operador resuelve reCAPTCHA → clic en "✅ CAPTCHA Resuelto — Continuar" en el dashboard |
| Flujo post-CAPTCHA | Clic "Buscar" → `expect_download()` |
| Resultado | PDF descargado directamente desde el servidor |
| Caso NIT inválido | Detecta indicadores de error en el HTML (`NIT DE EXACTAMENTE 10`, `SOLICÍTELO AL CORREO`) → marca `NO_ENCONTRADO` |
| Estado en Excel | `EXITOSO` o `NO_ENCONTRADO` |

---

## 6. Estructura de Archivos de Salida

### Nomenclatura de carpetas de tercero

```
output/CONSULTAS_AUTOMATIZADAS/[Nombre completo] [Tipo Doc] [Número]/
```

**Ejemplos:**
```
output/CONSULTAS_AUTOMATIZADAS/JUAN CARLOS PEREZ GOMEZ CC 12345678/
output/CONSULTAS_AUTOMATIZADAS/EMPRESA EJEMPLO SAS NIT 9001234567/
```

### Nomenclatura de PDFs de certificado

| Fuente | Prefijo | Formato completo | Ejemplo |
|--------|---------|-----------------|---------|
| Procuraduría | `PRO` | `PRO [Nombre completo] CC [Cédula].pdf` | `PRO JUAN CARLOS PEREZ GOMEZ CC 12345678.pdf` |
| Policía Nacional | `POL` | `POL [Nombre completo] CC [Cédula].pdf` | `POL JUAN CARLOS PEREZ GOMEZ CC 12345678.pdf` |
| Responsabilidad Fiscal | `RFIS` | `RFIS [Nombre completo] CC [Cédula].pdf` | `RFIS JUAN CARLOS PEREZ GOMEZ CC 12345678.pdf` |

**Para Persona Jurídica (NIT):**
```
PRO  EMPRESA EJEMPLO SAS NIT 9001234567.pdf
RFIS EMPRESA EJEMPLO SAS NIT 9001234567.pdf
```
*(Policía no aplica para NIT)*

### Estructura del reporte Excel (`reports/resultado_consultas.xlsx`)

Hoja: **Consultas** — Encabezados en azul oscuro (`#1F3864`), texto blanco.
Las columnas de estado de fuente tienen fondo de color según el estado general del tercero.
Las columnas de hallazgo tienen fondo blanco y texto ajustado con ajuste de línea.

| # | Columna | Descripción | Ancho |
|---|---------|-------------|-------|
| 1 | **Cédula** | Número de documento del tercero | 15 |
| 2 | **Tipo Doc** | `CC` o `NIT` | 10 |
| 3 | **Nombre** | Nombre completo del tercero | 40 |
| 4 | **Tipo Persona** | `Persona Natural` o `Persona Jurídica` | 18 |
| 5 | **Procuraduría** | Estado de la consulta en Procuraduría | 15 |
| 6 | **Hallazgo Procuraduría** | Texto interpretado del certificado de Procuraduría | 55 |
| 7 | **Policía** | Estado de la consulta en Policía (`NO APLICA` para NIT) | 12 |
| 8 | **Hallazgo Policía** | Texto interpretado del certificado de Policía | 55 |
| 9 | **Fiscal** | Estado de la consulta en Contraloría Fiscal | 12 |
| 10 | **Hallazgo Fiscal** | Texto interpretado del certificado Fiscal | 55 |
| 11 | **Estado** | Estado general del tercero (calculado) | 15 |
| 12 | **Fecha** | Fecha de la primera consulta (`dd/mm/aa`) | 12 |
| 13 | **Número de intentos** | Cantidad de ejecuciones que procesaron este tercero | 10 |
| 14 | **Fecha segunda validación** | Fecha y hora de la última actualización (`dd/mm/aa HH:MM`) | 18 |
| 15 | **Observacion** | Mensajes de error detallados por fuente (hasta 80 caracteres por fuente) | 50 |
| 16 | **NIT Inspektor** | Los 9 dígitos base del NIT (solo Persona Jurídica) | 12 |
| 17 | **Dígito verificación** | Dígito de verificación del NIT (posición 10) | 20 |
| 18 | **NIT completo** | NIT completo de 10 dígitos | 15 |

### Valores posibles en columnas de Hallazgo

Las columnas de hallazgo se llenan automáticamente usando `pdfplumber` sobre el certificado descargado. Solo se asigna valor cuando la descarga fue exitosa.

#### Hallazgo Procuraduría (col 6)

| Valor | Condición |
|-------|-----------|
| `NO REGISTRA SANCIONES NI INHABILIDADES VIGENTES` | El certificado contiene `"NO REGISTRA SANCIONES"` |
| `REGISTRA SANCIONES O INHABILIDADES VIGENTES` | El certificado contiene `"REGISTRA SANCIONES"` (sin prefijo negativo) |
| `NO SE ENCUENTRA REGISTRADO EN EL SISTEMA` | Número no encontrado en Procuraduría, o no se pudo leer el PDF |

#### Hallazgo Policía (col 8)

| Valor | Condición |
|-------|-----------|
| `NO TIENE ASUNTOS PENDIENTES CON LAS AUTORIDADES JUDICIALES` | El certificado contiene `"NO TIENE ASUNTOS PENDIENTES"` |
| `ACTUALMENTE NO ES REQUERIDO POR AUTORIDAD JUDICIAL` | El certificado contiene `"NO ES REQUERIDO"` |
| *(vacío)* | No se pudo extraer texto del PDF generado |
| `NO APLICA` | Tercero con NIT (Persona Jurídica) |

#### Hallazgo Fiscal (col 10)

| Valor | Condición |
|-------|-----------|
| `NO SE ENCUENTRA REPORTADO COMO RESPONSABLE FISCAL` | El certificado contiene `"NO SE ENCUENTRA REPORTADO"` |
| `SE ENCUENTRA REPORTADO COMO RESPONSABLE FISCAL` | El certificado contiene `"SE ENCUENTRA REPORTADO"` (sin prefijo negativo) |
| `NO SE ENCUENTRA REGISTRADO EN EL SISTEMA` | NIT inválido, número no encontrado, o no se pudo leer el PDF |

**Cálculo del Estado general:**

- **EXITOSO**: Todas las fuentes aplicables terminaron en `EXITOSO`, `AUTOMATICO` o `NO_ENCONTRADO`
- **PARCIAL**: Al menos una fuente terminó pero otras están pendientes o fallidas
- **FALLIDO_TOTAL**: Ninguna fuente terminó exitosamente

El color de cada fila refleja el estado general usando la paleta de semáforos descrita en la sección de arquitectura.

---

## 7. Usuarios y Roles

### Tabla de usuarios activos

| Usuario | Nombre completo | Rol | Contraseña |
|---------|----------------|-----|-----------|
| `franklin.rojas` | Franklin Rojas Moreno | Administrador | `Risk2026*` |
| `edward.paniagua` | Edward Enrique Paniagua | Supervisor | `Risk2026*` |
| `consultor` | Consultor RiskGC | Consultor | `Consul2026*` |

> **Nota de seguridad:** Las credenciales están en texto plano en `login.py`. En V1.1 se migrará a una base de datos con hashing de contraseñas.

### Permisos por rol

| Página / Acción | Consultor | Supervisor | Administrador |
|-----------------|-----------|------------|---------------|
| Inicio | ✅ | ✅ | ✅ |
| Nueva Consulta (subir PDFs + iniciar) | ✅ | ✅ | ✅ |
| Resultados (ver + descargar Excel + PDFs) | ✅ | ✅ | ✅ |
| Historial (filtros + descarga por tercero) | ❌ | ✅ | ✅ |
| Sistema (log + gestión usuarios) | ❌ | ❌ | ✅ |

---

## 8. Estados del Sistema

### Tabla de todos los estados posibles

| Estado | Scope | Color en tabla | Descripción |
|--------|-------|---------------|-------------|
| `EXITOSO` | Fuente y General | Verde | Certificado descargado y organizado correctamente |
| `AUTOMATICO` | Fuente | Verde | Específico de Procuraduría. CAPTCHA resuelto y descarga completada |
| `PARCIAL` | General | Amarillo | Algunas fuentes completadas, otras pendientes o fallidas |
| `EN_ESPERA` | Fuente | Amarillo | Proceso pausado esperando resolución manual de CAPTCHA |
| `REINTENTANDO` | Fuente | Amarillo | Reintento automático en curso (dentro del `RetryHandler`) |
| `NO_ENCONTRADO` | Fuente | Naranja | Número de identificación no figura en la base de datos consultada. Para CC se considera terminal válido; para NIT en Fiscal el tercero queda en PARCIAL |
| `FALLIDO` | Fuente | Rojo | Fuente falló tras los reintentos configurados |
| `FALLIDO_TOTAL` | General | Rojo | Todas las fuentes fallaron — ningún certificado obtenido |
| `ERROR_PDF` | General | Rojo | No se pudo extraer información del PDF de entrada (corrupto, protegido o formato no reconocido) |
| `PENDIENTE` | Fuente | Gris | Estado inicial antes de la consulta; también indica "en espera" para fuentes no iniciadas aún |
| `NO APLICA` | Fuente | Gris | Consulta a Policía para un tercero con NIT (Persona Jurídica). No corresponde consultarla |

### Lógica de reanudación entre ejecuciones

```
Estado en Excel → Comportamiento en la siguiente ejecución
─────────────────────────────────────────────────────────
EXITOSO          → Se omite completamente (skip)
AUTOMATICO       → Se omite completamente (skip)
PARCIAL          → Solo se reintentan las fuentes no terminadas
FALLIDO_TOTAL    → Se reprocesa desde cero (todas las fuentes)
ERROR_PDF        → Se reintenta extraer el PDF
```

---

## 9. Instalación y Configuración

### Requisitos del sistema

| Componente | Versión mínima |
|------------|---------------|
| Python | 3.11+ |
| Google Chrome | Última versión estable |
| Sistema operativo | Windows 10/11 (producción) o Ubuntu 20.04+ |
| RAM | 4 GB (recomendado 8 GB) |
| Conexión a internet | Requerida durante la ejecución |

### Dependencias Python

```
playwright
pdfplumber
openpyxl
pandas
fastapi
uvicorn
streamlit
httpx
```

### Pasos de instalación

**1. Clonar el repositorio**
```bash
git clone https://github.com/frojasinfo-hub/Automatizaci-n-validaci-n-de-reportes.git
cd Automatizaci-n-validaci-n-de-reportes
```

**2. Instalar dependencias Python**
```bash
pip install -r requirements.txt
```

**3. Instalar el navegador Chromium para Playwright**
```bash
playwright install chromium
```

**4. Configurar variables de entorno (opcional)**
```bash
cp .env.example .env
# Editar si se requiere cambiar puertos o carpetas
```

**5. Ajustar la configuración**

Editar `config/config.json` según el entorno (ver tabla siguiente).

**6. Iniciar el sistema**

En Windows:
```bat
start.bat
```

En Linux/Mac:
```bash
chmod +x start.sh && ./start.sh
```

Esto levanta la API en `http://localhost:8000` y el Dashboard en `http://localhost:8501`.

### Variables de configuración en `config/config.json`

| Parámetro | Tipo | Valor actual | Descripción |
|-----------|------|-------------|-------------|
| `input_folder` | string | `"input/pdfs"` | Carpeta donde el operador coloca los PDFs de Inspektor |
| `download_folder` | string | `"downloads"` | Carpeta temporal de descargas del navegador |
| `output_folder` | string | `"output/CONSULTAS_AUTOMATIZADAS"` | Carpeta de salida de certificados organizados. Puede apuntarse a una carpeta sincronizada con OneDrive para integración automática con SharePoint |
| `logs_folder` | string | `"logs"` | Carpeta de logs (`ejecucion.log`, `errores.log`, `resumen.csv`) |
| `reports_folder` | string | `"reports"` | Carpeta del Excel de resultados |
| `retry_attempts` | int | `1` | Número de reintentos por fuente ante fallo |
| `retry_wait_sec` | int | `30` | Segundos de espera entre reintentos |
| `timeout_sec` | int | `60` | Timeout general para operaciones del navegador (en segundos) |
| `headless` | bool | `false` | `false` = navegador visible (requerido para CAPTCHAs manuales); `true` = sin interfaz gráfica |
| `notify_email` | bool | `false` | Activar notificaciones por correo |
| `notify_teams` | bool | `false` | Activar notificaciones por Microsoft Teams |
| `email.smtp_host` | string | `""` | Servidor SMTP para notificaciones |
| `email.smtp_port` | int | `587` | Puerto SMTP |
| `email.sender` | string | `""` | Correo remitente |
| `email.password` | string | `""` | Contraseña del correo remitente |
| `email.recipients` | array | `[]` | Lista de destinatarios de notificaciones |
| `teams.webhook_url` | string | `""` | URL del webhook de Microsoft Teams |

> **Importante:** `headless` debe permanecer en `false` en todo entorno donde los operadores resuelvan CAPTCHAs. Cambiarlo a `true` solo tiene sentido para fuentes que no requieran intervención manual.

### Integración con SharePoint / OneDrive

Los certificados se pueden publicar automáticamente en SharePoint apuntando `output_folder` en `config.json` a una carpeta local sincronizada por el cliente de OneDrive:

```json
"output_folder": "C:/Users/<usuario>/OneDrive - Risk Consulting/CONSULTAS_AUTOMATIZADAS"
```

El cliente de OneDrive sincroniza la carpeta en tiempo real con la biblioteca de SharePoint correspondiente. No se requiere ningún cambio en el código del motor.

**Script `sync_historial.py`:** utilidad independiente que copia el Excel `resultado_consultas.xlsx` al destino de SharePoint/OneDrive configurado. Se puede ejecutar manualmente o programar en el Programador de tareas de Windows después de cada ejecución.

---

## 10. Limitaciones y Pendientes V2

### Limitaciones de V1 (MVP Técnico)

| Limitación | Descripción |
|-----------|-------------|
| **CAPTCHA de Policía y Fiscal: manual desde el dashboard** | El operador resuelve el reCAPTCHA en el navegador Chrome y confirma el dashboard. No es posible automatizarlo sin un servicio externo de resolución de reCAPTCHA |
| **CAPTCHA de Procuraduría: manual desde el navegador** | El operador escribe la respuesta del CAPTCHA de texto directamente en el formulario del navegador y confirma en el dashboard |
| **No funciona en la nube** | Requiere Chrome visible en la misma máquina. Los CAPTCHAs manuales no son compatibles con servidores headless remotos sin acceso GUI |
| **Despliegue pendiente aprobación gerencia TI** | El sistema está validado técnicamente. Su puesta en producción en equipos de la empresa requiere aprobación formal del área de TI |
| **Credenciales en texto plano** | Los usuarios del dashboard están hardcodeados en `login.py` sin hashing ni base de datos |
| **Un solo proceso activo** | La API solo rastrea un proceso `subprocess` a la vez. No hay soporte para ejecuciones paralelas |
| **Sin gestión de usuarios** | No hay interfaz para agregar, editar o desactivar usuarios sin modificar el código fuente |
| **Notificaciones no implementadas** | Los parámetros `notify_email` y `notify_teams` existen en config.json pero el módulo `notificador.py` está preparado para futura implementación |
| **Sin autenticación en la API** | Los endpoints de FastAPI no requieren token ni sesión. Están protegidos solo por ser locales (`localhost`) |
| **Logs no persistentes entre reinicios** | `LoggerManager` reinicia el conteo en cada ejecución. El historial completo está en el Excel pero no en un log de auditoría centralizado |
| **Extractor PDF acoplado a Inspektor** | `ExtractorPDF` está diseñado para el formato específico de Inspektor. Otros proveedores de reportes requerirían un nuevo extractor |

### Mejoras planificadas para V2

| Mejora | Prioridad | Descripción |
|--------|-----------|-------------|
| Autenticación con base de datos | Alta | Migrar usuarios a SQLite/PostgreSQL con contraseñas hasheadas (bcrypt) y JWT |
| Panel de administración de usuarios | Alta | CRUD de usuarios desde el Dashboard sin tocar código |
| Soporte multi-proceso | Media | Cola de trabajos para procesar múltiples lotes en paralelo |
| Resolución automática de reCAPTCHA | Media | Integración con servicio externo (2captcha, Anti-Captcha) para Policía y Contraloría |
| Notificaciones funcionales | Media | Implementar completamente el módulo `notificador.py` para email y Teams |
| API con autenticación | Media | Agregar Bearer Token o API Key a todos los endpoints de FastAPI |
| Soporte multi-fuente extensible | Baja | Registro dinámico de nuevas fuentes sin modificar `main.py` |
| Dashboard en la nube | Baja | Requiere resolver primero la automatización sin CAPTCHAs manuales (RPA cloud o resolución automática) |
| Extractor PDF genérico | Baja | Configuración de reglas de extracción por proveedor de reportes |

---

*AutomatizaciónV1 © 2026 — Risk Consulting Global Group — Uso exclusivo corporativo*
