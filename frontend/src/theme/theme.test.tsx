import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it } from "vitest"

import { THEME_STORAGE_KEY, ThemeProvider, detectTheme, useTheme } from "."

/** 只为了把 context 里的当前主题印出来, 免得断言去猜 DOM 结构。 */
const Current = () => {
  const { theme, toggle } = useTheme()
  return (
    <button type="button" onClick={toggle}>
      当前 {theme}
    </button>
  )
}

const renderProvider = () =>
  render(
    <ThemeProvider>
      <Current />
    </ThemeProvider>,
  )

beforeEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe("detectTheme", () => {
  it("存过的选择优先; 没存过时是浅色 —— 不嗅探系统偏好", () => {
    expect(detectTheme()).toBe("light")

    window.localStorage.setItem(THEME_STORAGE_KEY, "dark")
    expect(detectTheme()).toBe("dark")

    // 非法值(旧版本残留 / 手改过 localStorage)当没存过
    window.localStorage.setItem(THEME_STORAGE_KEY, "solarized")
    expect(detectTheme()).toBe("light")
  })
})

describe("ThemeProvider", () => {
  it("默认浅色, 并写到 <html data-theme> 与 localStorage", () => {
    renderProvider()

    expect(screen.getByRole("button", { name: "当前 light" })).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBe("light")
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light")
  })

  it("切换一次就落到 DOM 上, 不是只改了内存里的状态", async () => {
    renderProvider()

    await userEvent.click(screen.getByRole("button", { name: "当前 light" }))

    expect(screen.getByRole("button", { name: "当前 dark" })).toBeInTheDocument()
    // CSS 只认这一处开关(见 src/index.css), 所以它必须跟着变
    expect(document.documentElement.dataset.theme).toBe("dark")
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark")

    await userEvent.click(screen.getByRole("button", { name: "当前 dark" }))
    expect(document.documentElement.dataset.theme).toBe("light")
  })

  it("存过深色时下次进来还是深色", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark")
    renderProvider()
    expect(document.documentElement.dataset.theme).toBe("dark")
  })
})

describe("useTheme", () => {
  it("脱离 Provider 也能渲染, 退回浅色而不是抛异常", () => {
    render(<Current />)
    expect(screen.getByRole("button", { name: "当前 light" })).toBeInTheDocument()
  })
})