import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  // 上游是 GitHub Pages 部署, base 写的 '/travel-guide/'。本项目独立部署, 用根路径。
  // 若将来部署到 GitHub Pages 的子路径(如 /Have-A-Trip/), 改回该路径。
  base: '/',

  esbuild: {
    loader: 'tsx',
    include: /src\/.*\.[jt]sx?$/,
  },

  optimizeDeps: {
    esbuildOptions: {
      loader: {
        '.js': 'jsx',
        '.ts': 'tsx',
        '.tsx': 'tsx',
      },
    },
  },

  css: {
    lightningcss: {
      // tachyons@4.12(上游基座用的工具类库, 2017 年的版本)里含 IE 时代的
      // `*zoom` 星号 hack。Vite 8 默认的 LightningCSS 压缩器把它当非法语法,
      // 直接让构建失败。errorRecovery 会剥离这类无效声明。
      // 该 hack 只对 IE7 有意义, 现代浏览器本来就忽略, 剥离无副作用。
      // TODO: 重写前端时移除 tachyons, 即可关掉这个开关。
      errorRecovery: true,
    },
  },
})