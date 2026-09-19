import csv
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from exporters.config import SISMOS_HISTORICOS_CSV
from exporters.historical_exporter import build_event, extract_mercalli, normalize_text
from scripts.scrape_historical_photos import parse_galleries, parse_photo_links


class TestHistoricalExporter(unittest.TestCase):
    def test_normalize_text_removes_non_breaking_and_duplicate_spaces(self):
        self.assertEqual(normalize_text(" Daños\u00a0   y réplicas . "), "Daños y réplicas.")

    def test_extract_single_mercalli_intensity(self):
        result = extract_mercalli("Su intensidad fue de IX grados en la escala Mercalli.")
        self.assertEqual(result["grado_principal"], "IX")
        self.assertEqual(result["valor_maximo"], 9)

    def test_extract_regional_mercalli_range(self):
        result = extract_mercalli(
            "La intensidad Mercalli fue de V en Mendoza; III a IV en Córdoba; VI a VII en San Juan"
        )
        self.assertEqual(result["valor_minimo"], 3)
        self.assertEqual(result["valor_maximo"], 7)

    def test_real_catalog_normalizes_all_rows(self):
        with open(SISMOS_HISTORICOS_CSV, "r", encoding="utf-8", newline="") as file:
            events = [build_event(row, {}) for row in csv.DictReader(file)]
        self.assertEqual(len(events), 80)
        self.assertTrue(all(event["intensidad_mercalli"] for event in events))
        self.assertTrue(all("  " not in event["descripcion"] for event in events))

    def test_sampacho_photo_date_discrepancy_is_explicit(self):
        row = {
            "fecha": "11/06/1934",
            "provincia": "CÓRDOBA",
            "descripcion": "Intensidad VIII grados Mercalli.",
            "latitud": "-33.5",
            "longitud": "-64.5",
        }
        event = build_event(row, {"1934-06-10": [{"id": "photo"}]})
        self.assertEqual(event["fotos_asociacion"]["metodo"], "fecha_fuente_discrepante")
        self.assertEqual(event["fotos_asociacion"]["fecha_galeria"], "1934-06-10")


class TestHistoricalPhotoParser(unittest.TestCase):
    def test_index_keeps_dated_galleries_and_scopes(self):
        html = """
        <strong>Fotos de terremotos ocurridos en territorio argentino</strong>
        <table><tr><td>Mendoza, 20 de marzo de 1861</td><td>
          <a href="mendoza"><img src="thumb-mendoza"></a></td></tr></table>
        <strong>Fotos de terremotos ocurridos en el mundo</strong>
        <table><tr><td>Chile, 27 de febrero de 2010</td><td>
          <a href="chile"><img src="thumb-chile"></a></td></tr>
          <tr><td>Carreteras</td><td><a href="roads"><img src="thumb-roads"></a></td></tr>
        </table>
        """.encode()
        galleries = parse_galleries(html, "http://example.test/index")
        self.assertEqual(len(galleries), 2)
        self.assertEqual(galleries[0].scope, "argentina")
        self.assertEqual(galleries[1].scope, "internacional")

    def test_detail_prefers_full_image_link(self):
        html = b'<a href="../terremotos/full" title="Ruinas"><img src="../terremotos/thumb"></a>'
        photos = parse_photo_links(html, "http://example.test/gallery")
        self.assertEqual(photos[0]["fuente_url"], "http://example.test/terremotos/full")
        self.assertEqual(photos[0]["titulo"], "Ruinas")


if __name__ == "__main__":
    unittest.main()
