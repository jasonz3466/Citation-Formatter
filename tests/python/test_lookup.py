"""Tests for the DOI and ISBN lookup, with the network stubbed out.

The point is the mapping: turning someone else's JSON shape into our field names.
The HTTP call itself is replaced so these run offline and never hit a live service.
"""

import unittest
from unittest.mock import MagicMock, patch

from citation_formatter import lookup

CROSSREF_ARTICLE = {"message": {
    "type": "journal-article",
    "author": [{"given": "Claude E.", "family": "Shannon"}],
    "title": ["A Mathematical Theory of Communication"],
    "container-title": ["Bell System Technical Journal"],
    "issued": {"date-parts": [[1948, 7]]},
    "volume": "27", "issue": "3", "page": "379-423",
    "publisher": "Wiley", "DOI": "10.1002/j.1538-7305.1948.tb01338.x",
}}

CROSSREF_CHAPTER = {"message": {
    "type": "book-chapter",
    "author": [{"given": "Alan M.", "family": "Turing"}],
    "editor": [{"given": "B. Jack", "family": "Copeland"}],
    "title": ["Computing Machinery and Intelligence"],
    "container-title": ["The Essential Turing"],
    "issued": {"date-parts": [[2004]]},
    "publisher": "Oxford University Press", "page": "433-464", "DOI": "10.1093/oso/x",
}}

OPENLIBRARY = {"ISBN:9780321973610": {
    "title": "University Physics with Modern Physics",
    "authors": [{"name": "Hugh D. Young"}, {"name": "Roger A. Freedman"}],
    "publishers": [{"name": "Pearson"}],
    "publish_places": [{"name": "Boston"}],
    "publish_date": "January 2, 2015",
    "url": "https://openlibrary.org/books/OL1M",
}}


class TestIdentifiers(unittest.TestCase):

    def test_a_pasted_doi_url_is_stripped(self):
        self.assertEqual(lookup.clean_identifier("https://doi.org/10.1002/abc"), "10.1002/abc")
        self.assertEqual(lookup.clean_identifier("doi: 10.1002/abc"), "10.1002/abc")

    def test_dois_and_isbns_are_told_apart(self):
        self.assertTrue(lookup.looks_like_doi("10.1002/abc"))
        self.assertFalse(lookup.looks_like_doi("9780321973610"))
        self.assertTrue(lookup.looks_like_isbn("978-0-321-97361-0"))
        self.assertFalse(lookup.looks_like_isbn("10.1002/abc"))

    def test_junk_is_refused_before_any_request_is_made(self):
        with self.assertRaises(lookup.LookupError_):
            lookup.lookup("banana")

    def test_lowercase_isbn_check_digit_is_normalized(self):
        payload = {"ISBN:080442957X": {"title": "Example"}}
        with patch.object(lookup, "fetch_json", return_value=payload):
            result = lookup.from_openlibrary("0-8044-2957-x")
        self.assertEqual(result["isbn"], "080442957X")

    def test_requests_use_the_bundled_certificate_store(self):
        response = MagicMock()
        response.read.return_value = b'{"message": {}}'
        response.__enter__.return_value = response
        with patch.object(lookup.urllib.request, "urlopen", return_value=response) as opened:
            lookup.fetch_json("https://example.test")
        self.assertIs(opened.call_args.kwargs["context"], lookup.SSL_CONTEXT)


class TestCrossrefMapping(unittest.TestCase):

    def map(self, payload):
        with patch.object(lookup, "fetch_json", return_value=payload):
            return lookup.from_crossref("10.0/x")

    def test_an_article_maps_onto_our_fields(self):
        result = self.map(CROSSREF_ARTICLE)
        self.assertEqual(result["source_type"], "article")
        self.assertEqual(result["authors"], "Shannon, Claude E.")
        self.assertEqual(result["container"], "Bell System Technical Journal")
        self.assertEqual(result["year"], "1948")
        self.assertEqual(result["pages"], "379-423")

    def test_a_chapter_is_recognized_as_a_chapter(self):
        result = self.map(CROSSREF_CHAPTER)
        self.assertEqual(result["source_type"], "chapter")
        self.assertEqual(result["editors"], "Copeland, B. Jack")

    def test_missing_pieces_come_back_blank_rather_than_crashing(self):
        result = self.map({"message": {"type": "journal-article"}})
        self.assertEqual(result["title"], "")
        self.assertEqual(result["year"], "")


class TestOpenLibraryMapping(unittest.TestCase):

    def test_a_book_maps_onto_our_fields(self):
        with patch.object(lookup, "fetch_json", return_value=OPENLIBRARY):
            result = lookup.from_openlibrary("978-0-321-97361-0")
        self.assertEqual(result["source_type"], "book")
        self.assertEqual(result["authors"], "Hugh D. Young\nRoger A. Freedman")
        self.assertEqual(result["publisher"], "Pearson")
        self.assertEqual(result["year"], "2015")

    def test_an_unknown_isbn_is_reported_clearly(self):
        with patch.object(lookup, "fetch_json", return_value={}):
            with self.assertRaises(lookup.LookupError_):
                lookup.from_openlibrary("9780000000002")


class TestEndToEnd(unittest.TestCase):
    """A looked-up record should format without further editing."""

    def test_a_crossref_article_formats_straight_through(self):
        from citation_formatter.citations import format_all
        with patch.object(lookup, "fetch_json", return_value=CROSSREF_ARTICLE):
            fields = lookup.from_crossref("10.0/x")
        self.assertIn("Shannon, C. E. (1948).", format_all(fields)["APA"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
