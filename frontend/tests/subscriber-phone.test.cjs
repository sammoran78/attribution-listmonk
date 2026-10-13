const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const Vue = require('vue');
const { parseComponent } = require('vue-template-compiler');

// Load the real component script without browser-only child components.
const source = readFileSync(path.join(__dirname, '../src/views/SubscriberForm.vue'), 'utf8');
const script = parseComponent(source).script.content
  .replace(/^import .*;\r?\n/gm, '')
  .replace('export default', 'return');
const SubscriberForm = new Function('Vue', 'mapState', 'ListSelector', 'CopyText', 'SubscriberActivity', script)(
  Vue, () => ({}), {}, {}, {},
);

function form(data, isEditing) {
  const requests = [];
  const parent = new Vue();
  parent.close = () => {};
  const vm = new SubscriberForm({ parent, propsData: { data, isEditing } });
  const save = (payload) => {
    requests.push(JSON.parse(JSON.stringify(payload)));
    return Promise.resolve(payload);
  };
  vm.$api = {
    createSubscriber: save,
    updateSubscriber: save,
    getSubscriberBounces: () => Promise.resolve([]),
  };
  vm.$t = (s) => s;
  vm.$utils = { toast: () => {} };
  vm.$refs.focus = { focus: () => {} };
  vm.$options.mounted.forEach((hook) => hook.call(vm));
  return { vm, requests };
}

test('create, reload, update and clear phone while preserving other attributes', async () => {
  const created = form({ lists: [] }, false);
  created.vm.form.email = 'phone@example.com';
  created.vm.form.phone = '  +61 (0)412 345 678  ';
  created.vm.form.strAttribs = '{"city":"Sydney","nested":{"keep":true}}';
  created.vm.createSubscriber();
  await Vue.nextTick();
  assert.equal(created.requests[0].attribs.phone, '+61 (0)412 345 678');

  const record = { ...created.requests[0], id: 42 };
  const edited = form(record, true);
  assert.equal(edited.vm.form.phone, record.attribs.phone);
  assert.deepEqual(JSON.parse(edited.vm.form.strAttribs), { city: 'Sydney', nested: { keep: true } });
  edited.vm.form.phone = '0412 000 000';
  edited.vm.updateSubscriber();
  await Vue.nextTick();
  assert.deepEqual(edited.requests[0].attribs, {
    city: 'Sydney', nested: { keep: true }, phone: '0412 000 000',
  });
  assert.equal(record.attribs.phone, '+61 (0)412 345 678');

  edited.vm.form.phone = '  ';
  edited.vm.updateSubscriber();
  await Vue.nextTick();
  assert.deepEqual(edited.requests[1].attribs, { city: 'Sydney', nested: { keep: true } });
});

test('phone remains optional for new and existing subscribers', async () => {
  for (const isEditing of [false, true]) {
    const { vm, requests } = form({ id: 1, email: 'email@example.com', lists: [], attribs: null }, isEditing);
    vm.onSubmit();
    await Vue.nextTick();
    assert.equal(requests.length, 1);
    assert.deepEqual(requests[0].attribs, {});
  }
});

test('invalid attributes cannot discard phone or submit corrupt data', () => {
  for (const strAttribs of ['null', '[]', 'true', '42', '"text"', '{broken']) {
    const { vm, requests } = form({ lists: [] }, false);
    vm.form.phone = '+61 412 345 678';
    vm.form.strAttribs = strAttribs;
    vm.createSubscriber();
    assert.equal(requests.length, 0);
    assert.equal(vm.form.phone, '+61 412 345 678');
  }
});
