const fs = require("node:fs");
const crypto = require("node:crypto");
const prettier = require(require("node:path").resolve("work/vendor-format/node_modules/prettier"));

async function normalizedAstDigest(file) {
  const { ast } = await prettier.__debug.parse(fs.readFileSync(file, "utf8"), {
    parser: "babel",
    filepath: "codebuddy-headless.js",
  }, { massage: true });
  const serialized = JSON.stringify(ast, (key, value) => {
    return typeof value === "bigint" ? { bigint: value.toString() } : value;
  });
  return crypto.createHash("sha256").update(serialized).digest("hex");
}

async function main() {
  const [sourceFile = "work/codebuddy-single-turn-probe-v9/original-codebuddy-headless.js",
    formattedFile = "work/vendor-format/codebuddy-headless.before.js",
    outputFile = "work/codebuddy-vendor-format-verification.json"] = process.argv.slice(2);
  const upstream = await normalizedAstDigest(
    sourceFile,
  );
  const formatted = await normalizedAstDigest(formattedFile);
  if (upstream !== formatted) throw new Error("Formatting changed the normalized JavaScript syntax tree");
  const record = {
    check: "upstream and range-formatted JavaScript have identical normalized Babel syntax trees",
    status: "passed", upstream_ast: upstream, formatted_ast: formatted,
    normalization: "Prettier's own JavaScript AST massage used by --debug-check",
    standard_debug_check: "Prettier CLI failed to serialize a BigInt; this check retains BigInt values explicitly",
    model_calls: 0,
  };
  fs.writeFileSync(outputFile, JSON.stringify(record, null, 2) + "\n");
  process.stdout.write(JSON.stringify(record) + "\n");
}

main().catch((error) => {
  process.stderr.write(String(error) + "\n");
  process.exitCode = 1;
});
