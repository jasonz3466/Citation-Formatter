"""Regression cases from the project review. No network or real user data."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from citation_formatter import app, library, lookup
from citation_formatter.citations import format_all, mla_page_range
from citation_formatter.output import format_source
from citation_formatter.validation import ValidationError, normalize_fields

BOOK = {'source_type': 'book', 'authors': 'Doe, Jane', 'title': 'Study Guide',
        'year': '2024', 'publisher': 'Example Press'}
WEB = {'source_type': 'website', 'authors': 'Berners-Lee, Tim',
       'title': 'Information Management: A Proposal', 'container': 'CERN',
       'published_date': '1989-03-14', 'url': 'https://example.org/source'}


class FormattingFixes(unittest.TestCase):
    def render(self, fields):
        return format_source(normalize_fields(fields))['styles']

    def test_website_publication_year_reaches_intext(self):
        cite = self.render(WEB)['APA']
        self.assertIn('(1989, March 14)', cite['text'])
        self.assertEqual(cite['intext'][0]['text'], '(Berners-Lee, 1989)')

    def test_partial_dates_and_legacy_date(self):
        for value, expected in [('1989', '(1989)'), ('1989-03', '(1989, March)')]:
            with self.subTest(value=value):
                self.assertIn(expected, self.render(dict(WEB, published_date=value))['APA']['text'])
        legacy = dict(WEB); legacy['access_date'] = legacy.pop('published_date')
        self.assertEqual(self.render(legacy)['APA']['intext'][0]['text'], '(Berners-Lee, 1989)')

    def test_organization_and_repeated_site_name(self):
        cite = self.render(dict(WEB, authors='World Health Organization',
                                author_mode='organization', container='World Health Organization'))['APA']
        self.assertTrue(cite['text'].startswith('World Health Organization.'))
        self.assertEqual(cite['text'].count('World Health Organization'), 1)
        self.assertIn('World Health Organization, 1989', cite['intext'][0]['text'])

    def test_organization_containing_and_is_not_split(self):
        name = 'Department of Health and Social Care'
        cite = self.render(dict(BOOK, author_mode='organization', authors=name))['MLA']['text']
        self.assertTrue(cite.startswith(name + '.'))

    def test_mixed_people_and_organization(self):
        cite = self.render(dict(BOOK, authors='Doe, Jane\n[Health and Science Council]'))['APA']['text']
        self.assertTrue(cite.startswith('Doe, J., & Health and Science Council.'))

    def test_suffix_survives_inversion_and_note(self):
        cites = self.render(dict(BOOK, authors='King, Martin Luther, Jr.'))
        self.assertTrue(cites['APA']['text'].startswith('King, M. L., Jr.'))
        self.assertTrue(cites['Chicago']['intext'][0]['text'].startswith('Martin Luther King, Jr.,'))

    def test_missing_author_moves_title_before_date(self):
        cite = self.render(dict(BOOK, authors='', author_mode='unknown'))['APA']
        self.assertTrue(cite['text'].startswith('Study guide. (2024).'))
        self.assertIn('<em>', cite['intext'][0]['html'])
        self.assertNotIn('"', cite['intext'][0]['text'])

    def test_edited_book_uses_editor_as_lead(self):
        cite = self.render(dict(BOOK, authors='', editors='Smith, Alex'))['APA']
        self.assertTrue(cite['text'].startswith('Smith, A. (Ed.). (2024).'))
        self.assertEqual(cite['intext'][0]['text'], '(Smith, 2024)')

    def test_question_mark_is_not_followed_by_extra_period(self):
        cite = self.render(dict(BOOK, source_type='article', title='Why study?', container='Example Journal'))['APA']
        self.assertIn('Why study?', cite['text'])
        self.assertNotIn('?.', cite['text'])
        self.assertNotIn('?.', cite['interactive_html'])

    def test_literal_asterisk_and_braces_survive_all_representations(self):
        title = 'A* Search {g:Literal} \\ paths'
        for style, cite in self.render(dict(BOOK, title=title, capitalization='preserve')).items():
            with self.subTest(style=style):
                self.assertIn(title, cite['text'])
                self.assertIn(title, cite['html'])
                self.assertNotIn('<button', cite['html'])

    def test_literal_title_markup_cannot_create_html(self):
        title = '<script>alert("x")</script> & <img src=x onerror=alert(1)>'
        for cite in self.render(dict(BOOK, title=title, capitalization='preserve')).values():
            self.assertIn(title, cite['text'])
            self.assertNotIn('<script>', cite['html'])
            self.assertNotIn('<img ', cite['html'])
            self.assertIn('&lt;', cite['html'])

    def test_page_range_uses_plural_and_appropriate_shortening(self):
        cite = self.render(dict(BOOK, cited_page='101-108'))
        self.assertEqual(cite['APA']['intext'][0]['text'], '(Doe, 2024, pp. 101–108)')
        self.assertEqual(cite['MLA']['intext'][0]['text'], '(Doe 101–08)')
        self.assertEqual(mla_page_range('100-104'), '100–04')

    def test_apa_chapter_combines_edition_pages_and_joins_editors(self):
        source = dict(BOOK, source_type='chapter', title='Study methods', container='Collected Studies',
                      editors='Smith, Alex\nBrown, Sam', edition='2', pages='101-108')
        cite = self.render(source)['APA']['text']
        self.assertIn('In A. Smith & S. Brown (Eds.)', cite)
        self.assertIn('(2nd ed., pp. 101–108)', cite)

    def test_source_specific_corrections_cover_chapter_container(self):
        source = dict(BOOK, source_type='chapter', container='Deep Learning with Keras',
                      case_overrides={'keras': 'common'})
        self.assertIn('Deep learning with keras', self.render(source)['APA']['text'])
        self.assertIn('Keras', self.render(dict(source, case_overrides={}))['APA']['text'])

    def test_preserve_mode_keeps_case_in_all_styles(self):
        title = 'unusual iPhone TITLE'
        for cite in self.render(dict(BOOK, title=title, capitalization='preserve')).values():
            self.assertIn(title, cite['text'])

    def test_undated_mla_webpage_has_no_nd_placeholder(self):
        cite = self.render(dict(WEB, published_date=''))['MLA']['text']
        self.assertNotIn('n.d.', cite)

    def test_chicago_full_notes_keep_doi_and_translation(self):
        cite = self.render(dict(BOOK, doi='10.1234/example', translators='Smith, Alex'))['Chicago']['intext'][0]['text']
        self.assertIn('trans. Alex Smith', cite)
        self.assertIn('https://doi.org/10.1234/example', cite)

    def test_chicago17_three_and_four_author_notes(self):
        three = dict(BOOK, authors='Doe, Jane\nSmith, Alex\nBrown, Sam')
        notes = self.render(three)['Chicago']['intext']
        self.assertIn('Doe, Smith, and Brown', notes[1]['text'])
        four = dict(three, authors=three['authors'] + '\nGreen, Pat')
        self.assertIn('Jane Doe et al.', self.render(four)['Chicago']['intext'][0]['text'])

    def test_article_doi_is_present_in_chicago_full_note(self):
        cite = self.render(dict(BOOK, source_type='article', container='Example Journal',
                                volume='1', issue='2', doi='10.1234/article'))['Chicago']['intext'][0]['text']
        self.assertIn('https://doi.org/10.1234/article', cite)

    def test_editor_led_book_consistent_in_mla_and_chicago(self):
        cites = self.render(dict(BOOK, authors='', editors='Smith, Alex'))
        self.assertTrue(cites['MLA']['text'].startswith('Smith, Alex, editor.'))
        self.assertTrue(cites['Chicago']['text'].startswith('Smith, Alex, ed.'))
        self.assertEqual(cites['MLA']['intext'][0]['text'], '(Smith)')



class ValidationFixes(unittest.TestCase):
    def test_impossible_dates_rejected(self):
        for value in ['2024-13-01', '2024-02-31', '2024-00-01', '2024-01-00', '0000', 'garbage']:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_fields(dict(WEB, published_date=value))

    def test_wrong_field_type_rejected(self):
        for value in [['Doe'], {'last': 'Doe'}, 42]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_fields(dict(BOOK, authors=value))

    def test_invalid_url_and_doi_rejected(self):
        for change in [{'url': 'javascript:alert(1)'}, {'url': 'not a url'}, {'doi': 'nonsense'}]:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                normalize_fields(dict(BOOK, **change))

    def test_unknown_author_is_intentional(self):
        result = format_all(normalize_fields(dict(BOOK, author_mode='unknown')))
        self.assertNotIn('authors', result['missing'])


class ApiAndStorage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(library, 'DATA_DIR', Path(self.temp.name))
        self.patch.start()
        self.client = app.app.test_client()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def save(self, fields=BOOK):
        response = self.client.post('/api/library', json={'fields': fields})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_all_routes_reject_nonobject_json(self):
        for path in ['/api/format', '/api/lookup', '/api/library', '/api/library/restore']:
            with self.subTest(path=path):
                response = self.client.post(path, json=['bad'])
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.is_json)

    def test_invalid_save_cannot_poison_existing_list(self):
        self.save()
        bad = self.client.post('/api/library', json={'fields': dict(WEB, published_date='2024-13-01')})
        self.assertEqual(bad.status_code, 400)
        response = self.client.get('/api/library')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['count'], 1)

    def test_no_title_is_not_saved(self):
        response = self.client.post('/api/library', json={'fields': {'year': '2024'}})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get('/api/library').get_json()['count'], 0)

    def test_edit_keeps_id_and_changes_one_entry(self):
        source_id = self.save()['saved_id']
        response = self.client.put('/api/library', json={'id': source_id, 'fields': dict(BOOK, title='Revised title')})
        result = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result['saved_id'], source_id)
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['entries'][0]['fields']['title'], 'Revised title')

    def test_duplicate_detected_but_different_edition_allowed(self):
        self.save()
        response = self.client.post('/api/library', json={'fields': dict(BOOK, cited_page='15')})
        self.assertEqual(response.status_code, 409)
        self.save(dict(BOOK, edition='2'))
        self.assertEqual(self.client.get('/api/library').get_json()['count'], 2)

    def test_same_doi_is_duplicate_even_with_metadata_variations(self):
        self.save(dict(BOOK, doi='10.1234/example'))
        response = self.client.post('/api/library', json={'fields': dict(BOOK, title='Other spelling', doi='https://doi.org/10.1234/EXAMPLE')})
        self.assertEqual(response.status_code, 409)

    def test_remove_and_undo_restore_original_id(self):
        source_id = self.save()['saved_id']
        removed = self.client.delete('/api/library', json={'id': source_id}).get_json()
        self.assertEqual(removed['count'], 0)
        restored = self.client.post('/api/library/restore', json={'ids': removed['removed_ids']}).get_json()
        self.assertEqual(restored['entries'][0]['id'], source_id)

    def test_clear_and_undo_restore_whole_list(self):
        self.save(); self.save(dict(BOOK, title='Second book'))
        removed = self.client.delete('/api/library', json={'id': '*'}).get_json()
        self.assertEqual(len(removed['removed_ids']), 2)
        restored = self.client.post('/api/library/restore', json={'ids': removed['removed_ids']})
        self.assertEqual(restored.get_json()['count'], 2)

    def test_undo_conflict_does_not_duplicate_active_source(self):
        source_id = self.save()['saved_id']
        self.client.delete('/api/library', json={'id': source_id})
        self.save()
        response = self.client.post('/api/library/restore', json={'ids': [source_id]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get('/api/library').get_json()['count'], 1)

    def test_apa_chronological_mla_title_order(self):
        self.save(dict(BOOK, title='Alpha', year='2024'))
        self.save(dict(BOOK, title='Zebra', year='2020'))
        apa = self.client.get('/api/library?style=APA').get_json()
        mla = self.client.get('/api/library?style=MLA').get_json()
        self.assertEqual([e['fields']['year'] for e in apa['entries']], ['2020', '2024'])
        self.assertEqual([e['fields']['title'] for e in mla['entries']], ['Alpha', 'Zebra'])
        self.assertEqual(apa['heading'], 'References')
        self.assertEqual(mla['heading'], 'Works Cited')

    def test_export_escapes_content_and_contains_only_list(self):
        self.save(dict(BOOK, title='A* <script>study</script>', capitalization='preserve'))
        response = self.client.get('/api/library/export?style=APA')
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response.headers['Content-Disposition'])
        self.assertIn('<h1>References</h1>', html)
        self.assertIn('<em>A* &lt;script&gt;study&lt;/script&gt;</em>', html)
        self.assertNotIn('out-MLA', html)
        self.assertNotIn('<script>', html)

    def test_legacy_json_migrates_once_and_preserves_original(self):
        path = Path(self.temp.name) / 'library.json'
        original = json.dumps([{'id': 'legacy', 'fields': BOOK}])
        path.write_text(original)
        self.assertEqual(self.client.get('/api/library').get_json()['count'], 1)
        self.assertEqual(self.client.get('/api/library').get_json()['count'], 1)
        self.assertEqual(path.read_text(), original)

    def test_corrupt_legacy_file_is_not_replaced(self):
        path = Path(self.temp.name) / 'library.json'; path.write_text('{broken')
        response = self.client.post('/api/library', json={'fields': BOOK})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(path.read_text(), '{broken')

    def test_corrupt_sqlite_file_is_not_replaced(self):
        path = Path(self.temp.name) / 'library.sqlite3'; path.write_bytes(b'not a sqlite database')
        response = self.client.post('/api/library', json={'fields': BOOK})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(path.read_bytes(), b'not a sqlite database')

    def test_concurrent_saves_keep_both_sources(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(library.upsert, [dict(BOOK, title='Alpha'), dict(BOOK, title='Beta')]))
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(len(library.load()), 2)

    def test_concurrent_duplicate_is_rejected_transactionally(self):
        def attempt(_):
            try:
                library.upsert(BOOK)
                return 'saved'
            except library.DuplicateSource:
                return 'duplicate'
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(attempt, range(2))), ['saved', 'duplicate'])

    def test_oversize_body_returns_json(self):
        response = self.client.post('/api/format', json={'title': 'x' * 150000})
        self.assertEqual(response.status_code, 413)
        self.assertTrue(response.is_json)

    def test_health_check_and_browser_headers(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'ok')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_lookup_service_failure_keeps_its_http_status(self):
        failure = lookup.LookupError_("Service unavailable.", 503)
        with patch.object(lookup, 'lookup', side_effect=failure):
            response = self.client.post('/api/lookup', json={'identifier': '10.1234/test'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['error'], 'Service unavailable.')

    def test_database_adds_a_fingerprint_index(self):
        self.save()
        with library.database() as connection:
            indexes = {
                row['name']
                for row in connection.execute("SELECT name FROM pragma_index_list('sources')")
            }
        self.assertIn('source_fingerprint_idx', indexes)


class LookupFixes(unittest.TestCase):
    def test_isbn_checksum(self):
        self.assertTrue(lookup.looks_like_isbn('978-0-321-97361-0'))
        self.assertTrue(lookup.looks_like_isbn('0-306-40615-2'))
        self.assertFalse(lookup.looks_like_isbn('9780321973611'))
        self.assertFalse(lookup.looks_like_isbn('letters9780321973610'))

    def test_doi_book_is_a_book_with_subtitle(self):
        record = {'message': {'type': 'book', 'title': ['Example'], 'subtitle': ['A subtitle']}}
        with patch.object(lookup, 'fetch_json', return_value=record):
            fields = lookup.from_crossref('10.1234/book')
        self.assertEqual(fields['source_type'], 'book')
        self.assertEqual(fields['title'], 'Example: A subtitle')

    def test_unsupported_doi_type_is_explained(self):
        with patch.object(lookup, 'fetch_json', return_value={'message': {'type': 'report'}}):
            with self.assertRaises(lookup.LookupError_):
                lookup.from_crossref('10.1234/report')

    def test_group_author_and_article_number_preserved(self):
        record = {'message': {'type': 'journal-article', 'author': [{'name': 'Health and Science Council'}], 'article-number': 'e123'}}
        with patch.object(lookup, 'fetch_json', return_value=record):
            fields = lookup.from_crossref('10.1234/article')
        self.assertEqual(fields['authors'], '[Health and Science Council]')
        self.assertEqual(fields['article_number'], 'e123')


if __name__ == '__main__':
    unittest.main()
