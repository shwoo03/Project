/**
 * Process items in parallel with bounded concurrency using a semaphore-style worker pool.
 * Unlike chunked batching, workers start the next item immediately when one completes.
 *
 * @param {Array} items - Items to process
 * @param {number} concurrency - Max parallel operations
 * @param {Function} fn - async (item, index) => result
 * @returns {Promise<Array<{status: string, value?: *, reason?: *}>>}
 */
export async function batchParallel(items, concurrency, fn) {
  if (!items || items.length === 0) return [];

  const results = new Array(items.length);
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < items.length) {
      const index = nextIndex++;
      try {
        results[index] = { status: 'fulfilled', value: await fn(items[index], index) };
      } catch (reason) {
        results[index] = { status: 'rejected', reason };
      }
    }
  }

  const workerCount = Math.min(concurrency, items.length);
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return results;
}
