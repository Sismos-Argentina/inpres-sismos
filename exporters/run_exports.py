"""
run_exports.py

Punto de entrada principal del pipeline de exportación.
Lee sismos.csv una sola vez y ejecuta todos los exportadores en secuencia.

Exportadores incluidos:
1. geojson_exporter -> data/exports/sismos.geojson (GeoJSON completo RFC 7946)
2. metadata_exporter -> data/exports/metadata.json (Metadatos y bounding box)
3. recent_exporter -> data/exports/sismos_recientes.json (Últimos 500 sismos)
4. sample_exporter -> data/exports/sample.geojson (Muestra variada 100-300 registros)
5. stats_exporter -> data/exports/stats.json (Estadísticas agregadas)
6. historical_exporter -> data/exports/sismos_historicos.json (catalogo historico normalizado)

Uso:
    python exporters/run_exports.py

Invocado automáticamente por GitHub Actions al final del pipeline.
Si alguna exportación falla, no interrumpe el pipeline principal.
"""
import sys
import os

# Asegurar que el directorio raíz del repo esté en el path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from exporters.config import SISMOS_CSV
from exporters import (
    csv_exporter,
    geojson_exporter,
    historical_exporter,
    metadata_exporter,
    recent_exporter,
    sample_exporter,
    stats_exporter,
)


def main():
    print("=" * 60)
    print("GENERACIÓN DE ARCHIVOS DE EXPORTACIÓN")
    print("=" * 60)
    print(f"[CSV] Fuente: {SISMOS_CSV}")

    # Verificar que el CSV existe antes de intentar leerlo
    if not os.path.exists(SISMOS_CSV):
        print(f"[ERROR] No se encontro: {SISMOS_CSV}")
        sys.exit(1)

    # Leer el CSV una sola vez — todos los exportadores comparten el mismo DataFrame
    print("\n[1] Cargando sismos.csv e ID deterministicos...")
    df = csv_exporter.load_sismos()
    print(f"    {len(df)} registros cargados e IDs generados")

    errors = []

    # 1. GeoJSON completo
    print("\n[2] Exportando GeoJSON completo...")
    try:
        geojson_exporter.export(df)
    except Exception as e:
        print(f"  [ERROR] GeoJSON fallo: {e}")
        errors.append("geojson")

    # 2. Metadata
    print("\n[3] Exportando metadata...")
    try:
        metadata_exporter.export(df)
    except Exception as e:
        print(f"  [ERROR] Metadata fallo: {e}")
        errors.append("metadata")

    # 3. Recientes
    print("\n[4] Exportando sismos recientes...")
    try:
        recent_exporter.export(df)
    except Exception as e:
        print(f"  [ERROR] Recientes fallo: {e}")
        errors.append("recent")

    # 4. Sample GeoJSON
    print("\n[5] Exportando sample.geojson...")
    try:
        sample_exporter.export(df)
    except Exception as e:
        print(f"  [ERROR] Sample fallo: {e}")
        errors.append("sample")

    # 5. Stats JSON
    print("\n[6] Exportando stats.json...")
    try:
        stats_exporter.export(df)
    except Exception as e:
        print(f"  [ERROR] Stats fallo: {e}")
        errors.append("stats")

    # 6. Catalogo historico y vinculacion opcional con fotos
    print("\n[7] Exportando sismos historicos...")
    try:
        historical = historical_exporter.export()
        print(f"    {historical['total_eventos']} eventos historicos exportados")
    except Exception as e:
        print(f"  [ERROR] Historicos fallo: {e}")
        errors.append("historical")

    print("\n" + "=" * 60)
    if errors:
        print(f"[WARN] Completado con errores en: {', '.join(errors)}")
        print("       El pipeline principal no se ve afectado.")
        sys.exit(1)
    else:
        print("[OK] EXPORTACION COMPLETADA — todos los archivos generados")
    print("=" * 60)


if __name__ == "__main__":
    main()
