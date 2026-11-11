const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(__dirname + "/../assets/js/nova_status.js", "utf8");
const contract = "mosa2_nova_status_v1";
const symbol = {dataset: {}, setAttribute(name, value) { this[name] = value; }};
let visibility;
let clock = 0;
let requests = 0;
let timerId = 0;
const timers = new Map();
const document = {
  hidden: false,
  querySelector: () => symbol,
  addEventListener(name, handler) { assert.equal(name, "visibilitychange"); visibility = handler; }
};
let resolveRequest;
const context = {
  document, AbortSignal, performance: {now: () => clock},
  setTimeout(fn, delay) { timers.set(++timerId, {fn, delay}); return timerId; },
  clearTimeout(id) { timers.delete(id); },
  fetch(url, options) {
    assert.equal(url, "api/nova_status.php");
    assert.equal(options.credentials, "same-origin");
    requests++;
    return new Promise(resolve => { resolveRequest = resolve; });
  }
};
const flush = () => new Promise(setImmediate);
async function reply(state, version = contract, ok = true) {
  resolveRequest({ok, json: async () => ({contract_version: version, state})});
  await flush();
}
function tick() {
  assert.equal(timers.size, 1);
  const [id, {fn, delay}] = [...timers][0];
  assert.equal(delay, 5000);
  timers.delete(id);
  clock += delay;
  fn();
}

(async () => {
  vm.runInNewContext(source, context);
  vm.runInNewContext(source, context);
  visibility();
  assert.equal(requests, 1, "Repeated initialization and visibility events cannot overlap a request");
  await reply("running");
  assert.equal(symbol["aria-label"], "NOVA arbeitet");
  tick();
  await reply("idle");
  assert.equal(symbol.title, "NOVA bereit");
  document.hidden = true;
  visibility();
  assert.equal(timers.size, 0);
  document.hidden = false;
  visibility();
  assert.equal(requests, 3, "Visibility resumes immediately");
  await reply("running", "invalid");
  assert.equal(symbol.dataset.state, "unavailable");
  tick();
  await reply("running", contract, false);
  assert.equal(symbol.title, "NOVA-Status nicht verfügbar");
  tick();
  await reply("unavailable");
  assert.equal(symbol.dataset.state, "unavailable");
  console.log("PASS NOVA states, invalid responses, visibility and one polling loop");
})().catch(error => { console.error(error); process.exitCode = 1; });
