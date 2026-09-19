"""Descarga y optimiza las galerias historicas publicadas por INPRES.

Uso acotado:
    python scripts/scrape_historical_photos.py --limit-galleries 2

Corrida completa:
    python scripts/scrape_historical_photos.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import lxml.html
import requests
from PIL import Image, ImageOps
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


INDEX_URL = "http://contenidos.inpres.gob.ar/alumnos/fotos_terre"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "exports" / "fotos_historicas"
DEFAULT_MANIFEST = REPO_ROOT / "data" / "exports" / "fotos_historicas.json"
MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
DATE_PATTERN = re.compile(
    r"^(?P<place>.+),\s*(?P<day>\d{1,2})\s+de\s+"
    r"(?P<month>[a-záéíóú]+)\s+de\s+(?P<year>\d{4})$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Gallery:
    title: str
    place: str
    date_iso: str
    scope: str
    page_url: str
    index_thumbnail_url: str

    @property
    def slug(self) -> str:
        return f"{self.date_iso}-{slugify(self.place)}"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return value or "galeria"


def parse_document(content: bytes):
    # El servidor declara ISO-8859-1 en HTTP, pero el documento real es UTF-8.
    return lxml.html.fromstring(content.decode("utf-8"))


def parse_galleries(content: bytes, base_url: str = INDEX_URL) -> list[Gallery]:
    document = parse_document(content)
    galleries: list[Gallery] = []
    for anchor in document.xpath("//a[@href and .//img]"):
        rows = anchor.xpath("ancestor::tr[1]")
        if not rows:
            continue
        title = " ".join(rows[0].text_content().split())
        match = DATE_PATTERN.match(title)
        if not match:
            # Omite el logo y las galerias genericas por tipo de dano.
            continue

        month = MONTHS[match.group("month").casefold()]
        date = datetime(int(match.group("year")), month, int(match.group("day")))
        headings = anchor.xpath(
            "preceding::*[(self::strong or self::b) and contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
            "'fotos de terremotos')]"
        )
        heading = " ".join(headings[-1].text_content().split()).casefold() if headings else ""
        scope = "internacional" if "mundo" in heading else "argentina"
        image_sources = anchor.xpath(".//img/@src")
        galleries.append(
            Gallery(
                title=title,
                place=match.group("place"),
                date_iso=date.date().isoformat(),
                scope=scope,
                page_url=urljoin(base_url, anchor.get("href")),
                index_thumbnail_url=urljoin(base_url, image_sources[0]),
            )
        )
    return galleries


def parse_photo_links(content: bytes, base_url: str) -> list[dict[str, str]]:
    document = parse_document(content)
    photos: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in document.xpath("//a[@href and .//img]"):
        source_url = urljoin(base_url, anchor.get("href"))
        if "/terremotos/" not in source_url or source_url in seen:
            continue
        seen.add(source_url)
        image_sources = anchor.xpath(".//img/@src")
        title = anchor.get("title") or anchor.xpath("string(.//img/@alt)") or ""
        photos.append(
            {
                "titulo": " ".join(title.split()),
                "fuente_url": source_url,
                "miniatura_fuente_url": urljoin(base_url, image_sources[0]),
            }
        )
    return photos


def make_session() -> requests.Session:
    retries = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Sismos-Argentina historical-media-archiver/1.0 "
        "(+https://github.com/Sismos-Argentina/inpres-sismos)"
    )
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def get(session: requests.Session, url: str, timeout: int) -> requests.Response:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response


def webp_variants(
    image_bytes: bytes,
    output_base: Path,
) -> dict[str, int | str]:
    with Image.open(BytesIO(image_bytes)) as source:
        source = ImageOps.exif_transpose(source)
        original_width, original_height = source.size
        if source.mode not in ("RGB", "RGBA"):
            source = source.convert("RGB")

        large = source.copy()
        large.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        large_path = output_base.with_name(f"{output_base.name}-1600.webp")
        large.save(large_path, "WEBP", quality=82, method=6)

        thumbnail = source.copy()
        thumbnail.thumbnail((480, 480), Image.Resampling.LANCZOS)
        thumbnail_path = output_base.with_name(f"{output_base.name}-480.webp")
        thumbnail.save(thumbnail_path, "WEBP", quality=76, method=6)

    return {
        "ancho_original": original_width,
        "alto_original": original_height,
        "ancho_optimizado": large.width,
        "alto_optimizado": large.height,
        "archivo": large_path,
        "miniatura": thumbnail_path,
    }


def relative_web_path(path: Path, manifest_path: Path) -> str:
    return path.relative_to(manifest_path.parent).as_posix()


def load_existing_photos(manifest_path: Path) -> dict[str, dict]:
    if not manifest_path.exists():
        return {}
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    photos = (photo for gallery in document.get("galerias", []) for photo in gallery.get("fotos", []))
    return {photo["fuente_url"]: photo for photo in photos}


def cached_files_exist(photo: dict, manifest_path: Path) -> bool:
    return all((manifest_path.parent / photo[field]).is_file() for field in ("archivo", "miniatura"))


def scrape(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
    limit_galleries: int | None = None,
    delay: float = 0.5,
    timeout: int = 60,
) -> dict:
    session = make_session()
    index = get(session, INDEX_URL, timeout)
    galleries = parse_galleries(index.content)
    if limit_galleries is not None:
        galleries = galleries[:limit_galleries]
    if not galleries:
        raise RuntimeError("El indice de INPRES no devolvio galerias con fecha.")

    existing_photos = load_existing_photos(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    gallery_documents = []
    total_photos = 0
    total_unavailable = 0

    for gallery_number, gallery in enumerate(galleries, start=1):
        time.sleep(delay)
        detail = get(session, gallery.page_url, timeout)
        photo_links = parse_photo_links(detail.content, gallery.page_url)
        if not photo_links:
            raise RuntimeError(f"La galeria no contiene fotos: {gallery.page_url}")

        gallery_dir = output_dir / gallery.slug
        gallery_dir.mkdir(parents=True, exist_ok=True)
        photo_documents = []
        unavailable_documents = []
        print(f"[{gallery_number}/{len(galleries)}] {gallery.title}: {len(photo_links)} fotos")

        for photo_number, photo in enumerate(photo_links, start=1):
            cached = existing_photos.get(photo["fuente_url"])
            if cached and cached_files_exist(cached, manifest_path):
                photo_documents.append(cached)
                continue
            time.sleep(delay)
            used_fallback = False
            download_url = photo["fuente_url"]
            try:
                response = get(session, download_url, timeout)
            except requests.RequestException as original_error:
                download_url = photo["miniatura_fuente_url"]
                try:
                    response = get(session, download_url, timeout)
                except requests.RequestException as fallback_error:
                    unavailable_documents.append(
                        {
                            "titulo": photo["titulo"],
                            "fuente_url": photo["fuente_url"],
                            "miniatura_fuente_url": photo["miniatura_fuente_url"],
                            "error_original": str(original_error),
                            "error_miniatura": str(fallback_error),
                        }
                    )
                    print(f"  [WARN] Imagen no disponible en INPRES: {photo['fuente_url']}")
                    continue
                used_fallback = True
                print(f"  [WARN] Original no disponible; se usa miniatura: {photo['fuente_url']}")
            if not (response.headers.get("Content-Type") or "").startswith("image/"):
                raise RuntimeError(f"Respuesta no es una imagen: {download_url}")
            digest = hashlib.sha256(photo["fuente_url"].encode("utf-8")).hexdigest()[:8]
            name = f"{photo_number:02d}-{slugify(photo['titulo'])[:60]}-{digest}"
            variants = webp_variants(response.content, gallery_dir / name)
            photo_documents.append(
                {
                    "id": digest,
                    "titulo": photo["titulo"],
                    "fuente_url": photo["fuente_url"],
                    "miniatura_fuente_url": photo["miniatura_fuente_url"],
                    "descarga_url": download_url,
                    "original_disponible": not used_fallback,
                    "archivo": relative_web_path(variants.pop("archivo"), manifest_path),
                    "miniatura": relative_web_path(variants.pop("miniatura"), manifest_path),
                    **variants,
                    "bytes_fuente": len(response.content),
                }
            )

        total_photos += len(photo_documents)
        total_unavailable += len(unavailable_documents)
        gallery_documents.append(
            {
                "id": gallery.slug,
                "titulo": gallery.title,
                "lugar": gallery.place,
                "fecha_iso": gallery.date_iso,
                "ambito": gallery.scope,
                "pagina_fuente": gallery.page_url,
                "miniatura_indice_fuente": gallery.index_thumbnail_url,
                "total_fotos_fuente": len(photo_links),
                "total_fotos": len(photo_documents),
                "total_fotos_no_disponibles": len(unavailable_documents),
                "fotos": photo_documents,
                "fotos_no_disponibles": unavailable_documents,
            }
        )

    document = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "provider": "INPRES",
            "index_url": INDEX_URL,
            "note": "Imagenes publicas archivadas y optimizadas por un proyecto no oficial de INPRES.",
        },
        "total_galerias": len(gallery_documents),
        "total_fotos": total_photos,
        "total_fotos_no_disponibles": total_unavailable,
        "galerias": gallery_documents,
    }
    with manifest_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(document, file, ensure_ascii=False, separators=(",", ":"))
        file.write("\n")
    print(f"[OK] {len(gallery_documents)} galerias y {total_photos} fotos -> {manifest_path}")
    return document


def parse_args(arguments: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-galleries", type=int)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args(arguments)


if __name__ == "__main__":
    args = parse_args()
    scrape(
        output_dir=args.output_dir,
        manifest_path=args.manifest,
        limit_galleries=args.limit_galleries,
        delay=args.delay,
        timeout=args.timeout,
    )
