import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { viteExternalsPlugin } from 'vite-plugin-externals';

const externalLibs: Record<string, string> = {
  react: 'React',
  'react-dom': 'ReactDOM',
  ReactDom: 'ReactDOM',
  '@mantine/core': 'MantineCore',
  '@mantine/notifications': 'MantineNotifications'
};

const externalKeys = Object.keys(externalLibs);

export default defineConfig({
  plugins: [
    react({ jsxRuntime: 'classic' }),
    viteExternalsPlugin(externalLibs)
  ],
  esbuild: { jsx: 'preserve' },
  build: {
    target: 'esnext',
    cssCodeSplit: false,
    manifest: true,
    sourcemap: true,
    rollupOptions: {
      preserveEntrySignatures: 'exports-only',
      input: ['./src/Panel.tsx'],
      output: [
        {
          dir: '../inventree_customer_pricing/static',
          entryFileNames: '[name].js',
          assetFileNames: 'assets/[name].[ext]',
          globals: externalLibs
        },
        {
          dir: '../inventree_customer_pricing/static',
          entryFileNames: '[name]-[hash].js',
          assetFileNames: 'assets/[name].[ext]',
          globals: externalLibs
        }
      ],
      external: externalKeys
    }
  },
  optimizeDeps: { exclude: externalKeys }
});
