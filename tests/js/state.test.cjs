const {test} = require('node:test');
const assert = require('node:assert/strict');
const {LatestRequest, isFormEmpty, copyPayload} = require('../../src/citation_formatter/static/state.js');

test('only the latest request is current', () => {
  const requests = new LatestRequest();
  const old = requests.begin(); const fresh = requests.begin();
  assert.equal(old.isCurrent(), false);
  assert.equal(old.signal.aborted, true);
  assert.equal(fresh.isCurrent(), true);
});
test('clear invalidates in-flight work before the debounce', () => {
  const requests = new LatestRequest(); const old = requests.begin(); requests.invalidate();
  assert.equal(old.isCurrent(), false); assert.equal(old.signal.aborted, true);
});
test('configuration and corrections alone do not make an empty source nonempty', () => {
  assert.equal(isFormEmpty({source_type: 'book', capitalization: 'auto', author_mode: 'people', case_overrides: {may:'proper'}}), true);
  assert.equal(isFormEmpty({title: 'A source'}), false);
});
test('rich copy carries both HTML and faithful plain text', async () => {
  let items;
  class Item { constructor(data) { this.data = data; } }
  const clipboard = {write: async value => {items = value;}};
  const mode = await copyPayload(clipboard, Item, {text:'A* Search', html:'<em>A* Search</em>'});
  assert.equal(mode, 'formatted');
  assert.equal(await items[0].data['text/plain'].text(), 'A* Search');
  assert.equal(await items[0].data['text/html'].text(), '<em>A* Search</em>');
});
test('failed rich copy explicitly falls back to plain text', async () => {
  let copied;
  class Item { constructor(data) { this.data = data; } }
  const mode = await copyPayload({write: async () => {throw new Error('unsupported');}, writeText: async text => {copied = text;}}, Item, {text:'A* Search',html:'<em>A* Search</em>'});
  assert.equal(mode, 'plain'); assert.equal(copied, 'A* Search');
});
test('plain-copy preference avoids the rich clipboard API', async () => {
  let copied;
  const mode = await copyPayload({write: async () => assert.fail(), writeText: async text => {copied = text;}}, class {}, {text:'source',html:'<em>source</em>'}, true);
  assert.equal(mode, 'plain'); assert.equal(copied, 'source');
});
