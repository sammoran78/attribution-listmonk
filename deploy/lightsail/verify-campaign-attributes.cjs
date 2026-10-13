// Run the real API response interceptor and key transformer without network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const src = path.resolve(__dirname, '../../frontend/src');
const stripImports = (s) => s.replace(/^import[\s\S]*?from ['"][^'"]+['"];\r?$/gm, '');
const utilsSource = stripImports(fs.readFileSync(path.join(src, 'utils.js'), 'utf8'))
  .replace('export default class Utils', 'return class Utils');
const Utils = new Function('dayjs', 'updateLocale', 'relativeTime', 'dayDuration', utilsSource)(
  { extend() {} }, {}, {}, {},
);
let interceptor;
let responseData;
const http = {
  interceptors: { request: { use() {} }, response: { use(fn) { interceptor = fn; } } },
  async get(url, config = {}) { return interceptor({ config, data: { data: structuredClone(responseData) } }); },
  async post(url, data, config = {}) { return interceptor({ config, data: { data: structuredClone(responseData) } }); },
  async put(url, data, config = {}) { return interceptor({ config, data: { data: structuredClone(responseData) } }); },
};
const apiSource = stripImports(fs.readFileSync(path.join(src, 'api/index.js'), 'utf8'))
  .replaceAll('export const ', 'const ').replaceAll('import.meta.env', '({})');
const exportsToCheck = ['getCampaigns', 'getCampaign', 'createCampaign', 'updateCampaign', 'updateCampaignArchive', 'changeCampaignStatus'];
const api = new Function('axios', 'Utils', 'store', 'models', 'Toast', 'qs', apiSource + `\nreturn {${exportsToCheck.join(',')}};`)(
  { create: () => http }, Utils, { commit() {} }, {}, {}, {},
);
const original = {
  id: 3, from_email: 'CAIRN <newsletter@example.com>', template_id: 5,
  attribs_backup: 'ordinary field still converts',
  headers: [{ 'X-Custom-Header': 'keep verbatim' }],
  attribs: {
    cairn: { event_title: 'Reading group', zoom_url: 'https://example.com/zoom', calendar_ics_url: 'https://example.com/event.ics' },
    'My-Custom-Key': [{ Mixed_Case: true, 'space in name': 'preserve' }],
  },
};
function check(record, label) {
  assert.deepEqual(record.attribs, original.attribs, `${label}: custom attributes changed`);
  assert.deepEqual(record.headers, original.headers, `${label}: headers changed`);
  assert.equal(record.fromEmail, original.from_email);
  assert.equal(record.templateId, 5);
  assert.equal(record.attribsBackup, original.attribs_backup);
}
(async () => {
  for (const name of exportsToCheck) {
    responseData = name === 'getCampaigns' ? { results: [original] } : original;
    const data = await api[name](3, original);
    check(name === 'getCampaigns' ? data.results[0] : data, name);
    console.log(`${name}: nested attribute/header keys preserved`);
  }
  // Simulate the editor's repeated save/reopen JSON round trips.
  responseData = structuredClone(original);
  for (let n = 0; n < 3; n += 1) {
    const saved = await api.updateCampaign(3, responseData);
    responseData.attribs = JSON.parse(JSON.stringify(saved.attribs));
    const reopened = await api.getCampaign(3);
    check(reopened, `save/reopen ${n + 1}`);
  }
  console.log('Three save/reopen cycles passed; ordinary API fields still convert. No network requests made.');
})().catch((err) => { console.error(err); process.exitCode = 1; });
