# Dashboard Regional Chile 🇨🇱

Dashboard interactivo de indicadores regionales para las 16 regiones de Chile, desarrollado para la División de Coordinación Interministerial del Ministerio del Interior.

## 🌐 Ver el dashboard

**[👉 Abrir Dashboard](https://manuelcarvallo97-tech.github.io/dashboard-regional-chile/dashboard.html)**

> Actualizado automáticamente cada vez que se sube un nuevo `dashboard.html`

---

## 📊 Módulos disponibles

| Módulo | Fuente | Frecuencia | Cobertura |
|--------|--------|------------|-----------|
| 🛡 Seguridad Pública | Carabineros · LeyStop | Semanal | 2026 |
| 📈 PIB Regional | Banco Central de Chile | Trimestral / Anual | 2010–2024 |
| 💼 Empleo | Banco Central de Chile / INE | Mensual | 2010–2026 |
| 🏘 Censo 2024 | INE Chile | Puntual | 2024 |

---

## 🗂 Estructura del repositorio

```
📁 raíz del repositorio
├── dashboard.html          ← Dashboard principal (se abre en GitHub Pages)
├── README.md               ← Este archivo
│
├── 📁 scripts/             ← Scripts Python de descarga y generación
│   ├── bce_api.py          ← Descarga PIB desde API Banco Central
│   ├── bce_empleo.py       ← Descarga empleo regional desde API BCE
│   ├── bcn_scraper.py      ← Scraping indicadores BCN SIIT
│   ├── limpiar_datos.py    ← Limpieza y normalización de datos
│   ├── leystop_scraper.py  ← Scraping seguridad desde LeyStop
│   └── generar_dashboard.py← Genera dashboard.html desde SQLite
│
├── 📁 data/                ← Archivos de datos procesados
│   └── censo_regiones.json ← Datos Censo 2024 procesados
│
└── 📁 docs/                ← Documentación adicional (opcional)
```

---

## 🚀 Cómo actualizar el dashboard

### Opción A — Subir solo el HTML (más simple)

1. Corre los scrapers que necesites actualizar:
   ```bash
   python scripts/bce_empleo.py        # Actualiza empleo
   python scripts/leystop_scraper.py   # Actualiza seguridad
   ```

2. Regenera el dashboard:
   ```bash
   python scripts/generar_dashboard.py
   ```

3. Sube `dashboard.html` a GitHub:
   - Ve a tu repositorio en github.com
   - Arrastra el archivo `dashboard.html` al repositorio
   - Haz clic en **Commit changes**
   - En ~1 minuto el sitio se actualiza automáticamente

### Opción B — GitHub Desktop (recomendado)

1. Instala [GitHub Desktop](https://desktop.github.com/)
2. Clona este repositorio
3. Copia los archivos actualizados a la carpeta local
4. En GitHub Desktop: **Commit** → **Push origin**

---

## ⚙️ Instalación local

### Requisitos
- Python 3.10 o superior
- Las siguientes librerías:

```bash
pip install pandas requests selenium webdriver-manager python-dotenv
```

### Credenciales (archivo `env.local`)

Crea un archivo `env.local` en la carpeta `Scrap` con:

```
BDE_USER=tu@email.cl          # Usuario API Banco Central
BDE_PASS=tucontraseña         # Contraseña API Banco Central
USER=12345678                  # RUT sin puntos ni dígito verificador (para ADIS)
PASS=tucontraseña             # Contraseña ADIS
```

> ⚠️ **Nunca subas `env.local` o `bcn_indicadores.db` a GitHub** (ya están en `.gitignore`)

### Ejecución completa desde cero

```bash
# 1. Descargar datos BCE (PIB)
python scripts/bce_api.py

# 2. Descargar empleo regional
python scripts/bce_empleo.py

# 3. Descargar seguridad LeyStop
python scripts/leystop_scraper.py

# 4. Limpiar datos BCE
python scripts/limpiar_datos.py

# 5. Generar dashboard
python scripts/generar_dashboard.py
```

---

## 🔧 Configurar GitHub Pages (primera vez)

1. Ve a tu repositorio en github.com
2. **Settings** → **Pages**
3. En **Source** selecciona: `Deploy from a branch`
4. En **Branch** selecciona: `main` y carpeta `/ (root)`
5. Haz clic en **Save**
6. Espera ~2 minutos y tu sitio estará en:
   `https://[TU-USUARIO].github.io/[NOMBRE-REPO]/`

---

## 📁 Archivos que NO se suben a GitHub

Agrega estos al `.gitignore`:

```
env.local
bcn_indicadores.db
*.db
__pycache__/
*.pyc
```

---

## 🔗 Fuentes de datos

| Fuente | URL | Acceso |
|--------|-----|--------|
| Banco Central de Chile (BDE) | [si3.bcentral.cl](https://si3.bcentral.cl) | Requiere registro gratuito |
| BCN SIIT | [siit.bcn.cl](https://siit.bcn.cl) | Público |
| LeyStop Carabineros | [leystop.carabineros.cl](https://leystop.carabineros.cl) | Público |
| ADIS RSH | [adis.gob.cl](https://adis.gob.cl) | Requiere cuenta institucional |
| Censo 2024 INE | [ine.gob.cl](https://ine.gob.cl) | Público |

---

## 📝 Notas técnicas

- El dashboard es un **HTML autónomo** — no requiere servidor ni base de datos para visualizarse
- Todos los datos están embebidos en el HTML al momento de generarlo
- Compatible con Chrome, Firefox, Edge y Safari modernos
- Optimizado para pantallas ≥1280px

---

*Ministerio del Interior y Seguridad Pública · División de Coordinación Interministerial*
