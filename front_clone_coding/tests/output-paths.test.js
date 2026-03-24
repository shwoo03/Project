import test from 'node:test';
import assert from 'node:assert/strict';

import { getOutputDomainRoot } from '../src/index.js';

test('output packages always use the registrable domain as the folder name', () => {
  assert.equal(getOutputDomainRoot('https://www.netflix.com/kr-en/'), 'netflix.com');
  assert.equal(getOutputDomainRoot('https://subdomain.example.co.uk/dashboard'), 'example.co.uk');
});
