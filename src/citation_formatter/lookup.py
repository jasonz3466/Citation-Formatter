"""Fetch source details from a DOI or ISBN so the form can fill itself.

Crossref covers journal articles and many book chapters; Open Library covers
books. Both are free and need no API key. Neither is reliable enough to trust
blindly, so everything here returns whatever it found and leaves the rest blank
for the user to complete.

urllib keeps the request code small. certifi supplies a dependable certificate
bundle on Python installations whose system certificate path is incomplete.
"""

import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

import certifi

CROSSREF = "https://api.crossref.org/works/"
OPENLIBRARY = "https://openlibrary.org/api/books"

# Optionally include your own contact information. Never ship a fake email.
USER_AGENT = os.environ.get("CITATION_USER_AGENT", "QuickCite/0.4.1 (personal citation tool)")

TIMEOUT_SECONDS = 8
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class LookupError_(Exception):
    """Raised when an identifier can't be resolved. Carries a message for the user."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT_SECONDS, context=SSL_CONTEXT
        ) as response:
            content = response.read(2_000_001)
            if len(content) > 2_000_000:
                raise LookupError_("The lookup response was unexpectedly large.")
            result = json.loads(content.decode("utf-8"))
            if not isinstance(result, dict):
                raise LookupError_("The lookup service returned an unexpected record.")
            return result
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise LookupError_("No record found for that identifier.", 404) from error
        if error.code == 429:
            raise LookupError_("The lookup service is busy. Wait a moment and try again.", 503) from error
        raise LookupError_(f"The lookup service returned an error ({error.code}).", 502) from error
    except urllib.error.URLError as error:
        raise LookupError_("Couldn't reach the lookup service. Check your connection.", 503) from error
    except (TimeoutError, OSError) as error:
        raise LookupError_("The lookup service timed out or disconnected. Try again.", 504) from error
    except ValueError as error:
        raise LookupError_("The lookup service sent something unreadable.", 502) from error


def clean_identifier(raw):
    """Strip the wrappers people paste along with an identifier."""
    text = (raw or "").strip()
    text = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I)
    text = re.sub(r"^ISBN(?:-1[03])?:?\s*", "", text, flags=re.I)
    return text.strip()


def looks_like_doi(text):
    return bool(re.fullmatch(r"10\.\d{4,9}/\S+", text))


def looks_like_isbn(text):
    digits = re.sub(r"[\s-]", "", text).upper()
    if re.fullmatch(r"\d{9}[\dX]", digits):
        return sum((10 - i) * (10 if char == "X" else int(char)) for i, char in enumerate(digits)) % 11 == 0
    if re.fullmatch(r"97[89]\d{10}", digits):
        return sum(int(char) * (1 if i % 2 == 0 else 3) for i, char in enumerate(digits)) % 10 == 0
    return False


def names_to_lines(people, given_key, family_key):
    """Turn a list of name records into the textarea format: one 'Last, First' per line."""
    lines = []
    for person in people or []:
        if not isinstance(person, dict):
            continue
        family = (person.get(family_key) or "").strip()
        given = (person.get(given_key) or "").strip()
        if family and given:
            lines.append(f"{family}, {given}")
        elif family or given:
            lines.append(family or given)
        elif person.get("name"):
            lines.append("[" + str(person["name"]).strip() + "]")
    return "\n".join(lines)


def first(value):
    """Crossref wraps most fields in a list even when there's only ever one."""
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def from_crossref(doi):
    """Map a Crossref record onto our field names."""
    payload = fetch_json(CROSSREF + urllib.parse.quote(doi))
    work = payload.get("message") or {}

    # Crossref dates arrive as nested lists: {"date-parts": [[2026, 3, 14]]}.
    parts = (work.get("issued") or {}).get("date-parts") or [[]]
    year = str(parts[0][0]) if parts and parts[0] else ""

    kinds = {"journal-article": "article", "book-chapter": "chapter", "book-part": "chapter",
             "book": "book", "monograph": "book", "edited-book": "book", "reference-book": "book"}
    if work.get("type") not in kinds:
        raise LookupError_("This DOI describes a source type the formatter does not support yet. Enter its details manually if an available type fits.")
    kind = kinds[work["type"]]
    title = first(work.get("title"))
    subtitle = first(work.get("subtitle"))
    if subtitle and subtitle.casefold() not in title.casefold():
        title = title.rstrip(": ") + ": " + subtitle

    return {
        "source_type": kind,
        "authors": names_to_lines(work.get("author"), "given", "family"),
        "editors": names_to_lines(work.get("editor"), "given", "family"),
        "title": title,
        "container": first(work.get("container-title")),
        "publisher": work.get("publisher", ""),
        "year": year,
        "volume": work.get("volume", ""),
        "issue": work.get("issue", ""),
        "pages": work.get("page", ""),
        "article_number": work.get("article-number", ""),
        "doi": work.get("DOI", doi),
        "url": "",
    }


def from_openlibrary(isbn):
    """Map an Open Library record onto our field names."""
    digits = re.sub(r"[^0-9Xx]", "", isbn).upper()
    query = urllib.parse.urlencode({"bibkeys": f"ISBN:{digits}",
                                    "format": "json", "jscmd": "data"})
    payload = fetch_json(f"{OPENLIBRARY}?{query}")

    book = payload.get(f"ISBN:{digits}")
    if not book:
        raise LookupError_("No book found with that ISBN.")

    publishers = book.get("publishers") or []
    places = book.get("publish_places") or []

    # Open Library gives one "name" string per person, not split into parts.
    authors = "\n".join(person.get("name", "") for person in book.get("authors") or [])

    title = book.get("title", "")
    subtitle = book.get("subtitle", "")
    if subtitle and subtitle.casefold() not in title.casefold():
        title = title.rstrip(": ") + ": " + subtitle
    year_match = re.search(r"\b(\d{4})\b", book.get("publish_date", ""))
    return {
        "source_type": "book",
        "authors": authors,
        "title": title,
        "edition": book.get("edition_name", ""),
        "isbn": digits,
        "publisher": publishers[0].get("name", "") if publishers else "",
        "city": places[0].get("name", "") if places else "",
        "year": year_match.group(1) if year_match else "",
        "url": "",  # A catalog record URL is not the consulted book itself.
    }


def lookup(raw):
    """Resolve a DOI or ISBN into form fields. Picks the service from the shape."""
    text = clean_identifier(raw)
    if not text:
        raise LookupError_("Enter a DOI or an ISBN first.")
    if looks_like_doi(text):
        return from_crossref(text)
    if looks_like_isbn(text):
        return from_openlibrary(text)
    raise LookupError_("Enter a DOI (10.xxxx/yyyy) or a valid ISBN with the correct check digit.")
