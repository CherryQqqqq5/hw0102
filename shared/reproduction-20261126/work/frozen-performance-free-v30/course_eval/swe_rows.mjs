import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const [, , dependencies, parquet, mode] = process.argv;
if (!dependencies || !parquet || !['inventory', 'grader'].includes(mode)) {
  throw new Error('Usage: node course_eval/swe_rows.mjs /absolute/npm-prefix/package.json FILE inventory|grader');
}

const requireDependency = createRequire(dependencies);
const { asyncBufferFromFile, parquetReadObjects } = await import(
  pathToFileURL(requireDependency.resolve('hyparquet'))
);
const { compressors } = await import(pathToFileURL(requireDependency.resolve('hyparquet-compressors')));
const file = await asyncBufferFromFile(parquet);
const inventory = ['instance_id', 'repo', 'base_commit', 'difficulty', 'image', 'eval_type'];
const rows = await parquetReadObjects({ file, compressors, ...(mode === 'inventory' ? { columns: inventory } : {}) });
if (rows.length !== 500 || new Set(rows.map(row => row.instance_id)).size !== rows.length) {
  throw new Error('Expected 500 distinct SWE-bench Verified tasks');
}
process.stdout.write(JSON.stringify(rows));
