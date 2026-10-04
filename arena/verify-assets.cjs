// Verify the distributable against its snapshot inventory, without network access.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const repo = path.resolve(__dirname, '..');
const inventory = JSON.parse(fs.readFileSync(path.join(__dirname, 'ASSET_INVENTORY.json'), 'utf8').replace(/^\uFEFF/, ''));
let bytes = 0;
for (const file of inventory.files) {
  const target = path.resolve(repo, file.path);
  assert.ok(target.startsWith(repo + path.sep), 'Inventory path leaves package');
  const content = fs.readFileSync(target);
  assert.equal(content.length, file.bytes, 'Size mismatch: ' + file.path);
  assert.equal(crypto.createHash('sha256').update(content).digest('hex'), file.sha256, 'Hash mismatch: ' + file.path);
  bytes += content.length;
}
const scenes = JSON.parse(fs.readFileSync(path.join(__dirname, 'scenes-v2/manifest.json'), 'utf8'));
assert.equal(scenes.length, 14);
assert.ok(scenes.every(s => s.approval === 'APPROVED'));
for (const scene of scenes) assert.ok(fs.existsSync(path.join(__dirname, 'scenes-v2', scene.file)));
console.log(`Verified ${inventory.files.length} files (${bytes} bytes), including all 14 approved scene assets.`);
