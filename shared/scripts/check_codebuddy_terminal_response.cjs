const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const prettier = require(path.resolve("work/vendor-format/node_modules/prettier"));

const root = "work/codebuddy-terminal-response-v11";
const active = "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js";

function* nodes(ast) {
  const stack = [ast];
  while (stack.length) {
    const current = stack.pop();
    yield current;
    for (const [key, value] of Object.entries(current)) {
      if (["loc", "comments", "tokens"].includes(key)) continue;
      if (Array.isArray(value)) stack.push(...value.filter((item) => item?.type));
      else if (value?.type) stack.push(value);
    }
  }
}

async function extract(file) {
  const source = fs.readFileSync(file, "utf8");
  const { ast } = await prettier.__debug.parse(source, { parser: "babel" });
  const functions = {};
  let render;
  let constructor;
  const modules = {};
  for (const node of nodes(ast)) {
    if (node.type === "ObjectMethod" && [895, 96829].includes(node.key?.value)) {
      const entries = {};
      for (const statement of node.body.body) {
        for (const call of nodes(statement)) {
          if (call.type !== "CallExpression" || call.callee?.object?.name !== "ec"
            || call.callee?.property?.name !== "d" || call.arguments[0]?.name !== "el"
            || call.arguments[1]?.type !== "ObjectExpression") continue;
          for (const property of call.arguments[1].properties) {
            entries[property.key.name ?? property.key.value] = property.value.body?.name;
          }
        }
      }
      modules[node.key.value] = entries;
    }
    if (node.type === "ClassExpression") {
      const names = node.body.body.map((method) => method.key?.name);
      if (names.includes("waitForResultCompletion") && names.includes("render")) {
        const method = node.body.body.find((method) => method.key?.name === "render");
        render = source.slice(method.start, method.end);
        const ctor = node.body.body.find((method) => method.kind === "constructor");
        constructor = source.slice(ctor.start, ctor.end);
      }
      if (["AgentsError", "MaxTurnsExceededError", "OpenaiAgentsCompatibilityError"].includes(node.id?.name)) {
        functions[node.id.name] = source.slice(node.start, node.end);
      }
    }
    if (node.type === "FunctionDeclaration" && ["isMaxTurnsExceededError", "getStreamPhysicalCompletion",
      "isThenable", "waitForSessionResultProcessing"].includes(node.id?.name)) {
      functions[node.id.name] = source.slice(node.start, node.end);
    }
  }
  assert.ok(render);
  assert.equal(modules[895].IN, "isMaxTurnsExceededError");
  assert.equal(modules[895].QL, "getStreamPhysicalCompletion");
  assert.equal(modules[96829].waitForSessionResultProcessing, "waitForSessionResultProcessing");
  return { render, constructor, functions, modules };
}

function verifyNamespace(extracted) {
  for (const name of ["isMaxTurnsExceededError", "getStreamPhysicalCompletion"]) {
    if (extracted.render.includes(`eb.${name}`)) {
      assert.ok(name in extracted.modules[96829], `Actual module 96829 does not export ${name}`);
    }
  }
}

async function replay(extracted, recorded, errorKind, enabled) {
  const headers = [];
  const order = [];
  const context = vm.createContext({
    process: { env: { COURSE_CODEBUDDY_EXTERNAL_RECOVERY: enabled ? "1" : "0" } },
    ev: { Context: { getRequest: () => ({ body: { outputFormat: "json" } }),
      getResponse: () => ({ setHeader: (...args) => headers.push(args) }) } },
    eE: { HttpHeaders: { CONTENT_TYPE: "Content-Type" },
      MediaType: { APPLICATION_JSON_UTF8: "application/json" } }, An: new Set(),
  });
  const definitions = extracted.functions;
  vm.runInContext(`const AgentsError = ${definitions.AgentsError};
    const MaxTurnsExceededError = ${definitions.MaxTurnsExceededError};
    const OpenaiAgentsCompatibilityError = ${definitions.OpenaiAgentsCompatibilityError};
    let eQ = MaxTurnsExceededError; const ej = "recorded replay";
    ${definitions.isThenable}
    ${definitions.isMaxTurnsExceededError}
    ${definitions.getStreamPhysicalCompletion}
    ${definitions.waitForSessionResultProcessing}
    globalThis.native = {MaxTurnsExceededError, isMaxTurnsExceededError, getStreamPhysicalCompletion,
      waitForSessionResultProcessing};`, context);
  const compatibility = { IN: context.native.isMaxTurnsExceededError,
    QL: context.native.getStreamPhysicalCompletion };
  context.ec = (id) => {
    assert.equal(id, 895);
    assert.ok("IN" in extracted.modules[id] && "QL" in extracted.modules[id]);
    return compatibility;
  };
  const core = { RunResultUtils: { isStream: () => true },
    waitForSessionResultProcessing: context.native.waitForSessionResultProcessing,
    ErrorUtils: { getErrorMessage: (error) => error.message } };
  context.eb = new Proxy(core, { get(target, name) {
    assert.ok(name in extracted.modules[96829], `Actual module 96829 does not export ${String(name)}`);
    return target[name];
  } });
  const error = errorKind === "max_turns" ? new context.native.MaxTurnsExceededError("Max turns (1) exceeded")
    : new Error("recorded test: unrelated transport failure");
  const completion = errorKind === "none" ? Promise.resolve() : Promise.reject(error);
  const stream = { completed: completion, state: { _currentStep: { type: "next_step_final_output" } },
    whenStreamLoopSettled: async () => { order.push("physical_stream_settled"); } };
  const session = { resultSubject: { value: stream } };
  context.An.add({ session, result: stream, settled: Promise.resolve().then(() => order.push("history_processed")) });
  const view = vm.runInContext(`new (class { ${extracted.constructor} ${extracted.render} })()`, context);
  let output;
  Object.assign(view, {
    // 回放使用已保存的真实响应；只注入本地异常，不创建提供方响应或费用。
    waitForResultCompletion: async () => { await completion; },
    toSerializableArray: () => structuredClone(recorded),
    logger: { info: () => {} }, jsonView: { contentType: "application/json",
      render: async (events) => { order.push("json_serialized"); output = JSON.stringify(events); } },
  });
  try {
    await view.render(session, {});
  } catch (caught) {
    assert.equal(caught, error);
    assert.equal(output, undefined);
    return { propagated: true, error: caught.name };
  }
  assert.ok(output);
  const payload = JSON.parse(output);
  assert.deepEqual(payload.filter((item) => item.type !== "result"), recorded.filter((item) => item.type !== "result"));
  const terminal = payload.find((item) => item.type === "result");
  if (errorKind === "max_turns") {
    assert.equal(terminal.subtype, "error_max_turns");
    assert.equal(terminal.is_error, true);
    assert.equal(terminal.structured_output, undefined);
    assert.ok(order.indexOf("physical_stream_settled") < order.indexOf("json_serialized"));
    assert.ok(order.indexOf("history_processed") < order.indexOf("json_serialized"));
  } else {
    assert.deepEqual(payload, recorded);
  }
  assert.equal(headers.length, 1);
  return { propagated: false, payload, order };
}

async function main() {
  const events = fs.readFileSync("evals/regression_cases/codebuddy-capped-structured-success/model.jsonl", "utf8")
    .trim().split("\n").map(JSON.parse);
  const recorded = events.find((event) => event.event === "response").payload;
  const before = await extract(path.join(root, "codebuddy-headless.v10.js"));
  verifyNamespace(before);
  assert.equal((await replay(before, recorded, "max_turns", true)).propagated, true);
  const broken = await extract(path.join(root, "codebuddy-headless.failed-cf1edc0d.js"));
  assert.throws(() => verifyNamespace(broken), /does not export/);
  const after = await extract(active);
  verifyNamespace(after);
  const fixed = await replay(after, recorded, "max_turns", true);
  assert.equal(fixed.propagated, false);
  assert.equal((await replay(after, recorded, "none", true)).propagated, false);
  assert.equal((await replay(after, recorded, "unrelated", true)).propagated, true);
  assert.equal((await replay(after, recorded, "max_turns", false)).propagated, true);
  const missing = structuredClone(recorded);
  for (const event of missing) if (event.providerData) delete event.providerData.rawUsage;
  const paid = JSON.parse(fs.readFileSync("work/codebuddy-quota-probe/hy4free-smoke-bundledca.stdout.json", "utf8"));
  const output = { scope: "Offline native-render method replay with recorded provider events and injected local exception; not a live CLI result",
    before_rejects_known_turn_error: true, preserved_provider_events: true,
    unknown_error_propagates: true, disabled_flag_propagates: true, normal_result_unchanged: true,
    actual_export_maps_verified: true, failed_cf1edc0d_namespace_rejected: true,
    fixed, missing_receipt: await replay(after, missing, "max_turns", true),
    paid_receipt: await replay(after, paid, "max_turns", true), model_calls: 0 };
  fs.writeFileSync(path.join(root, "render-replay.json"), JSON.stringify(output, null, 2) + "\n");
  process.stdout.write(JSON.stringify({ status: "passed", model_calls: 0, cases: 8,
    provider_events_preserved: true, original_error_reproduced: true }) + "\n");
}

main().catch((error) => { process.stderr.write(error.stack + "\n"); process.exitCode = 1; });
