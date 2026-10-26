"""Testes locais sem dependências externas para a consulta ao Manual FMABC."""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from manual_search import load_index, search_manual  # noqa: E402


class ManualSearchTests(unittest.TestCase):
    def test_index_contains_full_manual_pages(self):
        index = load_index()
        self.assertEqual(index["pdf_pages"], 67)
        self.assertEqual(len(index["pages"]), 67)
        self.assertGreater(len(index["chunks"]), 100)

    def test_ti_deadline_cites_page_20(self):
        results = search_manual("Qual a antecedência para solicitar suporte de TI?")
        self.assertTrue(results)
        self.assertEqual(results[0]["page"], 20)
        self.assertIn("15", results[0]["text"])

    def test_spaces_capacity_cites_page_23(self):
        results = search_manual("Qual a capacidade dos espaços da FMABC?")
        self.assertTrue(results)
        self.assertEqual(results[0]["page"], 23)
        self.assertIn("Auditório David Uip", results[0]["text"])

    def test_event_stages_are_retrieved(self):
        results = search_manual("Quais são as etapas de organização de um evento?")
        self.assertTrue(results)
        self.assertTrue(any(r["page"] == 12 for r in results))

    def test_communication_support_deadline_cites_page_20(self):
        results = search_manual("Qual o prazo para a Comunicação apoiar divulgação de eventos?")
        self.assertTrue(results)
        page_20 = next(r for r in results if r["page"] == 20)
        self.assertIn("30 (trinta) dias", page_20["text"])

    def test_inspetoria_space_reservation_deadline_cites_page_19(self):
        results = search_manual("Qual a antecedência da Inspetoria para reservar espaços?")
        self.assertTrue(results)
        self.assertEqual(results[0]["page"], 19)
        self.assertIn("15 (quinze) dias", results[0]["text"])

    def test_unrelated_question_does_not_create_an_answer(self):
        results = search_manual("Como faço tokenização quântica no evento?")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
