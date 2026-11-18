const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const prettier = require(path.resolve("work/vendor-format/node_modules/prettier"));

const root = "work/codebuddy-local-result-v14";
const active = "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js";
const trace = "work/vmshare/confirmation-hy4flash-free-v14/C-swe-django__django-11999-B0-r3/model.jsonl";

async function assignment(file) {
  const source = fs.readFileSync(file, "utf8");
  const { ast } = await prettier.__debug.parse(source, { parser: "babel" });
  const stack = [ast];
  const matches = [];
  while (stack.length) {
    const node = stack.pop();
    if (node.type === "AssignmentExpression" && node.left?.object?.name === "ey"
      && node.left?.property?.name === "providerData" && node.right?.type === "ObjectExpression"
      && node.right.properties.some((p) => p.key?.name === "requestModelId")) {
      matches.push(source.slice(node.start, node.end));
    }
    for (const [key, value] of Object.entries(node)) {
      if (["loc", "comments", "tokens"].includes(key)) continue;
      if (Array.isArray(value)) stack.push(...value.filter((item) => item?.type));
      else if (value?.type) stack.push(value);
    }
  }
  assert.equal(matches.length, 1);
  return matches[0];
}

function replay(code, payload, enabled, changeHistory = () => {}) {
  const events = structuredClone(payload);
  const index = events.findIndex((item) => item.type === "function_call_result");
  assert.ok(index >= 0);
  const item = events[index];
  const provider = item.providerData;
  const history = structuredClone(events.slice(0, index));
  changeHistory(history);
  const context = vm.createContext({
    process: { env: { COURSE_CODEBUDDY_EXTERNAL_RECOVERY: enabled ? "1" : "0" } },
    ey: item, ef: {}, eu: provider.conversationRequestId,
    eA: { history, messageId: provider.messageId, telemetry: { modelId: provider.requestModelId } },
    ec: { model: provider.requestModelId }, ep: provider.requestModelId,
    eh: provider.requestModelName, ed: provider.traceId,
  });
  vm.runInContext(code, context);
  return JSON.parse(JSON.stringify(events));
}

async function main() {
  const events = fs.readFileSync(trace, "utf8").trim().split("\n").map(JSON.parse);
  const response = events.find((event) => event.event === "response" && event.request_id === 5).payload;
  const before = await assignment(`${root}/codebuddy-headless.formatted.js`);
  const after = await assignment(active);
  assert.deepEqual(replay(before, response, true), response);
  assert.deepEqual(replay(after, response, false), response);
  const fixed = replay(after, response, true);
  const index = response.findIndex((item) => item.type === "function_call_result");
  const expected = structuredClone(response);
  expected[index].providerData.model = response.find((item) => item.type === "function_call"
    && item.callId === response[index].callId).providerData.model;
  assert.deepEqual(fixed, expected);
  assert.deepEqual(fixed.filter((item) => item.type !== "function_call_result"),
    response.filter((item) => item.type !== "function_call_result"));
  const noParent = replay(after, response, true, (history) => {
    for (const item of history) if (item.type === "function_call") item.callId = "unmatched-local-test";
  });
  const wrongMessage = replay(after, response, true, (history) => {
    for (const item of history) if (item.type === "function_call") item.providerData.messageId = "unmatched-local-test";
  });
  const wrongRequest = replay(after, response, true, (history) => {
    for (const item of history) if (item.type === "function_call") item.providerData.conversationRequestId = "unmatched-local-test";
  });
  assert.deepEqual(noParent, response);
  assert.deepEqual(wrongMessage, response);
  assert.deepEqual(wrongRequest, response);
  fs.writeFileSync(`${root}/replay.json`, JSON.stringify({
    scope: "Offline actual SDK metadata-assignment replay of a saved response; no model or tool execution",
    original_rejection_reproduced: true, actual_provider_events_unchanged: true,
    changed_field: "function_call_result.providerData.model", checks: 6, model_calls: 0,
    fixed, no_parent: noParent, wrong_message: wrongMessage, wrong_request: wrongRequest,
  }, null, 2) + "\n");
  console.log(JSON.stringify({ status: "passed", checks: 6, model_calls: 0,
    actual_provider_events_unchanged: true, only_local_tool_result_identity_changed: true }));
}

main().catch((error) => { process.stderr.write(error.stack + "\n"); process.exitCode = 1; });
