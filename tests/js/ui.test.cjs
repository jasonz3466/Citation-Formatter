/* DOM unit tests, with a simulated API. These do not render a real browser. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const root = path.join(__dirname, '../..');
const packageRoot = path.join(root, 'src/citation_formatter');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const base = {source_type:'book', title:'Initial book', authors:'Doe, Jane', year:'2024', publisher:'Press'};
const html = fs.readFileSync(path.join(packageRoot, 'templates/index.html'), 'utf8');
const styleNames = ['APA', 'MLA', 'Chicago'];
const encode = text => String(text).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function citation(fields) {
  return {styles: Object.fromEntries(styleNames.map(style => [style, {
    text:fields.title, html:'<em>' + encode(fields.title) + '</em>', interactive_html:'<em>' + encode(fields.title) + '</em>',
    intext:[{label:'Parenthetical',text:'(Doe, 2024)',html:'(Doe, 2024)'}],
  }])), warnings:[],missing:[],parsed_authors:fields.authors || '',corrections:0};
}
async function setup(t, {initial = base, intercept} = {}) {
  const dom = new JSDOM(html, {url:'http://localhost/', runScripts:'outside-only', pretendToBeVisual:true});
  t.after(() => dom.window.close());
  const w = dom.window;
  w.HTMLElement.prototype.scrollIntoView = function () {};
  w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  w.HTMLDialogElement.prototype.close = function () { this.open = false; };
  let entries = [], deleted = [], sequence = 0, copied = '';
  const calls = [];
  const payload = style => ({style, heading:style === 'APA' ? 'References' : style === 'MLA' ? 'Works Cited' : 'Bibliography',
    count:entries.length, entries:entries.map(e => ({...e,...citation(e.fields).styles[style]})),
    plain:entries.map(e=>e.fields.title).join('\n\n'),html:entries.map(e=>'<p><em>'+encode(e.fields.title)+'</em></p>').join('')});
  Object.defineProperty(w.navigator, 'clipboard', {value:{writeText:async text=>{copied=text;}}});
  w.fetch = async (url, options) => {
    const method = options.method || 'GET';
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({url,method,body});
    if (intercept) { const handled = intercept(url, options, body); if (handled) return handled; }
    const style = new URL(url, 'http://localhost').searchParams.get('style') || 'APA';
    let result;
    if (url === '/api/format') result = citation(body);
    else if (url === '/api/lookup') result = {fields:{...base,title:'Imported book'}};
    else if (url.startsWith('/api/library/restore')) {entries.push(...deleted.filter(e=>body.ids.includes(e.id))); deleted=[];result={...payload(style),message:'Restored.'};}
    else if (method === 'GET') result=payload(style);
    else if (method === 'POST') { const id=String(++sequence);entries.push({id,fields:body.fields});result={...payload(style),saved_id:id,message:'Source saved.'}; }
    else if (method === 'PUT') {const entry=entries.find(e=>e.id===body.id);entry.fields=body.fields;result={...payload(style),saved_id:entry.id,message:'Changes saved.'};}
    else if (method === 'DELETE') {deleted=entries.filter(e=>body.id==='*'||e.id===body.id);entries=entries.filter(e=>!deleted.includes(e));result={...payload(style),removed_ids:deleted.map(e=>e.id),message:'Removed.'};}
    return {ok:true,json:async()=>result};
  };
  if (initial !== null) w.sessionStorage.setItem('citation-formatter-draft-v2', JSON.stringify({fields:initial,editingId:null}));
  w.eval(fs.readFileSync(path.join(packageRoot, 'static/state.js'),'utf8'));
  w.eval(fs.readFileSync(path.join(packageRoot, 'static/script.js'),'utf8'));
  const input = (id,value) => {const node=w.document.getElementById(id);node.value=value;node.dispatchEvent(new w.Event('input',{bubbles:true}));};
  return {w,doc:w.document,calls,input,copied:()=>copied,entries:()=>entries};
}

test('startup renders all styles and uses the restored source', async t => {
  const {doc} = await setup(t); await wait(280);
  styleNames.forEach(style => assert.equal(doc.getElementById('out-'+style).textContent,'Initial book'));
  assert.equal(doc.getElementById('save').disabled,false);
  assert.match(doc.getElementById('status').textContent,/Ready/);
});
test('cleared draft stays empty after startup', async t => {
  const {doc} = await setup(t,{initial:{source_type:'book',title:'',author_mode:'people'}}); await wait(280);
  assert.equal(doc.getElementById('title').value,'');
  assert.equal(doc.getElementById('out-APA').textContent,'');
  assert.equal(doc.getElementById('save').disabled,true);
});
test('an older formatting response cannot overwrite a new title', async t => {
  let release;
  const {doc,input} = await setup(t,{intercept:(url,options,body)=>{
    if (url==='/api/format' && body.title==='Initial book') return new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>citation(body)});});
  }});
  await wait(280); input('title','New title'); await wait(280);
  assert.equal(doc.getElementById('out-APA').textContent,'New title');
  release(); await wait(5);
  assert.equal(doc.getElementById('out-APA').textContent,'New title');
});
test('clear immediately disables copy and invalidates an in-flight response', async t => {
  let release;
  const {doc} = await setup(t,{intercept:(url,options,body)=>{
    if(url==='/api/format') return new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>citation(body)});});
  }});
  await wait(280); doc.getElementById('clear').click();release();await wait(10);
  assert.equal(doc.getElementById('out-APA').textContent,'');
  assert.equal(doc.querySelector('.copy[data-style="APA"]').disabled,true);
});
test('save, edit, and update preserve the source ID', async t => {
  const {doc,input,calls,entries} = await setup(t); await wait(280);
  doc.getElementById('save').click(); await wait(20);
  assert.equal(entries().length,1);
  doc.getElementById('new-source').click(); doc.querySelector('.edit-source').click();
  assert.equal(doc.getElementById('title').value,'Initial book');
  input('title','Updated title'); await wait(280); doc.getElementById('save').click(); await wait(20);
  assert.equal(entries().length,1);assert.equal(entries()[0].id,'1');assert.equal(entries()[0].fields.title,'Updated title');
  assert.equal(calls.filter(call=>call.method==='PUT').length,1);
});
test('remove and undo reconnect to the saved list', async t => {
  const {doc,entries} = await setup(t);await wait(280);doc.getElementById('save').click();await wait(20);
  doc.querySelector('.remove').click();await wait(20);
  assert.equal(entries().length,0);assert.equal(doc.getElementById('undo-bar').hidden,false);
  doc.getElementById('undo-remove').click();await wait(20);
  assert.equal(entries().length,1);assert.equal(doc.getElementById('undo-bar').hidden,true);
});
test('copy falls back visibly and keeps its icon', async t => {
  const {doc,copied} = await setup(t);await wait(280);
  const button=doc.querySelector('.copy[data-style="APA"]');button.click();await wait(5);
  assert.equal(copied(),'Initial book');assert.ok(button.querySelector('svg'));
  assert.match(doc.getElementById('status').textContent,/Copied plain text/);
});
test('in-text citations have working individual copy actions', async t => {
  const {doc,copied} = await setup(t);await wait(280);
  doc.querySelector('.intext-copy').click();await wait(5);
  assert.equal(copied(),'(Doe, 2024)');
});
test('lookup presents a review before it replaces current edits', async t => {
  const {doc} = await setup(t);await wait(280);
  doc.getElementById('identifier').value='9780321973610';doc.getElementById('lookup').click();await wait(10);
  assert.equal(doc.getElementById('lookup-preview').open,true);
  assert.equal(doc.getElementById('title').value,'Initial book');
  doc.getElementById('replace-lookup').click();await wait(280);
  assert.equal(doc.getElementById('title').value,'Imported book');
});
test('website source switch collects the partial publication date', async t => {
  const {doc,input,calls} = await setup(t);await wait(280);
  doc.querySelector('[data-type="website"]').click(); input('published_date','2026-09');await wait(280);
  const fields=calls.filter(call=>call.url==='/api/format').at(-1).body;
  assert.equal(fields.published_date,'2026-09');assert.equal('year' in fields,false);
});
test('selected bibliography style changes its heading and exposed state', async t => {
  const {doc} = await setup(t);await wait(280);
  doc.querySelector('.style-option[data-style="MLA"]').click();await wait(10);
  assert.equal(doc.getElementById('library-heading-text').textContent,'Works Cited');
  assert.equal(doc.querySelector('.style-option[data-style="MLA"]').getAttribute('aria-pressed'),'true');
});
test('saved sources can be filtered without changing the library', async t => {
  const {doc,input,entries} = await setup(t);await wait(280);
  doc.getElementById('save').click();await wait(20);
  doc.getElementById('new-source').click();
  input('title','A second source');await wait(280);
  doc.getElementById('save').click();await wait(20);
  input('library-filter','Initial');await wait(5);
  assert.equal(entries().length,2);
  assert.equal(doc.querySelectorAll('.library-item').length,1);
  assert.match(doc.getElementById('library-filter-status').textContent,/1 of 2/);
});
test('saved titles cannot break out of their remove-button label', async t => {
  const title='"><img id="injected" src=x>';
  const {doc} = await setup(t,{initial:{...base,title}});await wait(280);
  doc.getElementById('save').click();await wait(20);
  assert.equal(doc.getElementById('injected'),null);
  assert.equal(doc.querySelector('.remove').getAttribute('aria-label'),'Remove '+title);
});
test('control-enter saves the current source', async t => {
  const {w,doc,entries} = await setup(t);await wait(280);
  doc.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,bubbles:true}));
  await wait(20);
  assert.equal(entries().length,1);
});
