"""Exporta el catalogo historico de INPRES listo para consumo web."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from exporters.config import (
    HISTORICAL_OUT,
    HISTORICAL_PHOTOS_MANIFEST,
    SISMOS_HISTORICOS_CSV,
)


ROMAN_TO_INT = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
}
ROMAN_PATTERN = re.compile(
    r"\b(XII|XI|IX|VIII|VII|VI|IV|III|II|X|V|I)\b", re.IGNORECASE
)
SPACE_PATTERN = re.compile(r"\s+")

LOCATION_NAMES = {
    "SGO. DEL ESTERO": "Santiago del Estero",
    "ISLAS ORCADAS": "Islas Orcadas del Sur",
    "TIERRA DEL FUEGO": "Tierra del Fuego",
}

# El catalogo historico de INPRES dice 11/06; su galeria fotografica dice 10/06.
# Se conservan ambas fechas y se explicita el metodo de asociacion en la salida.
PHOTO_DATE_OVERRIDES = {"1934-06-11": "1934-06-10"}


def normalize_text(value: str) -> str:
    """Normaliza Unicode y espacios sin reescribir el contenido editorial."""
    value = unicodedata.normalize("NFC", value or "")
    value = value.replace("\u00a0", " ").replace("\u202f", " ")
    value = SPACE_PATTERN.sub(" ", value).strip()
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    return value


def normalize_location(value: str) -> tuple[str, list[str]]:
    original = normalize_text(value).upper()
    if "–" in original or " - " in original:
        parts = re.split(r"\s*(?:–|-)\s*", original)
        normalized = [LOCATION_NAMES.get(part, part.title()) for part in parts if part]
        return " – ".join(normalized), normalized
    normalized = LOCATION_NAMES.get(original, original.title())
    return normalized, [normalized]


def extract_mercalli(description: str) -> dict[str, Any] | None:
    """Extrae los grados reportados sin convertirlos en magnitud instrumental."""
    lowered = description.casefold()
    marker_positions = [
        position
        for marker in ("intensidad", "mercalli")
        if (position := lowered.find(marker)) >= 0
    ]
    if not marker_positions:
        return None

    relevant = description[min(marker_positions) :]
    roman_values = [match.group(1).upper() for match in ROMAN_PATTERN.finditer(relevant)]
    if not roman_values:
        # Algunos registros escriben el grado antes de "intensidad".
        relevant = description
        roman_values = [match.group(1).upper() for match in ROMAN_PATTERN.finditer(relevant)]
    if not roman_values:
        return None

    numeric_values = [ROMAN_TO_INT[value] for value in roman_values]
    primary = roman_values[0]
    minimum = min(numeric_values)
    maximum = max(numeric_values)
    return {
        "grado_principal": primary,
        "valor_principal": ROMAN_TO_INT[primary],
        "grado_minimo": next(key for key, value in ROMAN_TO_INT.items() if value == minimum),
        "valor_minimo": minimum,
        "grado_maximo": next(key for key, value in ROMAN_TO_INT.items() if value == maximum),
        "valor_maximo": maximum,
        "escala_reportada": (
            "Mercalli Modificada"
            if "mercalli modificada" in lowered or re.search(r"\bmm\b", relevant, re.I)
            else "Mercalli"
        ),
        "es_estimada": bool(re.search(r"\bestim(?:ada|ado|o|ó)", lowered)),
    }


def make_id(fecha_iso: str, latitud: float, longitud: float) -> str:
    raw = f"historico|{fecha_iso}|{latitud:.6f}|{longitud:.6f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_photo_manifest(path: str = HISTORICAL_PHOTOS_MANIFEST) -> dict[str, list[dict]]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as file:
        manifest = json.load(file)
    return {
        gallery["fecha_iso"]: gallery.get("fotos", [])
        for gallery in manifest.get("galerias", [])
        if gallery.get("ambito") == "argentina"
    }


def build_event(row: dict[str, str], photos_by_date: dict[str, list[dict]]) -> dict[str, Any]:
    date = datetime.strptime(row["fecha"], "%d/%m/%Y")
    fecha_iso = date.date().isoformat()
    latitud = float(row["latitud"].replace(",", "."))
    longitud = float(row["longitud"].replace(",", "."))
    descripcion = normalize_text(row["descripcion"])
    ubicacion, ubicaciones = normalize_location(row["provincia"])
    gallery_date = fecha_iso if fecha_iso in photos_by_date else PHOTO_DATE_OVERRIDES.get(fecha_iso)
    photos = photos_by_date.get(gallery_date, []) if gallery_date else []
    photo_association = None
    if photos:
        photo_association = {
            "metodo": "fecha_exacta" if gallery_date == fecha_iso else "fecha_fuente_discrepante",
            "fecha_evento": fecha_iso,
            "fecha_galeria": gallery_date,
        }

    return {
        "id": make_id(fecha_iso, latitud, longitud),
        "fecha": row["fecha"],
        "fecha_iso": fecha_iso,
        "anio": date.year,
        "ubicacion_original": normalize_text(row["provincia"]),
        "ubicacion": ubicacion,
        "ubicaciones": ubicaciones,
        "descripcion": descripcion,
        "intensidad_mercalli": extract_mercalli(descripcion),
        "coordenadas": {"latitud": latitud, "longitud": longitud},
        "fotos_asociacion": photo_association,
        "fotos": photos,
    }


def export(
    source_path: str = SISMOS_HISTORICOS_CSV,
    output_path: str = HISTORICAL_OUT,
    photo_manifest_path: str = HISTORICAL_PHOTOS_MANIFEST,
) -> dict[str, Any]:
    photos_by_date = load_photo_manifest(photo_manifest_path)
    with open(source_path, "r", encoding="utf-8", newline="") as file:
        events = [build_event(row, photos_by_date) for row in csv.DictReader(file)]

    document = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "provider": "INPRES",
            "catalog_url": "http://contenidos.inpres.gob.ar/sismologia/historicos",
            "note": "Datos publicos normalizados por un proyecto no oficial de INPRES.",
        },
        "total_eventos": len(events),
        "total_eventos_con_fotos": sum(bool(event["fotos"]) for event in events),
        "eventos": events,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as file:
        json.dump(document, file, ensure_ascii=False, separators=(",", ":"))
        file.write("\n")
    return document


if __name__ == "__main__":
    result = export()
    print(f"[OK] {result['total_eventos']} eventos historicos exportados a {HISTORICAL_OUT}")
