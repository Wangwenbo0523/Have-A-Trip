import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

// 没开 globals, 所以要手工登记清理 —— 否则多个 render 会互相污染 DOM
afterEach(() => {
  cleanup()
})