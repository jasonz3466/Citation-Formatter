"""Citation rules for APA 7, MLA 9, and Chicago 17.

The formatter returns a small internal markup format. Asterisks mean italics,
and output.py is the only place that turns that markup into browser HTML.
"""

import re
from datetime import date
from pathlib import Path

from .output import plain_text

# Kept lowercase in a title-cased title, unless first, last, or after a colon.
LOWERCASE_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "but",
    "or",
    "nor",
    "for",
    "so",
    "yet",
    "as",
    "at",
    "by",
    "down",
    "from",
    "in",
    "into",
    "like",
    "near",
    "of",
    "off",
    "on",
    "onto",
    "out",
    "over",
    "past",
    "per",
    "than",
    "to",
    "up",
    "upon",
    "via",
    "with",
    "within",
    "without",
    "about",
    "above",
    "across",
    "after",
    "against",
    "along",
    "among",
    "around",
    "before",
    "behind",
    "below",
    "beneath",
    "beside",
    "between",
    "beyond",
    "during",
    "except",
    "inside",
    "outside",
    "through",
    "throughout",
    "under",
    "until",
}

EN_DASH = "\u2013"

RESOURCE_DIR = Path(__file__).with_name("resources")


def load_word_list(filename):
    """Read one word per line into a set. Returns an empty set if the file is missing."""
    try:
        with (RESOURCE_DIR / filename).open(encoding="utf-8") as handle:
            return {line.strip() for line in handle if line.strip()}
    except OSError:
        return set()


# proper_nouns.txt holds words that appear only capitalized in a dictionary,
# so they're probably names. common_words.txt holds ordinary English words.
PROPER_NOUNS = load_word_list("proper_nouns.txt")
COMMON_WORDS = load_word_list("common_words.txt")


# --- string helpers -------------------------------------------------------


def has_internal_caps(word):
    """Rough proper-noun test: protects DNA, iPhone, PostgreSQL from being flattened."""
    stripped = re.sub(r"[^A-Za-z]", "", word)
    return any(character.isupper() for character in stripped[1:])


def capitalize_first_letter(word):
    """Uppercase the first letter, leave the rest alone. str.capitalize() would wreck 'DNA'."""
    for index, character in enumerate(word):
        if character.isalpha():
            return word[:index] + character.upper() + word[index + 1 :]
    return word


def to_title_case(title):
    """Title Case for MLA and Chicago.

    >>> to_title_case("the lord of the rings: the return of the king")
    'The Lord of the Rings: The Return of the King'
    """
    if not title:
        return ""

    words = title.split()
    result = []
    force_next = True  # true for the first word and anything after a colon

    for index, word in enumerate(words):
        is_last = index == len(words) - 1

        if has_internal_caps(word):
            result.append(word)
        elif force_next or is_last:
            result.append(capitalize_first_letter(word))
        elif word.lower().strip(".,;") in LOWERCASE_WORDS:
            result.append(word.lower())
        else:
            result.append(capitalize_first_letter(word))

        force_next = word.endswith(":")

    return " ".join(result)


# A title needs at least this many content words before its capitalization is
# worth reading, and this share of them capitalized to count as Title Case.
MIN_CONTENT_WORDS = 4
TITLE_CASE_SHARE = 0.8


def word_key(word):
    """Strip a title word down to the key used for word lists and overrides."""
    text = word.replace("’", "'").split("'")[0]
    return "".join(c for c in text if c.isalpha() or c == "-").strip("-").lower()


def looks_like_title_case(title):
    """True if the title is in Title Case rather than the writer's own capitals.

    Only content words count. The first word and anything after a colon is
    capitalized either way, particles like "of" are lowercase either way, and
    words like iPhone carry no signal. Short titles are too ambiguous to call,
    so they're treated as Title Case and go through the guessing.

    >>> looks_like_title_case("The Lord of the Rings: The Return of the King")
    True
    >>> looks_like_title_case("deep learning with Python in Southeast Asia")
    False
    """
    content = []
    force = True

    for word in title.split():
        bare = re.sub(r"[^A-Za-z]", "", word)
        informative = (
            bare
            and not force
            and not has_internal_caps(bare)
            and bare.lower() not in LOWERCASE_WORDS
        )
        if informative:
            content.append(bare)
        force = word.endswith((":", "?", "!", "\u2014", EN_DASH))

    if len(content) < MIN_CONTENT_WORDS:
        return True

    capitalized = sum(1 for word in content if word[0].isupper())
    return capitalized / len(content) >= TITLE_CASE_SHARE


def classify_word(word, overrides):
    """Guess what a title word is: 'proper', 'common', or 'unknown'.

    Checks your saved overrides first, so a word you've corrected once stays corrected.
    """
    bare = re.sub(r"[^A-Za-z'-]", "", word).split("'")[0].strip("-")
    if not bare:
        return "common"

    key = word_key(word)
    if key in overrides:
        return overrides[key]
    if has_internal_caps(bare):
        return "proper"
    if not COMMON_WORDS:
        return "common"  # word lists missing, so fall back to plain sentence case
    if bare.capitalize() in PROPER_NOUNS:
        return "proper"
    if key in COMMON_WORDS:
        return "common"
    return "unknown"  # in neither list, so more likely a name than a noun


def to_sentence_case(title, overrides=None, mark=False):
    """Sentence case for APA titles.

    English only capitalizes proper nouns, so if the title was typed normally its
    capitals already say which words are names and nothing needs guessing. The
    word lists are only consulted for Title Case input, where that signal is gone.

    With mark=True, each guessed word is wrapped in {g:...} and each confident one
    in {p:...} so the page can underline the guesses and make every word clickable.

    >>> to_sentence_case("The Lord of the Rings: The Return of the King")
    'The lord of the rings: The return of the king'
    >>> to_sentence_case("bridges of New York City: an engineering survey")
    'Bridges of New York City: An engineering survey'
    """
    overrides = overrides or {}
    if not title:
        return ""

    words = title.split()
    guessing = looks_like_title_case(title)

    # Classify every word first; the marking pass below needs to see neighbours.
    kinds = []
    force = True
    for word in words:
        if force:
            kinds.append("forced")
        elif guessing:
            kinds.append(classify_word(word, overrides))
        else:
            # Trust what was typed, but a saved correction still wins.
            kinds.append(overrides.get(word_key(word), "typed"))
        force = word.endswith((":", "?", "!", "\u2014", EN_DASH))

    # A common word next to a name is often part of it ("New York City"), so flag
    # it as uncertain without changing its case.
    uncertain = set()
    for index, kind in enumerate(kinds if guessing else []):
        if kind in ("proper", "unknown"):
            uncertain.update({index - 1, index + 1})
    # "of" and "in" are never part of a name, so don't flag them.
    uncertain = {
        index
        for index in uncertain
        if 0 <= index < len(words)
        and words[index].lower().strip(".,;:") not in LOWERCASE_WORDS
    }

    result = []
    for index, (word, kind) in enumerate(zip(words, kinds)):
        if kind == "forced":
            result.append(
                word
                if has_internal_caps(word)
                else capitalize_first_letter(word.lower())
            )
            continue

        if kind == "typed":
            result.append(f"{{p:{word}}}" if mark else word)
            continue

        if kind in ("proper", "unknown"):
            # Leave iPhone and TensorFlow exactly as typed.
            text = word if has_internal_caps(word) else capitalize_first_letter(word)
            marker = "g"
        else:
            text, marker = word.lower(), "g" if index in uncertain else "p"

        result.append(f"{{{marker}:{text}}}" if mark else text)

    return " ".join(result)


def ordinal(number):
    """3 -> '3rd'. The teens are the exception: 11th, not 11st.

    >>> [ordinal(n) for n in (1, 2, 3, 11, 12, 13, 21)]
    ['1st', '2nd', '3rd', '11th', '12th', '13th', '21st']
    """
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def normalize_edition(raw):
    """'2' or '2nd edition' -> '2nd ed.'; 'revised' -> 'Revised ed.'"""
    raw = (raw or "").strip()
    if not raw:
        return ""

    match = re.match(r"^(\d+)", raw)
    if match:
        return f"{ordinal(int(match.group(1)))} ed."

    cleaned = re.sub(r"\s*\b(ed|eds|edition)\b\.?\s*$", "", raw, flags=re.I).strip()
    return f"{capitalize_first_letter(cleaned)} ed."


def condense_page_range(pages):
    """Shorten the second number, per Chicago 9.61. MLA follows the same rules; APA doesn't.

    >>> [condense_page_range(p) for p in ("71-72", "101-108", "808-833")]
    ['71\u201372', '101\u20138', '808\u201333']
    >>> [condense_page_range(p) for p in ("321-328", "498-532", "1496-1500")]
    ['321\u201328', '498\u2013532', '1496\u2013500']
    """
    pages = (pages or "").strip()
    if not pages:
        return ""

    parts = re.split(r"\s*(?:-{1,2}|\u2013|\u2014|\bto\b)\s*", pages, maxsplit=1)
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        # Single page, roman numerals, or something unexpected. Leave it alone.
        return pages.replace("-", EN_DASH)

    start_text, end_text = parts[0], parts[1]
    start = int(start_text)

    if start < 100 or start % 100 == 0:
        condensed = end_text
    else:
        # Both remaining rules drop the digits the two numbers share.
        shared = 0
        if len(start_text) == len(end_text):
            while shared < len(start_text) and start_text[shared] == end_text[shared]:
                shared += 1
        remainder = end_text[shared:]

        if 1 <= start % 100 <= 9:
            condensed = remainder or end_text
        else:
            # Two digits minimum, more when the range crosses a hundred.
            condensed = remainder if len(remainder) >= 2 else end_text[-2:]

    return f"{start_text}{EN_DASH}{condensed}"


def full_page_range(pages):
    """APA keeps every digit. 123-145 -> 123-145 with an en dash."""
    pages = (pages or "").strip()
    return re.sub(r"\s*(?:-{1,2}|\u2013|\u2014|\bto\b)\s*", EN_DASH, pages)


def mla_page_range(pages):
    normalized = full_page_range(pages)
    match = re.fullmatch(r"(\d+)–(\d+)", normalized)
    if not match:
        return normalized
    start, end = match.groups()
    if int(end) <= int(start) or len(start) != len(end) or int(end) < 100:
        return normalized
    shared = 0
    while shared < len(end) - 2 and start[shared] == end[shared]:
        shared += 1
    return start + EN_DASH + end[shared:]


def sentence_title(data, field):
    if data.get("capitalization") == "preserve":
        return data[field]
    return to_sentence_case(data[field], data["overrides"], data["mark"])


def headline_title(data, field):
    if data.get("capitalization") == "preserve":
        return data[field]
    return to_title_case(data[field])


def apa_lead(data, authors, year, title):
    """No author moves the title before the date."""
    if authors:
        return [terminate(authors), f"{year}.", terminate(title)]
    return [terminate(title), f"{year}."]


def italic(text):
    return f"*{text}*" if text else ""


# --- authors --------------------------------------------------------------

# Suffixes that follow a comma without starting a new author.
NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "esq"}


def looks_like_full_name(segment):
    """True if a comma-separated segment carries its own surname.

    'Roger A. Freedman' does, so the comma before it separated two authors.
    'Hugh D.' and 'Jr.' don't, so the comma was part of one 'Last, First' name.
    """
    tokens = segment.split()
    if len(tokens) < 2 or tokens[-1].rstrip(".").lower() in NAME_SUFFIXES:
        return False
    ends_in_initial = len(tokens[-1].rstrip(".")) == 1
    has_initial = any(len(token.rstrip(".")) == 1 for token in tokens[:-1])
    return has_initial and not ends_in_initial


def split_author_line(line):
    """Split one line into separate authors.

    Semicolons, 'and', and '&' always separate people. A comma usually doesn't —
    'Young, Hugh D.' is one author — so it only splits when every side of the
    comma carries a surname of its own. 'Copeland' alone doesn't, so
    'Copeland, B. Jack' stays whole.
    """
    authors = []
    for part in re.split(r"\s*;\s*|\s+&\s+|\s+\band\b\s+", line):
        segments = [segment.strip() for segment in part.split(",") if segment.strip()]
        if len(segments) > 1 and all(looks_like_full_name(s) for s in segments):
            authors.extend(segments)
        elif part.strip():
            authors.append(part.strip())
    return authors


def parse_author(raw):
    """Accept Last, First, Suffix; [Organization]; or a natural personal name."""
    raw = raw.strip().rstrip(",")
    if not raw:
        return None
    if raw.startswith("[") and raw.endswith("]"):
        return {"last": raw[1:-1].strip(), "given": "", "is_organization": True}
    suffix = ""
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) >= 2 and parts[-1].rstrip(".").lower() in NAME_SUFFIXES:
        suffix = parts.pop()
        raw = ", ".join(parts)
    if "," in raw:
        last, given = raw.split(",", 1)
    else:
        tokens = raw.split()
        if len(tokens) > 1 and tokens[-1].rstrip(".").lower() in NAME_SUFFIXES:
            suffix = tokens.pop()
        if len(tokens) == 1:
            return {"last": tokens[0], "given": "", "is_organization": True}
        last, given = tokens[-1], " ".join(tokens[:-1])
    person = {"last": last.strip(), "given": given.strip(), "is_organization": False}
    if suffix:
        person["suffix"] = suffix
    return person


def parse_author_list(raw_block):
    """One author per line; square brackets protect a mixed-in organization."""
    if not raw_block:
        return []
    names = []
    for line in raw_block.splitlines():
        if line.strip().startswith("[") and line.strip().endswith("]"):
            names.append(line.strip())
        else:
            names.extend(split_author_line(line))
    return [author for author in (parse_author(name) for name in names) if author]


def natural_name(author):
    name = f"{author['given']} {author['last']}".strip()
    return name + (f", {author['suffix']}" if author.get("suffix") else "")


def inverted_name(author):
    name = f"{author['last']}, {author['given']}" if author["given"] else author["last"]
    return name + (f", {author['suffix']}" if author.get("suffix") else "")


def to_initials(given):
    """'John Ronald Reuel' -> 'J. R. R.'; 'Jean-Paul' -> 'J.-P.'"""
    if not given:
        return ""

    pieces = []
    for token in given.replace(".", " ").split():
        if "-" in token:
            halves = [part[0].upper() + "." for part in token.split("-") if part]
            pieces.append("-".join(halves))
        else:
            pieces.append(token[0].upper() + ".")
    return " ".join(pieces)


def format_authors_apa(authors):
    """1: 'Last, F. M.'  2: 'A, & B'  3-20: all, & before last  21+: first 19, ..., last."""
    if not authors:
        return ""

    def one(author):
        if author.get("is_organization"):
            return author["last"]
        initials = to_initials(author["given"])
        name = f"{author['last']}, {initials}" if initials else author["last"]
        return name + (f", {author['suffix']}" if author.get("suffix") else "")

    names = [one(author) for author in authors]

    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}, & {names[1]}"
    if len(names) <= 20:
        return ", ".join(names[:-1]) + f", & {names[-1]}"
    return ", ".join(names[:19]) + ", ... " + names[-1]


def format_authors_mla(authors):
    """1: 'Last, First'  2: 'Last, First, and First Last'  3+: 'Last, First, et al.'"""
    if not authors:
        return ""

    def inverted(author):
        return inverted_name(author)

    def natural(author):
        return natural_name(author)

    if len(authors) == 1:
        return inverted(authors[0])
    if len(authors) == 2:
        return f"{inverted(authors[0])}, and {natural(authors[1])}"
    return f"{inverted(authors[0])}, et al."


def format_authors_chicago(authors):
    """Bibliography form: up to 10 names listed in full, 11+ becomes first 7 plus et al.

    Only the first author is inverted, since only that name does the alphabetizing.
    """
    if not authors:
        return ""

    def inverted(author):
        return inverted_name(author)

    def natural(author):
        return natural_name(author)

    if len(authors) == 1:
        return inverted(authors[0])
    if len(authors) > 10:
        listed = [inverted(authors[0])] + [natural(a) for a in authors[1:7]]
        return ", ".join(listed) + ", et al."

    listed = [inverted(authors[0])] + [natural(a) for a in authors[1:]]
    if len(listed) == 2:
        return f"{listed[0]}, and {listed[1]}"
    return ", ".join(listed[:-1]) + f", and {listed[-1]}"


def natural_list(people, joiner="and"):
    """First Last, First Last, and First Last — names in reading order."""
    names = [natural_name(person) for person in people]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} {joiner} {names[1]}"
    return ", ".join(names[:-1]) + f", {joiner} {names[-1]}"


def initialed_list(people):
    """E. E. Editor, T. T. Translator — APA puts initials first in this position."""
    names = [
        f"{to_initials(person['given'])} {person['last']}".strip() for person in people
    ]
    if len(names) < 2:
        return "".join(names)
    if len(names) == 2:
        return " & ".join(names)
    return ", ".join(names[:-1]) + ", & " + names[-1]


def contributors_apa(editors, translators):
    """(E. Editor, Ed.; T. Translator, Trans.) — the bracket after an APA title."""
    parts = []
    if editors:
        parts.append(
            f"{initialed_list(editors)}, {'Eds.' if len(editors) > 1 else 'Ed.'}"
        )
    if translators:
        parts.append(f"{initialed_list(translators)}, Trans.")
    return f"({'; '.join(parts)})" if parts else ""


def contributors_mla(editors, translators):
    """edited by First Last, translated by First Last"""
    parts = []
    if editors:
        parts.append(f"edited by {natural_list(editors)}")
    if translators:
        parts.append(f"translated by {natural_list(translators)}")
    return ", ".join(parts)


def contributors_chicago(editors, translators, abbreviate=False):
    """Edited by First Last. Translated by First Last.  (abbreviated in footnotes)"""
    edit_word, trans_word = (
        ("ed.", "trans.") if abbreviate else ("Edited by", "Translated by")
    )
    parts = []
    if editors:
        parts.append(f"{edit_word} {natural_list(editors)}")
    if translators:
        parts.append(f"{trans_word} {natural_list(translators)}")
    return parts


# --- dates ----------------------------------------------------------------

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

# MLA abbreviates everything except May, June, and July.
MLA_MONTH_ABBREVIATIONS = [
    "Jan.",
    "Feb.",
    "Mar.",
    "Apr.",
    "May",
    "June",
    "July",
    "Aug.",
    "Sept.",
    "Oct.",
    "Nov.",
    "Dec.",
]


def split_iso_date(iso_date):
    """Accept a real YYYY, YYYY-MM, or YYYY-MM-DD date; reject invalid dates."""
    text = (iso_date or "").strip()
    if not text:
        return None, None, None
    if not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", text):
        raise ValueError("Use YYYY, YYYY-MM, or YYYY-MM-DD.")
    parts = [int(part) for part in text.split("-")]
    year, month, day = (
        parts[0],
        parts[1] if len(parts) > 1 else None,
        parts[2] if len(parts) > 2 else None,
    )
    date(year, month or 1, day or 1)
    if month == 0 or day == 0:
        raise ValueError("Date components cannot be zero.")
    return year, month, day


def date_apa(iso_date, fallback_year):
    year, month, day = split_iso_date(iso_date)
    if month:
        return f"({year}, {MONTH_NAMES[month - 1]}{f' {day}' if day else ''})"
    return f"({year or fallback_year})" if year or fallback_year else "(n.d.)"


def date_mla(iso_date, fallback_year):
    year, month, day = split_iso_date(iso_date)
    if month:
        return f"{f'{day} ' if day else ''}{MLA_MONTH_ABBREVIATIONS[month - 1]} {year}"
    return str(year or fallback_year or "")


def date_chicago(iso_date, fallback_year):
    year, month, day = split_iso_date(iso_date)
    if month:
        return f"{MONTH_NAMES[month - 1]} {f'{day}, ' if day else ''}{year}"
    return str(year or fallback_year or "n.d.")


# --- assembling -----------------------------------------------------------


def join_segments(segments, separator=" "):
    """Join the non-empty pieces. Dropping blanks is what stops ', ,' appearing
    where an optional field was left empty."""
    return separator.join(segment for segment in segments if segment)


def terminate(text):
    """End with exactly one period, unless it already ends in . ? or !"""
    text = text.strip()
    if not text:
        return ""
    if plain_text(text).endswith((".", "?", "!")):
        return text
    return text + "."


def format_doi_or_url(doi, url):
    """A DOI wins over a URL when both are given: it's the stabler link."""
    doi = (doi or "").strip()
    url = (url or "").strip()

    if doi:
        # Accept '10.1234/abc', 'doi:10.1234/abc', or the full URL.
        bare = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.I)
        return f"https://doi.org/{bare}"
    return url


# --- reference formatters ------------------------------------------------


def apa_book(data):
    editors_as_authors = not data["authors"] and bool(data["editors"])
    authors = format_authors_apa(
        data["editors"] if editors_as_authors else data["authors"]
    )
    if editors_as_authors:
        authors += f" ({'Eds.' if len(data['editors']) > 1 else 'Ed.'})"
    year = f"({data['year']})" if data["year"] else "(n.d.)"
    title = italic(sentence_title(data, "title"))
    edition = f"({normalize_edition(data['edition'])})" if data["edition"] else ""
    extra = contributors_apa(
        [] if editors_as_authors else data["editors"], data["translators"]
    )
    return join_segments(
        apa_lead(data, authors, year, join_segments([title, edition, extra]))
        + [terminate(data["publisher"]), format_doi_or_url(data["doi"], data["url"])]
    )


def apa_article(data):
    """Author, A. A. (Year). Title of article. *Journal*, *12*(3), 45-67. DOI"""
    authors = format_authors_apa(data["authors"])
    year = f"({data['year']})" if data["year"] else "(n.d.)"
    title = sentence_title(data, "title")
    journal = italic(headline_title(data, "container"))

    # The volume is italic, the issue in parentheses is not.
    volume = italic(data["volume"]) if data["volume"] else ""
    issue = f"({data['issue']})" if data["issue"] else ""
    pages = full_page_range(data["pages"])

    locator = join_segments(
        [journal, volume + issue if volume or issue else "", pages], ", "
    )
    link = format_doi_or_url(data["doi"], data["url"])

    if data.get("article_number") and not pages:
        locator = join_segments(
            [journal, volume + issue, "Article " + data["article_number"]], ", "
        )
    return join_segments(
        apa_lead(data, authors, year, title) + [terminate(locator), link]
    )


def apa_website(data):
    """Author, A. A. (2023, March 14). *Title of page*. Site Name. URL"""
    authors = format_authors_apa(data["authors"])
    date = date_apa(data["access_date"], data["year"])
    title = italic(sentence_title(data, "title"))
    site = headline_title(data, "container")
    link = format_doi_or_url(data["doi"], data["url"])

    if (
        len(data["authors"]) == 1
        and data["authors"][0].get("is_organization")
        and data["authors"][0]["last"].casefold() == data["container"].casefold()
    ):
        site = ""
    return join_segments(apa_lead(data, authors, date, title) + [terminate(site), link])


def mla_book(data):
    """Author. *Title in Title Case*. 2nd ed., Publisher, Year."""
    editor_led = not data["authors"] and bool(data["editors"])
    authors = format_authors_mla(data["editors"] if editor_led else data["authors"])
    if editor_led:
        authors += ", editors" if len(data["editors"]) > 1 else ", editor"
    title = italic(headline_title(data, "title"))
    edition = normalize_edition(data["edition"])
    extra = capitalize_first_letter(
        contributors_mla([] if editor_led else data["editors"], data["translators"])
    )

    facts = join_segments(
        [extra, edition, data["publisher"], str(data["year"] or "")], ", "
    )
    link = format_doi_or_url(data["doi"], data["url"])

    return join_segments(
        [
            terminate(authors),
            terminate(title),
            terminate(facts),
            terminate(link),
        ]
    )


def mla_article(data):
    """Author. "Title." *Journal*, vol. 12, no. 3, 2023, pp. 45-67. DOI"""
    authors = format_authors_mla(data["authors"])
    title = f'"{terminate(headline_title(data, "title"))}"'
    journal = italic(headline_title(data, "container"))

    volume = f"vol. {data['volume']}" if data["volume"] else ""
    issue = f"no. {data['issue']}" if data["issue"] else ""
    year = str(data["year"] or "")

    pages_value = mla_page_range(data["pages"])
    if pages_value:
        prefix = "pp." if EN_DASH in pages_value else "p."  # 'p.' for a single page
        pages = f"{prefix} {pages_value}"
    else:
        pages = ""

    facts = join_segments([journal, volume, issue, year, pages], ", ")
    link = format_doi_or_url(data["doi"], data["url"])

    return join_segments(
        [
            terminate(authors),
            title,
            terminate(facts),
            terminate(link),
        ]
    )


def mla_website(data):
    """Author. "Title of Page." *Site Name*, 14 Mar. 2023, URL."""
    authors = format_authors_mla(data["authors"])
    title = f'"{terminate(headline_title(data, "title"))}"'
    site = italic(headline_title(data, "container"))
    date = date_mla(data["access_date"], data["year"])
    link = format_doi_or_url(data["doi"], data["url"])

    facts = join_segments([site, date, link], ", ")

    return join_segments(
        [
            terminate(authors),
            title,
            terminate(facts),
        ]
    )


def chicago_book(data):
    """Author. *Title in Title Case*. 2nd ed. City: Publisher, Year."""
    editor_led = not data["authors"] and bool(data["editors"])
    authors = format_authors_chicago(data["editors"] if editor_led else data["authors"])
    if editor_led:
        authors += ", eds." if len(data["editors"]) > 1 else ", ed."
    title = italic(headline_title(data, "title"))
    edition = normalize_edition(data["edition"])

    # Chicago is the only one of the three that still wants the city.
    if data["city"] and data["publisher"]:
        imprint = f"{data['city']}: {data['publisher']}"
    else:
        imprint = data["publisher"] or data["city"]

    if data["year"]:
        imprint = f"{imprint}, {data['year']}" if imprint else str(data["year"])

    link = format_doi_or_url(data["doi"], data["url"])

    return join_segments(
        [
            terminate(authors),
            terminate(title),
            *[
                terminate(part)
                for part in contributors_chicago(
                    [] if editor_led else data["editors"], data["translators"]
                )
            ],
            terminate(edition),
            terminate(imprint),
            terminate(link),
        ]
    )


def chicago_article(data):
    """Author. "Title." *Journal* 12, no. 3 (2023): 45-67. DOI"""
    authors = format_authors_chicago(data["authors"])
    title = f'"{terminate(headline_title(data, "title"))}"'
    journal = italic(headline_title(data, "container"))

    volume = str(data["volume"] or "")
    issue = f"no. {data['issue']}" if data["issue"] else ""
    year = f"({data['year']})" if data["year"] else ""
    pages = condense_page_range(data["pages"])

    # No comma between the journal name and the volume number.
    head = join_segments([journal, join_segments([volume, issue], ", ")])
    tail = join_segments([head, year])
    locator = f"{tail}: {pages}" if pages else tail

    link = format_doi_or_url(data["doi"], data["url"])

    return join_segments(
        [
            terminate(authors),
            title,
            terminate(locator),
            terminate(link),
        ]
    )


def chicago_website(data):
    """Author. "Title of Page." Site Name. March 14, 2023. URL."""
    authors = format_authors_chicago(data["authors"])
    title = f'"{terminate(headline_title(data, "title"))}"'
    site = headline_title(data, "container")  # Chicago doesn't italicize site names
    date = date_chicago(data["access_date"], data["year"])
    link = format_doi_or_url(data["doi"], data["url"])

    return join_segments(
        [
            terminate(authors),
            title,
            terminate(site),
            terminate(date),
            terminate(link),
        ]
    )


def apa_chapter(data):
    """Author, A. (Year). Title of chapter. In E. Editor (Ed.), *Book* (pp. 45-67). Publisher."""
    authors = format_authors_apa(data["authors"])
    year = f"({data['year']})" if data["year"] else "(n.d.)"
    title = sentence_title(data, "title")
    book = italic(sentence_title(data, "container"))

    if data["editors"]:
        role = "Eds." if len(data["editors"]) > 1 else "Ed."
        editors = f"In {initialed_list(data['editors'])} ({role}),"
    else:
        editors = "In"

    pages = f"pp. {full_page_range(data['pages'])}" if data["pages"] else ""
    edition = normalize_edition(data["edition"]) if data["edition"] else ""
    details = join_segments([edition, pages], ", ")
    details = f"({details})" if details else ""
    link = format_doi_or_url(data["doi"], data["url"])
    return join_segments(
        apa_lead(data, authors, year, title)
        + [
            editors,
            terminate(join_segments([book, details])),
            terminate(data["publisher"]),
            link,
        ]
    )


def mla_chapter(data):
    """Author. "Chapter." *Book*, edited by First Last, Publisher, Year, pp. 45-67."""
    authors = format_authors_mla(data["authors"])
    title = f'"{terminate(headline_title(data, "title"))}"'
    book = italic(headline_title(data, "container"))
    extra = contributors_mla(data["editors"], data["translators"])

    pages_value = mla_page_range(data["pages"])
    pages = (
        f"{'pp.' if EN_DASH in pages_value else 'p.'} {pages_value}"
        if pages_value
        else ""
    )

    facts = join_segments(
        [
            book,
            extra,
            normalize_edition(data["edition"]),
            data["publisher"],
            str(data["year"] or ""),
            pages,
        ],
        ", ",
    )
    link = format_doi_or_url(data["doi"], data["url"])

    return join_segments([terminate(authors), title, terminate(facts), terminate(link)])


def chicago_chapter(data):
    """Author. "Chapter." In *Book*, edited by First Last, 45-67. City: Publisher, Year."""
    authors = format_authors_chicago(data["authors"])
    title = f'"{terminate(headline_title(data, "title"))}"'
    book = italic(headline_title(data, "container"))
    extra = contributors_chicago(data["editors"], data["translators"])
    extra = [part[0].lower() + part[1:] for part in extra]
    pages = condense_page_range(data["pages"])

    # In *Book*, edited by ..., 45-67.
    inner = join_segments(
        [f"In {book}"] + extra + [normalize_edition(data["edition"]), pages], ", "
    )

    if data["city"] and data["publisher"]:
        imprint = f"{data['city']}: {data['publisher']}"
    else:
        imprint = data["publisher"] or data["city"]
    if data["year"]:
        imprint = f"{imprint}, {data['year']}" if imprint else str(data["year"])

    link = format_doi_or_url(data["doi"], data["url"])

    return join_segments(
        [
            terminate(authors),
            title,
            terminate(inner),
            terminate(imprint),
            terminate(link),
        ]
    )


FORMATTERS = {
    "book": {"APA": apa_book, "MLA": mla_book, "Chicago": chicago_book},
    "chapter": {"APA": apa_chapter, "MLA": mla_chapter, "Chicago": chicago_chapter},
    "article": {"APA": apa_article, "MLA": mla_article, "Chicago": chicago_article},
    "website": {"APA": apa_website, "MLA": mla_website, "Chicago": chicago_website},
}


# --- in-text citations and footnotes -------------------------------------


def short_title(title, words=4, preserve=False):
    """First few words of a title, for a shortened Chicago note.

    Long titles are cut at the first particle inside the window, so
    "University Physics with Modern Physics" shortens to "University Physics"
    rather than the ragged "University Physics with Modern".

    >>> short_title("University Physics with Modern Physics")
    'University Physics'
    >>> short_title("A Mathematical Theory of Communication")
    'Mathematical Theory of Communication'
    """
    tokens = (title if preserve else to_title_case(title)).split()
    if tokens and tokens[0].lower() in ("a", "an", "the"):
        tokens = tokens[1:]
    if len(tokens) <= words:
        return " ".join(tokens)

    kept = []
    for token in tokens[:words]:
        if kept and token.lower().strip(".,;:") in LOWERCASE_WORDS:
            break
        kept.append(token)
    return " ".join(kept)


def signal_phrase(authors, joiner="and", limit=3):
    """Young, Young and Freedman, or Young et al. — the surnames an in-text cite uses."""
    names = [author["last"] for author in authors]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} {joiner} {names[1]}"
    return (
        f"{names[0]} et al."
        if len(names) >= limit
        else ", ".join(names[:-1]) + f", {joiner} {names[-1]}"
    )


def in_text_apa(data):
    """APA cites author and year, and a page only for a direct quote."""
    year = data["year"] or "n.d."
    locator = full_page_range(data["cited_page"])
    page = (
        f", {'pp.' if EN_DASH in locator or ',' in locator else 'p.'} {locator}"
        if locator
        else ""
    )
    anchor = signal_phrase(
        data["authors"] or (data["editors"] if data["source_type"] == "book" else []),
        "&",
    )
    narrative_anchor = signal_phrase(
        data["authors"] or (data["editors"] if data["source_type"] == "book" else []),
        "and",
    )

    if not anchor:
        stub = short_title(
            data["title"], preserve=data.get("capitalization") == "preserve"
        )
        anchor = narrative_anchor = (
            italic(stub) if data["source_type"] in ("book", "website") else f'"{stub}"'
        )

    return [
        {"label": "Parenthetical", "text": f"({anchor}, {year}{page})"},
        {"label": "Narrative", "text": f"{narrative_anchor} ({year}{page})"},
    ]


def in_text_mla(data):
    """MLA cites author and page — no year, and no comma between them."""
    page = mla_page_range(data["cited_page"]) or ""
    anchor = signal_phrase(
        data["authors"] or (data["editors"] if data["source_type"] == "book" else []),
        "and",
    )
    if not anchor:
        stub = short_title(
            data["title"], preserve=data.get("capitalization") == "preserve"
        )
        anchor = italic(stub) if data["source_type"] == "book" else f'"{stub}"'

    return [
        {"label": "Parenthetical", "text": f"({join_segments([anchor, page])})"},
        {"label": "Narrative", "text": f"{anchor} ({page})" if page else anchor},
    ]


def chicago_note(data, short=False):
    """A footnote, which is a different shape from the bibliography entry: names
    are not inverted, commas replace periods, and the publication details sit in
    parentheses. Each branch is written out in full because the punctuation
    differs per source type in ways a shared join can't express."""
    kind = data["source_type"]
    page = condense_page_range(data["cited_page"]) or ""
    tail = f", {page}." if page else "."

    if short:
        names = signal_phrase(
            data["authors"]
            or (data["editors"] if data["source_type"] == "book" else []),
            "and",
            limit=4,
        )
        stub = short_title(
            data["title"], preserve=data.get("capitalization") == "preserve"
        )
        if kind == "book":
            title = italic(stub)
        else:
            # American style tucks the comma inside a closing quotation mark.
            title, tail = (f'"{stub},"', f" {page}.") if page else (f'"{stub}."', "")
        return join_segments([f"{names}," if names else "", title]) + tail

    note_authors = data["authors"] or (data["editors"] if kind == "book" else [])
    names = (
        natural_list(note_authors)
        if len(note_authors) < 4
        else natural_name(note_authors[0]) + " et al."
    )
    if not data["authors"] and note_authors:
        names += ", eds." if len(note_authors) > 1 else ", ed."
    lead = f"{names}, " if names else ""
    link = format_doi_or_url(data["doi"], data["url"])

    def finish(text):
        return text.rstrip(".") + ", " + link + "." if link else text

    if data["city"] and data["publisher"]:
        imprint = f"{data['city']}: {data['publisher']}"
    else:
        imprint = data["publisher"] or data["city"]
    imprint = join_segments([imprint, str(data["year"] or "")], ", ")
    parenthetical = f" ({imprint})" if imprint else ""

    if kind == "book":
        body = italic(headline_title(data, "title"))
        edition = normalize_edition(data["edition"])
        if edition:
            body = f"{body}, {edition}"
        extra = contributors_chicago(
            data["editors"] if data["authors"] else [],
            data["translators"],
            abbreviate=True,
        )
        if extra:
            body += ", " + ", ".join(extra)
        return finish(f"{lead}{body}{parenthetical}{tail}")

    if kind == "chapter":
        body = (
            f'"{headline_title(data, "title")}," '
            f"in {italic(headline_title(data, 'container'))}"
        )
        editors = contributors_chicago(
            data["editors"], data["translators"], abbreviate=True
        )
        if editors:
            body = f"{body}, {', '.join(editors)}"
        if data["edition"]:
            body += ", " + normalize_edition(data["edition"])
        return finish(f"{lead}{body}{parenthetical}{tail}")

    if kind == "article":
        volume = join_segments(
            [
                str(data["volume"] or ""),
                f"no. {data['issue']}" if data["issue"] else "",
            ],
            ", ",
        )
        locator = join_segments([italic(headline_title(data, "container")), volume])
        if data["year"]:
            locator = f"{locator} ({data['year']})"
        closing = f": {page}." if page else "."
        return finish(f'{lead}"{headline_title(data, "title")}," {locator}{closing}')

    when = date_chicago(data["access_date"], data["year"])
    return (
        join_segments(
            [
                f'{lead}"{headline_title(data, "title")},"',
                f"{headline_title(data, 'container')},",
                f"{when},",
                data["url"],
            ]
        )
        + "."
    )


def in_text_chicago(data):
    return [
        {"label": "Full note", "text": chicago_note(data)},
        {"label": "Shortened note", "text": chicago_note(data, short=True)},
    ]


IN_TEXT = {"APA": in_text_apa, "MLA": in_text_mla, "Chicago": in_text_chicago}


FIELD_NAMES = [
    "source_type",
    "authors",
    "editors",
    "translators",
    "title",
    "container",
    "publisher",
    "city",
    "year",
    "volume",
    "issue",
    "pages",
    "edition",
    "doi",
    "isbn",
    "url",
    "access_date",
    "published_date",
    "cited_page",
    "author_mode",
    "capitalization",
    "article_number",
]

# Fields holding people rather than plain text.
PEOPLE_FIELDS = ["authors", "editors", "translators"]

# Recommended fields per source type. Missing ones warn rather than block.
REQUIRED_FIELDS = {
    "book": [
        ("title", "title"),
        ("authors", "author"),
        ("year", "year"),
        ("publisher", "publisher"),
    ],
    "article": [
        ("title", "article title"),
        ("authors", "author"),
        ("container", "journal name"),
        ("year", "year"),
        ("pages", "page range"),
    ],
    "website": [("title", "page title"), ("container", "site name"), ("url", "URL")],
    "chapter": [
        ("title", "chapter title"),
        ("authors", "author"),
        ("container", "book title"),
        ("year", "year"),
        ("publisher", "publisher"),
        ("pages", "page range"),
    ],
}


def clean_input(raw, overrides=None, mark=False):
    """Give every field a default in one place, so a formatter can't hit a KeyError."""
    data = {name: str(raw.get(name, "") or "").strip() for name in FIELD_NAMES}
    for field in PEOPLE_FIELDS:
        data[field] = parse_author_list(raw.get(field, ""))
    if data.get("author_mode") == "organization":
        data["authors"] = [
            {"last": line.strip(), "given": "", "is_organization": True}
            for line in raw.get("authors", "").splitlines()
            if line.strip()
        ]
    elif data.get("author_mode") == "unknown":
        data["authors"] = []
    data["access_date"] = data["published_date"] or data["access_date"]
    if data["source_type"] == "website" and data["access_date"]:
        year, _, _ = split_iso_date(data["access_date"])
        data["year"] = str(year)
    data["overrides"] = dict(overrides or {}) | raw.get("case_overrides", {})
    data["mark"] = mark
    if data["source_type"] not in FORMATTERS:
        data["source_type"] = "book"
    return data


def collect_warnings(data):
    """Plain-language names of the recommended fields still blank."""
    return [
        label
        for field, label in REQUIRED_FIELDS[data["source_type"]]
        if field in collect_missing_fields(data)
    ]


def collect_missing_fields(data):
    """The same gaps, as field names, so the page can flag the inputs themselves."""
    missing = [
        field
        for field, label in REQUIRED_FIELDS[data["source_type"]]
        if not data[field]
    ]
    if data.get("author_mode") == "unknown" or (
        data["source_type"] == "book" and data["editors"]
    ):
        missing = [field for field in missing if field != "authors"]
    if data.get("article_number"):
        missing = [field for field in missing if field != "pages"]
    return missing


def format_all(raw, overrides=None, mark=False):
    """Format one source for every supported style.

    overrides maps a lowercase word to 'proper' or 'common'. mark=True adds the
    {g:...} / {p:...} wrappers described in to_sentence_case.

    Returns {'APA': ..., 'MLA': ..., 'Chicago': ..., 'warnings': [...]}.
    """
    data = clean_input(raw, overrides, mark)
    formatters = FORMATTERS[data["source_type"]]

    citations = {style: function(data) for style, function in formatters.items()}
    citations["intext"] = {style: builder(data) for style, builder in IN_TEXT.items()}
    citations["warnings"] = collect_warnings(data)
    citations["missing"] = collect_missing_fields(data)
    return citations


if __name__ == "__main__":
    import doctest

    results = doctest.testmod()
    print(f"{results.attempted - results.failed}/{results.attempted} doctests passed.")
    raise SystemExit(bool(results.failed))
