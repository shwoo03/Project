import js from '@eslint/js';
import nodePlugin from 'eslint-plugin-n';

export default [
  js.configs.recommended,
  {
    plugins: { n: nodePlugin },
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      globals: {
        console: 'readonly',
        process: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        Buffer: 'readonly',
        URL: 'readonly',
        Map: 'readonly',
        Set: 'readonly',
        Promise: 'readonly',
        AbortController: 'readonly',
        EventTarget: 'readonly',
        Element: 'readonly',
        HTMLElement: 'readonly',
        navigator: 'readonly',
        window: 'readonly',
        document: 'readonly',
        history: 'readonly',
        location: 'readonly',
        globalThis: 'readonly',
        fetch: 'readonly',
        URLSearchParams: 'readonly',
        AbortSignal: 'readonly',
        AbortController: 'readonly',
      },
    },
    rules: {
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-undef': 'error',
      'no-shadow': 'warn',
      'no-control-regex': 'off',
      'no-useless-escape': 'warn',
      'no-useless-assignment': 'warn',
    },
  },
  {
    files: ['tests/**/*.js'],
    languageOptions: {
      globals: {
        global: 'writable',
        Response: 'readonly',
        Headers: 'readonly',
        TextDecoder: 'readonly',
      },
    },
  },
  {
    ignores: ['output/**', 'research/**', 'node_modules/**', '.codex/**', 'src/scaffolder/templates/**'],
  },
];
