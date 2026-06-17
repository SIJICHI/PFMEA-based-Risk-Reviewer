import { defineConfig } from 'i18next-cli';

export default defineConfig({
  locales: ['es-419', 'fr', 'ja', 'ko', 'pt-BR'],
  extract: {
    input: 'src/**/!(*.test).{js,jsx,ts,tsx}',
    output: './src/lib/i18n/locales/{{language}}.json',
    defaultNS: false,
    keySeparator: false,
    nsSeparator: false,
    functions: ['t', '*.t'],
    defaultValue: '',
  },
});
