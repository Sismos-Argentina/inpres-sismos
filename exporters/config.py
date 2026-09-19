"""
Configuración de rutas para los exportadores.
Centraliza las rutas de entrada y salida para evitar rutas hardcodeadas.
"""
import os

# Raíz del repositorio (dos niveles arriba de este archivo)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Archivos de entrada (producidos por el pipeline)
DATA_DIR = os.path.join(REPO_ROOT, "data")
SISMOS_CSV = os.path.join(DATA_DIR, "sismos.csv")
SISMOS_HISTORICOS_CSV = os.path.join(DATA_DIR, "sismos_historicos.csv")

# Directorio de salida de exportaciones
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")

# Archivos de salida
GEOJSON_OUT = os.path.join(EXPORTS_DIR, "sismos.geojson")
METADATA_OUT = os.path.join(EXPORTS_DIR, "metadata.json")
RECENT_OUT = os.path.join(EXPORTS_DIR, "sismos_recientes.json")
SAMPLE_OUT = os.path.join(EXPORTS_DIR, "sample.geojson")
STATS_OUT = os.path.join(EXPORTS_DIR, "stats.json")
HISTORICAL_OUT = os.path.join(EXPORTS_DIR, "sismos_historicos.json")
HISTORICAL_PHOTOS_MANIFEST = os.path.join(EXPORTS_DIR, "fotos_historicas.json")

# Cantidad de registros para la exportación "recientes"
RECENT_LIMIT = 500
SAMPLE_TARGET_SIZE = 200
