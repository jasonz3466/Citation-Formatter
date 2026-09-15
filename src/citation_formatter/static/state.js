/* These helpers do not touch the page, which makes them easy to test in Node. */
(function (root) {
  'use strict';

  class LatestRequest {
    constructor() {
      this.version = 0;
      this.controller = null;
    }

    invalidate() {
      this.version += 1;
      if (this.controller) this.controller.abort();
      this.controller = null;
    }

    begin() {
      this.invalidate();
      const version = this.version;
      this.controller = new AbortController();

      return {
        signal: this.controller.signal,
        isCurrent: () => this.version === version,
      };
    }
  }

  const contentFields = [
    'authors',
    'editors',
    'translators',
    'title',
    'container',
    'publisher',
    'city',
    'year',
    'published_date',
    'volume',
    'issue',
    'pages',
    'edition',
    'doi',
    'isbn',
    'url',
    'cited_page',
    'article_number',
  ];

  function isFormEmpty(fields) {
    return !contentFields.some(
      key => typeof fields[key] === 'string' && fields[key].trim(),
    );
  }

  async function copyPayload(clipboard, ClipboardItemType, value, plainOnly = false) {
    if (!value || !value.text) throw new Error('Nothing to copy yet.');

    if (!plainOnly && clipboard && clipboard.write && ClipboardItemType) {
      try {
        const item = new ClipboardItemType({
          'text/html': new Blob([value.html], {type: 'text/html'}),
          'text/plain': new Blob([value.text], {type: 'text/plain'}),
        });
        await clipboard.write([item]);
        return 'formatted';
      } catch (error) {
        // Safari and permission-restricted browsers often need the plain-text path.
      }
    }

    if (!clipboard || !clipboard.writeText) {
      throw new Error('Clipboard unavailable.');
    }
    await clipboard.writeText(value.text);
    return 'plain';
  }

  const api = {LatestRequest, isFormEmpty, copyPayload};
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    root.CitationState = api;
  }
})(typeof window === 'undefined' ? {} : window);
