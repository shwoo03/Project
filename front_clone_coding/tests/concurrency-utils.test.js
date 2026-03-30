import { test } from 'node:test';
import assert from 'node:assert/strict';
import { batchParallel } from '../src/utils/concurrency-utils.js';

test('batchParallel respects bounded concurrency', async () => {
  let active = 0;
  let maxActive = 0;
  const items = Array.from({ length: 20 }, (_, i) => i);

  await batchParallel(items, 4, async () => {
    active++;
    maxActive = Math.max(maxActive, active);
    await new Promise((r) => setTimeout(r, 10));
    active--;
  });

  assert.ok(maxActive <= 4, `max active was ${maxActive}, expected <= 4`);
  assert.ok(maxActive >= 2, `max active was ${maxActive}, expected >= 2 for real parallelism`);
});

test('batchParallel returns allSettled-style results', async () => {
  const results = await batchParallel([1, 2, 3], 3, async (item) => item * 10);

  assert.equal(results.length, 3);
  assert.equal(results[0].status, 'fulfilled');
  assert.equal(results[0].value, 10);
  assert.equal(results[1].value, 20);
  assert.equal(results[2].value, 30);
});

test('batchParallel handles empty input', async () => {
  const results = await batchParallel([], 5, async () => {});
  assert.deepEqual(results, []);
});

test('batchParallel isolates errors without stopping other items', async () => {
  const results = await batchParallel([1, 2, 3, 4], 2, async (item) => {
    if (item === 2) throw new Error('fail');
    return item;
  });

  assert.equal(results[0].status, 'fulfilled');
  assert.equal(results[0].value, 1);
  assert.equal(results[1].status, 'rejected');
  assert.equal(results[1].reason.message, 'fail');
  assert.equal(results[2].status, 'fulfilled');
  assert.equal(results[2].value, 3);
  assert.equal(results[3].status, 'fulfilled');
  assert.equal(results[3].value, 4);
});

test('batchParallel preserves result order', async () => {
  const items = [50, 10, 30, 20, 40];
  const results = await batchParallel(items, 3, async (item) => {
    await new Promise((r) => setTimeout(r, item));
    return item;
  });

  assert.equal(results[0].value, 50);
  assert.equal(results[1].value, 10);
  assert.equal(results[2].value, 30);
  assert.equal(results[3].value, 20);
  assert.equal(results[4].value, 40);
});
