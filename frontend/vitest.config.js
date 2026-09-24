import { defineConfig, mergeConfig } from "vitest/config"

import viteConfig from "./vite.config.js"

// 单独一份配置: 测试要 jsdom 与 setup 文件, 这些不该塞进 vite.config.js。
// mergeConfig 复用 vite.config.js 的 plugins / 别名 / esbuild 设置。
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      include: ["src/**/*.{test,spec}.{ts,tsx}"],
      setupFiles: ["./src/setupTests.ts"],
      // 每个用例都从干净的 mock 开始, 免得跨用例串味
      restoreMocks: true,
    },
  }),
)