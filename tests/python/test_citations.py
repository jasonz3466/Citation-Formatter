"""Tests for the formatting rules. No server needed.

    uv run python -m unittest tests/python/test_citations.py
"""

import unittest

from citation_formatter.citations import (
    classify_word,
    split_author_line,
    looks_like_title_case,
    condense_page_range,
    format_all,
    format_authors_apa,
    format_authors_chicago,
    format_authors_mla,
    normalize_edition,
    ordinal,
    parse_author_list,
    to_initials,
    to_sentence_case,
    to_title_case,
)

EN_DASH = "\u2013"


class TestCapitalization(unittest.TestCase):

    def test_title_case_lowercases_interior_particles(self):
        self.assertEqual(
            to_title_case("the lord of the rings"),
            "The Lord of the Rings",
        )

    def test_title_case_capitalizes_after_colon(self):
        self.assertEqual(
            to_title_case("the lord of the rings: the return of the king"),
            "The Lord of the Rings: The Return of the King",
        )

    def test_title_case_always_capitalizes_the_last_word(self):
        # "of" is normally lowercase, but not in final position.
        self.assertEqual(to_title_case("something to think of"), "Something to Think Of")

    def test_title_case_protects_acronyms(self):
        self.assertEqual(to_title_case("the DNA of PostgreSQL"), "The DNA of PostgreSQL")

    def test_sentence_case_flattens_the_middle(self):
        self.assertEqual(
            to_sentence_case("The Lord of the Rings: The Return of the King"),
            "The lord of the rings: The return of the king",
        )

    def test_sentence_case_protects_internal_caps(self):
        self.assertEqual(
            to_sentence_case("A Study of iPhone and DNA"),
            "A study of iPhone and DNA",
        )


class TestTitleCaseDetection(unittest.TestCase):

    def test_title_case_is_recognized(self):
        self.assertTrue(looks_like_title_case("The Lord of the Rings: The Return of the King"))

    def test_natural_capitals_are_recognized(self):
        self.assertFalse(looks_like_title_case("deep learning with Python in Southeast Asia"))

    def test_short_titles_fall_back_to_guessing(self):
        # Too few content words to read anything into the capitals.
        self.assertTrue(looks_like_title_case("Climate Change"))

    def test_typed_capitals_are_left_alone(self):
        self.assertEqual(
            to_sentence_case("bridges of New York City: an engineering survey"),
            "Bridges of New York City: An engineering survey",
        )

    def test_nothing_is_flagged_when_the_capitals_are_trusted(self):
        marked = to_sentence_case("deep learning with Python in Southeast Asia", mark=True)
        self.assertNotIn("{g:", marked)

    def test_an_override_still_applies_to_a_trusted_title(self):
        self.assertIn("Keras", to_sentence_case(
            "deep learning with keras for image recognition", {"keras": "proper"}))


class TestProperNouns(unittest.TestCase):

    def test_known_names_are_kept(self):
        self.assertEqual(
            to_sentence_case("The Effects of Climate Change on Coastal Cities in Southeast Asia"),
            "The effects of climate change on coastal cities in Southeast Asia",
        )

    def test_ordinary_words_are_lowered(self):
        self.assertEqual(
            to_sentence_case("A Mathematical Theory of Communication"),
            "A mathematical theory of communication",
        )

    def test_unknown_words_are_assumed_to_be_names(self):
        self.assertEqual(classify_word("Kolmogorov", {}), "unknown")
        self.assertIn("Kolmogorov", to_sentence_case("On the Kolmogorov Bound"))

    def test_an_override_beats_the_word_lists(self):
        self.assertEqual(classify_word("bill", {}), "common")
        self.assertEqual(classify_word("bill", {"bill": "proper"}), "proper")

    def test_overrides_change_the_output(self):
        title = "Deep Learning with Keras"
        self.assertEqual(to_sentence_case(title, {"keras": "common"}),
                         "Deep learning with keras")
        self.assertEqual(to_sentence_case(title, {"learning": "proper"}),
                         "Deep Learning with Keras")

    def test_marking_wraps_guesses_and_confident_words_differently(self):
        marked = to_sentence_case("A Study of Paris", mark=True)
        self.assertIn("{g:Paris}", marked)     # guessed proper noun
        self.assertIn("{p:study}", marked)     # confident common word

    def test_the_forced_first_word_is_not_clickable(self):
        # It's capitalized by rule, not by guess, so there's nothing to toggle.
        self.assertTrue(to_sentence_case("Paris in the Spring", mark=True).startswith("Paris "))

    def test_a_word_beside_a_name_is_flagged_as_uncertain(self):
        # "city" stays lowercase but is marked, because names run in groups.
        self.assertIn("{g:city}", to_sentence_case("Bridges of New York City Today", mark=True))

    def test_markers_are_absent_by_default(self):
        self.assertNotIn("{", to_sentence_case("A Study of Paris"))


class TestAuthors(unittest.TestCase):

    def parse(self, text):
        return parse_author_list(text)

    def test_accepts_both_name_orders(self):
        inverted = self.parse("Tolkien, J. R. R.")[0]
        natural = self.parse("J. R. R. Tolkien")[0]
        self.assertEqual(inverted["last"], "Tolkien")
        self.assertEqual(natural["last"], "Tolkien")

    def test_initials_from_full_given_names(self):
        self.assertEqual(to_initials("John Ronald Reuel"), "J. R. R.")

    def test_initials_keep_hyphens(self):
        self.assertEqual(to_initials("Jean-Paul"), "J.-P.")

    def test_apa_two_authors_use_ampersand(self):
        authors = self.parse("Shannon, Claude E.\nWeaver, Warren")
        self.assertEqual(format_authors_apa(authors), "Shannon, C. E., & Weaver, W.")

    def test_apa_three_authors_keep_comma_before_ampersand(self):
        authors = self.parse("A, Ann\nB, Ben\nC, Cara")
        self.assertEqual(format_authors_apa(authors), "A, A., B, B., & C, C.")

    def test_mla_gives_up_at_three_authors(self):
        authors = self.parse("A, Ann\nB, Ben\nC, Cara")
        self.assertEqual(format_authors_mla(authors), "A, Ann, et al.")

    def test_mla_second_author_is_not_inverted(self):
        authors = self.parse("Shannon, Claude\nWeaver, Warren")
        self.assertEqual(format_authors_mla(authors), "Shannon, Claude, and Warren Weaver")

    def test_chicago_lists_all_three(self):
        authors = self.parse("A, Ann\nB, Ben\nC, Cara")
        self.assertEqual(format_authors_chicago(authors), "A, Ann, Ben B, and Cara C")

    def test_organization_name_survives_intact(self):
        authors = self.parse("UNESCO")
        self.assertEqual(format_authors_apa(authors), "UNESCO")


class TestMessyAuthorInput(unittest.TestCase):
    """Several authors crammed onto one line should not be read as one name."""

    EXPECTED = ["Hugh D. Young", "Roger A. Freedman"]

    def test_comma_separated_names_are_split(self):
        self.assertEqual(split_author_line("Hugh D. Young, Roger A. Freedman"), self.EXPECTED)

    def test_and_separates_authors(self):
        self.assertEqual(split_author_line("Hugh D. Young and Roger A. Freedman"), self.EXPECTED)

    def test_ampersand_separates_authors(self):
        self.assertEqual(split_author_line("Hugh D. Young & Roger A. Freedman"), self.EXPECTED)

    def test_semicolons_separate_inverted_names(self):
        self.assertEqual(split_author_line("Young, Hugh D.; Freedman, Roger A."),
                         ["Young, Hugh D.", "Freedman, Roger A."])

    def test_an_inverted_name_is_left_alone(self):
        # The comma here is part of the name, not a separator.
        self.assertEqual(split_author_line("Young, Hugh D."), ["Young, Hugh D."])

    def test_a_spelled_out_middle_name_is_left_alone(self):
        self.assertEqual(split_author_line("Young, Hugh David"), ["Young, Hugh David"])

    def test_a_suffix_does_not_start_a_new_author(self):
        self.assertEqual(split_author_line("Young, Hugh D., Jr."), ["Young, Hugh D., Jr."])

    def test_every_input_shape_gives_the_same_citation(self):
        book = {"source_type": "book", "title": "University Physics with Modern Physics",
                "edition": "16", "publisher": "Pearson", "city": "New York", "year": "2026"}
        shapes = ["Young, Hugh D.\nFreedman, Roger A.",
                  "Hugh D. Young\nRoger A. Freedman",
                  "Hugh D. Young, Roger A. Freedman",
                  "Hugh D. Young and Roger A. Freedman",
                  "Young, Hugh D.; Freedman, Roger A."]
        results = {format_all(dict(book, authors=shape))["MLA"] for shape in shapes}
        self.assertEqual(len(results), 1, results)


class TestUniversityPhysics(unittest.TestCase):
    """The worked example from the style guides, checked against all three."""

    SOURCE = {"source_type": "book", "authors": "Young, Hugh D.\nFreedman, Roger A.",
              "title": "University Physics with Modern Physics", "edition": "16",
              "publisher": "Pearson", "city": "New York", "year": "2026"}

    def test_apa(self):
        self.assertEqual(
            format_all(self.SOURCE)["APA"],
            "Young, H. D., & Freedman, R. A. (2026). "
            "*University physics with modern physics* (16th ed.). Pearson.",
        )

    def test_mla(self):
        self.assertEqual(
            format_all(self.SOURCE)["MLA"],
            "Young, Hugh D., and Roger A. Freedman. "
            "*University Physics with Modern Physics*. 16th ed., Pearson, 2026.",
        )

    def test_chicago(self):
        self.assertEqual(
            format_all(self.SOURCE)["Chicago"],
            "Young, Hugh D., and Roger A. Freedman. "
            "*University Physics with Modern Physics*. 16th ed. New York: Pearson, 2026.",
        )


class TestNumbers(unittest.TestCase):

    def test_ordinals_handle_the_teens(self):
        self.assertEqual(
            [ordinal(n) for n in (1, 2, 3, 11, 12, 13, 21, 102)],
            ["1st", "2nd", "3rd", "11th", "12th", "13th", "21st", "102nd"],
        )

    def test_edition_accepts_digits_or_words(self):
        self.assertEqual(normalize_edition("2"), "2nd ed.")
        self.assertEqual(normalize_edition("3rd edition"), "3rd ed.")
        self.assertEqual(normalize_edition("revised"), "Revised ed.")
        self.assertEqual(normalize_edition(""), "")

    def test_page_ranges_follow_chicago_9_61(self):
        cases = {
            "71-72": f"71{EN_DASH}72",          # under 100
            "100-104": f"100{EN_DASH}104",      # multiple of 100
            "101-108": f"101{EN_DASH}8",        # starts 01-09
            "808-833": f"808{EN_DASH}33",
            "321-328": f"321{EN_DASH}28",       # the ordinary case
            "498-532": f"498{EN_DASH}532",      # crosses a hundred
            "1087-1089": f"1087{EN_DASH}89",    # two-digit floor
            "1496-1500": f"1496{EN_DASH}500",   # crosses a thousand
        }
        for raw, expected in cases.items():
            with self.subTest(pages=raw):
                self.assertEqual(condense_page_range(raw), expected)

    def test_single_page_passes_through(self):
        self.assertEqual(condense_page_range("45"), "45")


class TestWholeCitations(unittest.TestCase):

    BOOK = {
        "source_type": "book",
        "authors": "Tolkien, J. R. R.",
        "title": "the lord of the rings: the return of the king",
        "publisher": "Allen & Unwin",
        "city": "London",
        "year": "1955",
        "edition": "2",
    }

    ARTICLE = {
        "source_type": "article",
        "authors": "Shannon, Claude E.",
        "title": "A Mathematical Theory of Communication",
        "container": "the bell system technical journal",
        "year": "1948",
        "volume": "27",
        "issue": "3",
        "pages": "379-423",
        "doi": "10.1002/j.1538-7305.1948.tb01338.x",
    }

    def test_apa_book(self):
        self.assertEqual(
            format_all(self.BOOK)["APA"],
            "Tolkien, J. R. R. (1955). *The lord of the rings: The return of the king* "
            "(2nd ed.). Allen & Unwin.",
        )

    def test_mla_book(self):
        self.assertEqual(
            format_all(self.BOOK)["MLA"],
            "Tolkien, J. R. R. *The Lord of the Rings: The Return of the King*. "
            "2nd ed., Allen & Unwin, 1955.",
        )

    def test_chicago_book_includes_the_city(self):
        self.assertIn("London: Allen & Unwin, 1955.", format_all(self.BOOK)["Chicago"])

    def test_chicago_article_has_no_comma_before_the_volume(self):
        chicago = format_all(self.ARTICLE)["Chicago"]
        self.assertIn("*The Bell System Technical Journal* 27, no. 3 (1948):", chicago)

    def test_apa_italicizes_volume_but_not_issue(self):
        self.assertIn("*27*(3)", format_all(self.ARTICLE)["APA"])

    def test_doi_becomes_a_full_link(self):
        for style in ("APA", "MLA", "Chicago"):
            with self.subTest(style=style):
                self.assertIn("https://doi.org/10.1002/", format_all(self.ARTICLE)[style])

    def test_missing_fields_produce_warnings_not_crashes(self):
        result = format_all({"source_type": "book", "title": "Untitled"})
        self.assertIn("author", result["warnings"])
        self.assertIn("Untitled", result["APA"])

    def test_empty_input_does_not_crash(self):
        result = format_all({})
        self.assertIsInstance(result["APA"], str)

    def test_no_stray_punctuation_when_fields_are_blank(self):
        citation = format_all({"source_type": "book", "authors": "Doe, Jane",
                               "title": "A Title"})["MLA"]
        self.assertNotIn(" ,", citation)
        self.assertNotIn("..", citation)


class TestChapters(unittest.TestCase):

    SOURCE = {"source_type": "chapter", "authors": "Turing, Alan M.",
              "editors": "Copeland, B. Jack",
              "title": "Computing Machinery and Intelligence",
              "container": "The Essential Turing", "publisher": "Oxford University Press",
              "city": "Oxford", "year": "2004", "pages": "433-464"}

    def test_apa_puts_the_editor_before_the_book(self):
        self.assertIn("In B. J. Copeland (Ed.), *The essential Turing* (pp. 433\u2013464).",
                      format_all(self.SOURCE)["APA"])

    def test_mla_names_the_editor_in_reading_order(self):
        self.assertIn("edited by B. Jack Copeland", format_all(self.SOURCE)["MLA"])

    def test_chicago_names_the_editor_and_drops_pp(self):
        self.assertIn("In *The Essential Turing*, edited by B. Jack Copeland, 433\u201364.",
                      format_all(self.SOURCE)["Chicago"])


class TestContributors(unittest.TestCase):

    SOURCE = {"source_type": "book", "authors": "Homer", "editors": "Knox, Bernard",
              "translators": "Fagles, Robert", "title": "The Odyssey",
              "publisher": "Penguin", "city": "New York", "year": "1996"}

    def test_apa_brackets_both_roles(self):
        self.assertIn("(B. Knox, Ed.; R. Fagles, Trans.)", format_all(self.SOURCE)["APA"])

    def test_mla_capitalizes_what_follows_the_title(self):
        self.assertIn(". Edited by Bernard Knox, translated by Robert Fagles,",
                      format_all(self.SOURCE)["MLA"])

    def test_chicago_gives_each_role_its_own_sentence(self):
        self.assertIn(". Edited by Bernard Knox. Translated by Robert Fagles.",
                      format_all(self.SOURCE)["Chicago"])


class TestInTextCitations(unittest.TestCase):

    BOOK = {"source_type": "book", "authors": "Young, Hugh D.\nFreedman, Roger A.",
            "title": "University Physics with Modern Physics", "edition": "16",
            "publisher": "Pearson", "city": "New York", "year": "2026", "cited_page": "412"}

    ARTICLE = {"source_type": "article", "authors": "Shannon, Claude E.",
               "title": "A Mathematical Theory of Communication",
               "container": "Bell System Technical Journal", "year": "1948",
               "volume": "27", "issue": "3", "cited_page": "380"}

    def forms(self, source, style):
        return {form["label"]: form["text"] for form in format_all(source)["intext"][style]}

    def test_apa_uses_an_ampersand_in_parentheses_and_and_in_prose(self):
        forms = self.forms(self.BOOK, "APA")
        self.assertEqual(forms["Parenthetical"], "(Young & Freedman, 2026, p. 412)")
        self.assertEqual(forms["Narrative"], "Young and Freedman (2026, p. 412)")

    def test_mla_gives_a_page_and_no_year(self):
        forms = self.forms(self.BOOK, "MLA")
        self.assertEqual(forms["Parenthetical"], "(Young and Freedman 412)")

    def test_three_authors_become_et_al(self):
        source = dict(self.BOOK, authors="A, Ann\nB, Ben\nC, Cara")
        self.assertEqual(self.forms(source, "APA")["Parenthetical"], "(A et al., 2026, p. 412)")

    def test_a_missing_year_becomes_nd(self):
        source = dict(self.BOOK, year="", cited_page="")
        self.assertEqual(self.forms(source, "APA")["Parenthetical"], "(Young & Freedman, n.d.)")

    def test_a_chicago_note_is_not_the_bibliography_entry(self):
        note = self.forms(self.BOOK, "Chicago")["Full note"]
        # Names in reading order, details in parentheses, commas not periods.
        self.assertTrue(note.startswith("Hugh D. Young and Roger A. Freedman,"))
        self.assertIn("(New York: Pearson, 2026), 412.", note)

    def test_a_shortened_note_trims_the_title_at_a_particle(self):
        self.assertEqual(self.forms(self.BOOK, "Chicago")["Shortened note"],
                         "Young and Freedman, *University Physics*, 412.")

    def test_an_article_note_puts_the_comma_inside_the_quotes(self):
        note = self.forms(self.ARTICLE, "Chicago")["Full note"]
        self.assertIn('"A Mathematical Theory of Communication," ', note)
        self.assertNotIn('",', note)

    def test_a_source_with_no_author_falls_back_to_the_title(self):
        source = {"source_type": "website", "title": "Information Management: A Proposal",
                  "container": "CERN", "year": "1989"}
        self.assertIn("Information Management", self.forms(source, "APA")["Parenthetical"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
