# INPRES Sismos — Data Pipeline (v2.0)

> **⚠️ AVISO LEGAL Y ATRIBUCIÓN:**
> Este repositorio **NO es un proyecto ni un producto oficial del INPRES** (Instituto Nacional de Prevención Sísmica de Argentina).
> Utiliza exclusivamente información pública disponible en el sitio web del INPRES para procesarla, normalizarla y proveerla como servicio de datos abierto para aplicaciones de visualización e investigación.

Fuente oficial de datos sísmicos de Argentina y zonas de influencia, concebida como **proveedor backend de datos** para aplicaciones modernas de visualización interactiva (React + MapLibre GL JS + Three.js).

---

## 🎯 Propósito del Repositorio

Este proyecto se encarga de:
- **Obtener** diariamente los registros de sismos reportados por el INPRES mediante scraping autónomo.
- **Almacenar** el histórico completo en archivos CSV y base de datos SQLite.
- **Normalizar y Enriquecer** los datos en la etapa de exportación (sin modificar la fuente original).
- **Publicar** los datasets procesados automáticamente mediante GitHub Actions en formatos listos para consumir (GeoJSON RFC 7946, JSON, CSV).

El frontend consumidor no necesita realizar procesamiento, parsing complejo ni normalización de cadenas; consumirá directamente los archivos procesados.

---

## 📦 Datasets Exportados

Todos los archivos se actualizan automáticamente todos los días a las 10:20 UTC y están disponibles vía **GitHub Raw**:

| Dataset | Formato | Tamaño aprox. | Descripción | URL Raw |
|---|---|---|---|---|
| [`sismos.geojson`](data/exports/sismos.geojson) | GeoJSON | ~20 MB | FeatureCollection RFC 7946 completo con 80.000+ eventos. Listo para MapLibre / Leaflet. | [Ver Raw](https://raw.githubusercontent.com/LuisOVaras/inpres-sismos/main/data/exports/sismos.geojson) |
| [`sample.geojson`](data/exports/sample.geojson) | GeoJSON | ~80 KB | Muestra estratificada de 100 a 300 eventos representativos para desarrollo rápido. | [Ver Raw](https://raw.githubusercontent.com/LuisOVaras/inpres-sismos/main/data/exports/sample.geojson) |
| [`metadata.json`](data/exports/metadata.json) | JSON | ~4 KB | Metadatos globales: bounding box completo, rangos, promedios, versiones de schema y timestamps UTC. | [Ver Raw](https://raw.githubusercontent.com/LuisOVaras/inpres-sismos/main/data/exports/metadata.json) |
| [`stats.json`](data/exports/stats.json) | JSON | ~8 KB | Estadísticas precalculadas: distribuciones por año, mes, rango de magnitud, profundidad, provincia y país. | [Ver Raw](https://raw.githubusercontent.com/LuisOVaras/inpres-sismos/main/data/exports/stats.json) |
| [`sismos_recientes.json`](data/exports/sismos_recientes.json) | JSON | ~80 KB | Últimos 500 sismos registrados en formato JSON plano enriquecido. | [Ver Raw](https://raw.githubusercontent.com/LuisOVaras/inpres-sismos/main/data/exports/sismos_recientes.json) |
| [`sismos.csv`](data/sismos.csv) | CSV | ~4.8 MB | Dataset maestro histórico completo (fuente de verdad del pipeline). | [Ver Raw](https://raw.githubusercontent.com/LuisOVaras/inpres-sismos/main/data/sismos.csv) |
| [`sismos.db`](data/sismos.db) | SQLite | ~10 MB | Base de datos SQLite para consultas SQL directas u offline. | [Ver Raw](https://raw.githubusercontent.com/LuisOVaras/inpres-sismos/main/data/sismos.db) |
| [`sismos_historicos.json`](data/exports/sismos_historicos.json) | JSON | ~100 KB | 80 terremotos historicos con texto limpio, fecha ISO, coordenadas numericas, Mercalli estructurada y fotos vinculadas por fecha. | — |
| [`fotos_historicas.json`](data/exports/fotos_historicas.json) | JSON | ~100 KB | Manifiesto de galerias y derivados WebP; separa `argentina` de `internacional` y registra enlaces rotos. | — |

---

## 📐 Esquema de Datos Enriquecido (v2.0)

Cada evento contiene tanto los datos originales del INPRES como campos derivados enriquecidos durante la exportación:

### Campos del Dataset

| Campo | Tipo | Origen | Descripción | Ejemplos |
|---|---|---|---|---|
| `id` | `string` | **Derivado** | Hash SHA-256 determinístico de 16 caracteres de longitud. Único y estable. | `"c32ffc4da05ffb1d"` |
| `fecha` | `string` | **Original** | Fecha del evento en formato `DD/MM/YYYY`. | `"07/08/2026"` |
| `hora` | `string` | **Original** | Hora reportada `HH:MM:SS`. | `"14:30:00"` |
| `latitud` | `float` | **Original** | Latitud geográfica decimal en grados (negativo = Sur). | `-31.537` |
| `longitud` | `float` | **Original** | Longitud geográfica decimal en grados (negativo = Oeste). | `-68.536` |
| `profundidad` | `float` | **Original** | Profundidad del hipocentro en kilómetros. | `110.0` |
| `magnitud` | `float` | **Original** | Magnitud del evento sísmico (Escala Richter / Mw). | `3.4` |
| `sentido` | `string` | **Original** | Indica si el evento fue reportado como sentido por la población (`"Si"` / `"No"`). | `"No"` |
| `ubicacion_original` | `string` | **Original** | Cadena de provincia / ubicación tal como la reporta el sitio del INPRES. | `"SAN JUAn"` |
| `ubicacion_normalizada` | `string` | **Derivado** | Nombre limpio y corregido (case, tildes, typos, limites). | `"San Juan"` |
| `provincia` | `string \| null` | **Derivado** | Nombre de la provincia argentina principal (si aplica, en Title Case). | `"San Juan"` |
| `provincias` | `list[string]` | **Derivado** | Lista de provincias involucradas (útil en límites interprovinciales). | `["San Juan", "Mendoza"]` |
| `pais` | `string` | **Derivado** | País correspondiente al epicentro. | `"Argentina"`, `"Chile"` |
| `tipo_ubicacion` | `string` | **Derivado** | Categoria: `provincia`, `limite_interprovincial`, `limite_internacional`, `extranjero`, `oceano`, `antartida`, `desconocido`. | `"provincia"` |
| `es_argentina` | `boolean` | **Derivado** | `true` si corresponde a territorio argentino (incl. Antártida y mares nacionales). | `true` |
| `es_limite` | `boolean` | **Derivado** | `true` si el epicentro está registrado en una zona fronteriza o límite. | `false` |

---

## 🔑 Identificador Único y Determinístico (`id`)

Cada evento sísmico posee un identificador de 16 caracteres generado mediante hashing SHA-256:

$$\text{ID} = \text{SHA256}(\text{fecha} \mid \text{hora} \mid \text{latitud} \mid \text{longitud} \mid \text{profundidad} \mid \text{magnitud})[:16]$$

- **Determinístico**: El mismo evento generará **siempre el mismo ID**, sin importar cuántas veces se ejecute el pipeline.
- **Estable**: No se altera con actualizaciones posteriores ni re-ordenamientos del dataset.
- **Soporte GeoJSON**: En `sismos.geojson` y `sample.geojson`, este ID se incluye tanto como `Feature.id` (primer nivel de GeoJSON) como en `properties.id`.

---

## 🔄 Arquitectura del Pipeline

```
 Sitio Oficial INPRES (Web)
            │
            ▼
 [1] Scraping Autónomo (Selenium) ──────► data/sismos.csv  (Fuente de verdad)
            │
            ├───────────────────────────► data/sismos.db   (Base de datos SQLite)
            │
            ├───────────────────────────► Supabase Cloud   (Sincronización remota)
            │
            ▼
 [2] Etapa de Exportación Enriquecida (exporters/)
            │
            ├──► location_normalizer.py  (Normalización de cadenas sin tocar el CSV)
            ├──► csv_exporter.py         (Generación de IDs determinísticos)
            ├──► geojson_exporter.py     (Genera sismos.geojson)
            ├──► sample_exporter.py      (Genera sample.geojson)
            ├──► metadata_exporter.py    (Genera metadata.json)
            ├──► stats_exporter.py       (Genera stats.json)
            └──► recent_exporter.py      (Genera sismos_recientes.json)
            │
            ▼
 [3] Publicación Automática (GitHub Actions -> main branch)
```

## 🏛️ Sismos historicos y fotografias

`data/sismos_historicos.csv` se conserva como fuente original. El exportador no lo
reescribe: corrige Unicode y espacios en la salida, convierte fecha y coordenadas a
tipos aptos para frontend, y expone la intensidad Mercalli como un objeto con grado
romano, valor numerico, minimo, maximo, escala reportada y marca de estimacion.

Las fotografias se archivan desde el indice publico del INPRES y se generan en dos
variantes WebP: miniatura de hasta 480 px y visualizacion de hasta 1600 px. Cada foto
mantiene sus URLs oficiales de procedencia. Las galerias de Chile 2010 y Japon 2011
se marcan como `internacional` y no se asocian al catalogo argentino.
La unica discrepancia de fecha observada se conserva: el catalogo fecha Sampacho el
11/06/1934 y la galeria el 10/06/1934; la vinculacion queda marcada como
`fecha_fuente_discrepante` con ambas fechas.

```bash
# Prueba acotada (dos galerias)
python scripts/scrape_historical_photos.py --limit-galleries 2

# Todas las galerias fechadas; reutiliza archivos ya descargados
python scripts/scrape_historical_photos.py

# Regenerar el catalogo y vincular las fotos argentinas por fecha
python -m exporters.historical_exporter
```

Si un original ya no existe pero su miniatura sigue disponible, el manifiesto marca
`original_disponible: false`. Si ambos enlaces fallan, la entrada queda documentada
en `fotos_no_disponibles` sin interrumpir el resto de la descarga.

---

## 🧪 Tests Automáticos

El repositorio cuenta con una suite de pruebas automatizadas para verificar que la exportación mantenga la integridad y el cumplimiento estricto del estándar GeoJSON RFC 7946.

Para ejecutar los tests localmente:

```bash
python test/test_exporters.py
```

Pruebas incluidas:
- **`test_deterministic_ids_are_unique_and_stable`**: Verifica 0 colisiones en los 80.000+ IDs y consistencia determinística.
- **`test_geojson_validity`**: Verifica cumplimiento de RFC 7946 (`FeatureCollection`, `Feature.id`, coordenadas `[lon, lat]`).
- **`test_sample_geojson_range`**: Verifica que `sample.geojson` tenga entre 100 y 300 elementos.
- **`test_metadata_counts_match`**: Verifica que la cantidad de registros en `metadata.json` coincida exactamente con el GeoJSON.
- **`test_location_normalizer_known_cases`**: Valida las reglas de normalización de cadenas de ubicación.

---

## 🚀 Uso Local

```bash
# 1. Clonar el repositorio
git clone https://github.com/LuisOVaras/inpres-sismos.git
cd inpres-sismos

# 2. Instalar dependencias del pipeline
pip install -r requirements.txt

# 3. Ejecutar el scraper diario
python inpres_sismos/inpres_sismos/selenium/actualizar_sismos.py

# 4. Actualizar la base de datos SQLite
python inpres_sismos/inpres_sismos/db_scripts/actualizar_database.py

# 5. Generar todos los datasets exportados
python exporters/run_exports.py

# 6. Ejecutar tests de validación
python test/test_exporters.py
```

---

## 📄 Licencia

Este repositorio es un desarrollo independiente y abierto. Los datos de origen pertenecen al **INPRES** y son de acceso público.
