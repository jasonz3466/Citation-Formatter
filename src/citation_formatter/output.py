"""Turn internal citation markup into safe HTML and faithful plain text.

User text is escaped BEFORE formatting. Only the formatter can introduce emphasis
or word annotations. The browser receives finished HTML and plain text together.
"""
from html import escape


def escape_source(text):
    for char in ('\\', '*', '{', '}'):
        text = text.replace(char, '\\' + char)
    return text


def runs(markup):
    """Parse escaped text, *emphasis*, and {p:word}/{g:word} annotations."""
    result, buffer = [], []
    italic = False
    index = 0

    def flush(word=False, guessed=False):
        if buffer:
            result.append({'text': ''.join(buffer), 'italic': italic,
                           'word': word, 'guessed': guessed})
            buffer.clear()

    while index < len(markup):
        char = markup[index]
        if char == '\\' and index + 1 < len(markup):
            buffer.append(markup[index + 1])
            index += 2
        elif char == '*':
            flush()
            italic = not italic
            index += 1
        elif markup[index:index + 3] in ('{p:', '{g:'):
            flush()
            guessed = markup[index + 1] == 'g'
            index += 3
            while index < len(markup) and markup[index] != '}':
                if markup[index] == '\\' and index + 1 < len(markup):
                    index += 1
                buffer.append(markup[index])
                index += 1
            flush(word=True, guessed=guessed)
            if index < len(markup):
                index += 1
        else:
            buffer.append(char)
            index += 1
    flush()
    return result


def plain_text(markup):
    return ''.join(run['text'] for run in runs(markup))


def as_html(markup, interactive=False):
    parts = []
    for run in runs(markup):
        value = escape(run['text'])
        if interactive and run['word']:
            first_letter = next((c for c in run['text'] if c.isalpha()), '')
            action = 'Lowercase' if first_letter.isupper() else 'Capitalize'
            classes = 'word word--guess' if run['guessed'] else 'word'
            label = escape(f"{action} {run['text']} for this source", quote=True)
            value = f'<button type="button" class="{classes}" aria-label="{label}">{value}</button>'
        if run['italic']:
            value = f'<em>{value}</em>'
        parts.append(value)
    return ''.join(parts)


def format_source(fields):
    """Public presentation contract: text and HTML always share literal content."""
    from .citations import clean_input, format_all, natural_list
    protected = {key: escape_source(value) if isinstance(value, str) else value
                 for key, value in fields.items()}
    result = format_all(protected, mark=True)
    styles = {}
    for style in ('APA', 'MLA', 'Chicago'):
        markup = result[style]
        styles[style] = {
            'text': plain_text(markup), 'html': as_html(markup),
            'interactive_html': as_html(markup, interactive=style == 'APA'),
            'intext': [{'label': item['label'], 'text': plain_text(item['text']),
                        'html': as_html(item['text'])} for item in result['intext'][style]],
        }
    data = clean_input(fields)
    return {'styles': styles, 'warnings': result['warnings'], 'missing': result['missing'],
            'parsed_authors': natural_list(data['authors']),
            'corrections': len(fields.get('case_overrides', {}))}


def bibliography_html(entries, heading):
    """A downloadable, printable page with the selected bibliography only."""
    body = ''.join('<p class="reference">' + item['html'] + '</p>' for item in entries)
    title = escape(heading)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title><style>'
        'body{font:12pt/2 Georgia,serif;color:#000;background:#fff;max-width:7in;'
        'margin:1in auto;padding:0 .4in}'
        'h1{text-align:center;font-size:12pt}.reference{padding-left:.5in;'
        'text-indent:-.5in;margin:0;overflow-wrap:anywhere}'
        '@page{margin:1in}@media print{body{margin:0;padding:0;max-width:none}}'
        f'</style></head><body><h1>{title}</h1>{body}</body></html>'
    )
