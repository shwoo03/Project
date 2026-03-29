import test from 'node:test';
import assert from 'node:assert/strict';

import { findHttpMockMatch } from '../src/utils/replay-mock-utils.js';

test('findHttpMockMatch allows bounded GraphQL fallback on operation and variables for render-critical requests', () => {
  const match = findHttpMockMatch([{
    method: 'POST',
    path: '/graphql',
    search: '',
    normalizedSearch: '',
    replayRole: 'render-critical',
    graphQL: true,
    matchStrategy: 'graphql-operation',
    graphQLOperationName: 'HomeQuery',
    graphQLVariablesHash: 'vars-1',
    graphQLDetails: {
      operationName: 'HomeQuery',
      variablesHash: 'vars-1',
      documentHash: 'expected-doc',
      extensions: null,
    },
  }], {
    method: 'POST',
    path: '/graphql',
    search: '',
    bodyHash: 'body-1',
    operationName: 'HomeQuery',
    documentHash: 'different-doc',
    variablesHash: 'vars-1',
    extensionsHash: 'no-body',
  });

  assert.equal(Boolean(match), true);
});
