"""Flask routes for the QuickCite web app."""

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from . import library, lookup
from .output import bibliography_html, format_source
from .validation import ValidationError, normalize_fields

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 128 * 1024
app.config['JSON_SORT_KEYS'] = False


@app.after_request
def add_response_headers(response):
    """Set conservative browser defaults without getting in the way of copying."""
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'no-referrer')
    response.headers.setdefault(
        'Permissions-Policy', 'camera=(), geolocation=(), microphone=()'
    )
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; base-uri 'none'; connect-src 'self'; "
        "frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; "
        "script-src 'self'; style-src 'self' 'unsafe-inline'",
    )
    if request.path.startswith('/api/'):
        response.headers.setdefault('Cache-Control', 'no-store')
    return response


def json_object():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError('Send a JSON object with the request details.')
    return payload


def selected_style():
    style = request.args.get('style', 'APA')
    if style not in library.HEADINGS:
        raise ValidationError('Choose APA, MLA, or Chicago.')
    return style


def source_id(payload):
    value = payload.get('id')
    if not isinstance(value, str) or not value or len(value) > 100:
        raise ValidationError('Specify a saved source ID.')
    return value


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/api/health')
def api_health():
    """A tiny endpoint for local checks and hosting health probes."""
    return jsonify({'status': 'ok', 'service': 'quickcite'})


@app.post('/api/format')
def api_format():
    return jsonify(format_source(normalize_fields(json_object())))


@app.post('/api/lookup')
def api_lookup():
    identifier = json_object().get('identifier', '')
    if not isinstance(identifier, str) or len(identifier) > 1000:
        raise ValidationError('Enter a DOI or ISBN as text, under 1,000 characters.')
    fields = lookup.lookup(identifier)
    return jsonify({'fields': normalize_fields(fields)})


@app.route('/api/library', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_library():
    style = selected_style()
    message, extra = '', {}
    if request.method in ('POST', 'PUT'):
        payload = json_object()
        entry_id = source_id(payload) if request.method == 'PUT' else None
        extra['saved_id'] = library.upsert(payload.get('fields'), entry_id)
        message = 'Changes saved.' if entry_id else 'Source saved.'
    elif request.method == 'DELETE':
        extra['removed_ids'] = library.remove(source_id(json_object()))
        message = 'Source removed.' if len(extra['removed_ids']) == 1 else 'List emptied.'
    return jsonify({**library.presentation(style), 'message': message, **extra})


@app.post('/api/library/restore')
def api_restore():
    ids = json_object().get('ids')
    if not isinstance(ids, list) or len(ids) > 10000 or not all(isinstance(item, str) and 0 < len(item) <= 100 for item in ids):
        raise ValidationError('Supply the source IDs to restore.')
    library.restore(ids)
    return jsonify({**library.presentation(selected_style()), 'message': 'Removed sources restored.'})


@app.get('/api/library/export')
def api_export():
    style = selected_style()
    payload = library.presentation(style)
    body = bibliography_html(payload['entries'], payload['heading'])
    response = Response(body, mimetype='text/html')
    filename = f'{style.lower()}-bibliography.html'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@app.errorhandler(ValidationError)
def validation_error(error):
    return jsonify({'error': str(error), 'fields': error.fields}), 400


@app.errorhandler(library.DuplicateSource)
def duplicate_error(error):
    return jsonify({'error': str(error), 'duplicate_id': error.entry_id}), 409


@app.errorhandler(library.SourceNotFound)
def missing_source(error):
    return jsonify({'error': str(error)}), 404


@app.errorhandler(library.StorageError)
def storage_error(error):
    app.logger.warning('Storage error: %s', error)
    return jsonify({'error': str(error)}), 503


@app.errorhandler(lookup.LookupError_)
def lookup_error(error):
    return jsonify({'error': str(error)}), error.status_code


@app.errorhandler(Exception)
def unexpected_error(error):
    if isinstance(error, HTTPException):
        return jsonify({'error': error.description}), error.code
    app.logger.exception('Unexpected request failure')
    return jsonify({'error': 'Something went wrong. Your displayed result may be out of date. Please try again.'}), 500
