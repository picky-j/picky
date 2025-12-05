import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { crx } from '@crxjs/vite-plugin';
import manifest from './src/manifest.js';

export default defineConfig({
  plugins: [
    react(),
    crx({ manifest }),
  ],
  build: {
    sourcemap: true,
    minify: 'terser',
    terserOptions: {
      // console.log 제거
      compress: {
        drop_console: false,
      },
      // 주석 제거
      format: {
        comments: false,
      },
      keep_classnames: true,
      keep_fnames: true,
    },
    rollupOptions: {
      input: {
        // content script에 주입될 CSS를 별도 빌드 결과물로 지정
        content: 'src/content.css',
      },
      output: {
        // content.css 결과물이 dist 폴더 바로 아래에 생성되도록 설정
        assetFileNames: (assetInfo) => {
          return assetInfo.name === 'content.css' ? 'content.css' : '[name]-[hash][extname]';
        },
      },
    },
  },
});
