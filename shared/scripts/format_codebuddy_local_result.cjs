const fs = require("node:fs");
const path = require("node:path");
const prettier = require(path.resolve("work/vendor-format/node_modules/prettier"));

(async () => {
  const root = "work/codebuddy-local-result-v14";
  const file = "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js";
  const source = fs.readFileSync(file, "utf8");
  const marker = "ey.providerData={conversationRequestId:eu,...ef,...ey.providerData,messageId:";
  const start = source.indexOf(marker);
  const end = source.indexOf(";let eE=", start);
  if (start < 0 || end < start || source.indexOf(marker, start + 1) >= 0) {
    throw new Error("Expected unique stream-history metadata assignment not found");
  }
  fs.mkdirSync(root, { recursive: true });
  fs.copyFileSync(file, `${root}/codebuddy-headless.fbd46d70.js`);
  const formatted = await prettier.format(source, { parser: "babel", rangeStart: start, rangeEnd: end });
  fs.writeFileSync(file, formatted);
  fs.copyFileSync(file, `${root}/codebuddy-headless.formatted.js`);
  console.log(JSON.stringify({ rangeStart: start, rangeEnd: end, formattingOnly: true }));
})().catch((error) => { process.stderr.write(error.stack + "\n"); process.exitCode = 1; });
