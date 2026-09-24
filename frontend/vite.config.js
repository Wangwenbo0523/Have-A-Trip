import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 后端地址: 默认本机 8000。scripts/dev-up.ps1 换端口(-BackendPort)时会把这个值
// 通过进程环境变量 DEV_API_PROXY 传进来; 手动改端口也能用同一个变量覆盖。
// 注意它走的是进程环境变量, 不是 .env —— Vite 不会把 .env 灌进 config 的 process.env。
const apiTarget = process.env.DEV_API_PROXY || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],

  // 上游是 GitHub Pages 部署, base 写的 '/travel-guide/'。本项目独立部署, 用根路径。
  // 若将来部署到 GitHub Pages 的子路径(如 /Have-A-Trip/), 改回该路径。
  base: '/',

  server: {
    // 前端默认请求同源的 /api/v1, 由这里转发到本机 FastAPI。
    // 这样本地开发不需要配跨域, 也不用写 .env.local。
    // 前后端分开部署时用 VITE_API_BASE 指到真实地址(见 .env.example)。
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },

  // 上游基底里混着写 JSX 的 .js 文件, 所以当年配了 esbuild.loader 兜底。
  // S4 之后 src/ 下已经没有 .js/.jsx, 这两段是死配置; 而且 Vite 8 改用
  // Rolldown/oxc 之后 optimizeDeps.esbuildOptions 已废弃, 留着只会每次构建
  // 打一行告警, 还会把 vite.config.js 自己的 esbuild 选项也一起忽略掉。

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
