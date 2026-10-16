// Public HDBR Atlas assets for the private non-commercial anatomy preview.
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const directory = new URL('../private_assets/hdbr/', import.meta.url);
const sources = [
  ['CS14', 'cs14_A386.glb', 'b784976080212e7557cee02a00fd2978f32e8b0a86fbf1a17eac3e3439fdbc9c'],
  ['CS15', 'N340.glb', '0f7905696199d4558c5e07c98acaba283245d16ee0cf2607813f4aa5213dc6d2'],
];
await mkdir(directory, { recursive: true });
for (const [stage, file, expected] of sources) {
  const target = new URL(file, directory);
  const checksum = bytes => createHash('sha256').update(bytes).digest('hex');
  const existing = await readFile(target).catch(() => null);
  if (existing) {
    if (checksum(existing) !== expected) throw new Error(`Existing ${file} checksum mismatch; preserve and inspect it.`);
    console.log(`${stage}: verified existing asset`); continue;
  }
  const response = await fetch(`https://hdbratlas.org/carnegie-stages/${stage}/${file}`, { signal: AbortSignal.timeout(60000) });
  if (!response.ok) throw new Error(`${stage}: HTTP ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (checksum(bytes) !== expected) throw new Error(`${stage}: source changed; review before using.`);
  await writeFile(target, bytes, { flag: 'wx' });
  console.log(`${stage}: downloaded and verified`);
}
