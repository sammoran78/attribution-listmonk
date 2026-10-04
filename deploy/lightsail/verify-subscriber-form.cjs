// Exercise the actual frontend permission predicates without browser credentials.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = path.resolve(__dirname, '../../frontend/src');
const main = fs.readFileSync(path.join(src, 'main.js'), 'utf8');
const predicates = main.slice(main.indexOf('Vue.prototype.$can ='), main.indexOf('// Set the page title after'));
const form = fs.readFileSync(path.join(src, 'views/SubscriberForm.vue'), 'utf8');
const manageable = new Function(form.match(/manageableLists\(\) \{([\s\S]*?)\n    \},/)[1]);
const optin = new Function(form.match(/hasOptinList\(\) \{([\s\S]*?)\n    \},/)[1]);

for (const [name, role, permissions, assigned, expected] of [
  ['super admin without list role', 1, [], null, [4, 5, 6]],
  ['view all cannot manage', 3, ['lists:get_all'], null, []],
  ['global management', 3, ['lists:manage_all'], null, [4, 5, 6]],
  ['unassigned', 3, [], null, []],
  ['assigned management', 3, [], { lists: [{ id: 4, permissions: ['list:get', 'list:manage'] }] }, [4]],
  ['assigned read only', 3, [], { lists: [{ id: 4, permissions: ['list:get'] }] }, []],
]) {
  const Vue = { prototype: {} };
  vm.runInNewContext(predicates, { Vue, profile: { userRole: { id: role, permissions }, listRole: assigned } });
  const selected = manageable.call({ lists: { results: [4, 5, 6].map(id => ({ id })) },
    $canList: Vue.prototype.$canList });
  assert.deepEqual(selected.map(l => l.id), expected, name);
  console.log(`${name}: passed`);
}
assert.equal(optin.call({ form: { lists: [] } }), false);
assert.equal(optin.call({ form: { lists: [{ optin: 'single' }] } }), false);
assert.equal(optin.call({ form: { lists: [{ optin: 'single' }, { optin: 'double' }] } }), true);
console.log('Preconfirmation is available for double opt-in only: passed');
