"""Validate external input before any formatter or persistence operation."""
import re
from datetime import date
from urllib.parse import urlsplit

SOURCE_TYPES = {'book', 'article', 'chapter', 'website'}
TEXT_FIELDS = {'source_type', 'authors', 'author_mode', 'editors', 'translators',
               'title', 'container', 'publisher', 'city', 'year', 'volume', 'issue',
               'pages', 'edition', 'doi', 'isbn', 'url', 'published_date',
               'access_date', 'cited_page', 'capitalization', 'article_number'}


class ValidationError(ValueError):
    def __init__(self, message, fields=None):
        super().__init__(message)
        self.fields = fields or {}


def validate_date(value):
    """Accept an honest year, year/month, or complete publication date."""
    if not re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?', value):
        raise ValueError('Use YYYY, YYYY-MM, or YYYY-MM-DD.')
    parts = [int(part) for part in value.split('-')]
    date(parts[0], parts[1] if len(parts) > 1 else 1,
         parts[2] if len(parts) > 2 else 1)
    return value


def normalize_fields(raw, *, saving=False):
    if not isinstance(raw, dict):
        raise ValidationError('Send a JSON object containing source details.')
    result, errors = {}, {}
    for key in TEXT_FIELDS:
        value = raw.get(key, '')
        if value is None:
            value = ''
        if not isinstance(value, str):
            errors[key] = 'Use text for this field.'
            continue
        value = value.strip()
        if len(value) > 6000:
            errors[key] = 'Keep this field under 6,000 characters.'
        if any(ord(c) < 32 and c not in '\n\r\t' for c in value):
            errors[key] = 'Remove control characters from this field.'
        result[key] = value
    if errors:
        raise ValidationError('Please correct the highlighted fields.', errors)
    result['source_type'] = result['source_type'] or 'book'
    result['author_mode'] = result['author_mode'] or 'people'
    result['capitalization'] = result['capitalization'] or 'auto'
    if result['source_type'] not in SOURCE_TYPES:
        errors['source_type'] = 'Choose a supported source type.'
    if result['author_mode'] not in {'people', 'organization', 'unknown'}:
        errors['author_mode'] = 'Choose people, organization, or unknown.'
    if result['capitalization'] not in {'auto', 'preserve'}:
        errors['capitalization'] = 'Choose automatic or preserve capitalization.'
    if result['author_mode'] == 'unknown':
        result['authors'] = ''
    result['published_date'] = result['published_date'] or result.pop('access_date', '')
    result.pop('access_date', None)
    if result['published_date']:
        try:
            validate_date(result['published_date'])
        except ValueError:
            errors['published_date'] = 'Enter a real date: YYYY, YYYY-MM, or YYYY-MM-DD.'
        else:
            if result['source_type'] == 'website':
                result['year'] = result['published_date'][:4]
    if result['year'] and (not re.fullmatch(r'\d{4}', result['year']) or int(result['year']) == 0):
        errors['year'] = 'Enter a four-digit year, or leave it blank if unknown.'
    if result['url']:
        try:
            url = urlsplit(result['url'])
            if url.scheme not in {'http', 'https'} or not url.netloc or any(c.isspace() for c in result['url']):
                raise ValueError
        except ValueError:
            errors['url'] = 'Use a complete http:// or https:// address.'
    if result['doi']:
        result['doi'] = re.sub(r'^(https?://(?:dx\.)?doi\.org/|doi:\s*)', '', result['doi'], flags=re.I)
        if not re.fullmatch(r'10\.\d{4,9}/\S+', result['doi']):
            errors['doi'] = 'Use a DOI such as 10.1002/example, or leave it blank.'
    if result['isbn']:
        from .lookup import clean_identifier, looks_like_isbn
        isbn = clean_identifier(result['isbn'])
        if not looks_like_isbn(isbn):
            errors['isbn'] = 'Enter a valid ISBN with its correct check digit, or leave it blank.'
        else:
            result['isbn'] = re.sub(r'[^0-9Xx]', '', isbn).upper()
    overrides = raw.get('case_overrides', {})
    if not isinstance(overrides, dict) or len(overrides) > 200 or any(
        not isinstance(k, str) or len(k) > 100 or not k or v not in ('proper', 'common')
        for k, v in overrides.items()
    ):
        errors['case_overrides'] = 'The capitalization corrections are invalid.'
    else:
        result['case_overrides'] = dict(overrides)
    if saving and not result['title']:
        errors['title'] = 'Add a title before saving this source.'
    if errors:
        raise ValidationError('Please correct the highlighted fields.', errors)
    return result
