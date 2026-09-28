import unittest

from index_courses import DOCUMENT_LIMIT, build_document


class IndexerTests(unittest.TestCase):
    def test_document_contains_catalog_fields_and_is_bounded(self) -> None:
        document = build_document(
            {
                "name": "SQL для аналитиков",
                "source": "stepik",
                "description": "A" * 7000,
                "topics": "SQL, аналитика",
                "keywords": "database",
            }
        )
        self.assertIn("Название: SQL для аналитиков", document)
        self.assertLessEqual(len(document), DOCUMENT_LIMIT)


if __name__ == "__main__":
    unittest.main()
