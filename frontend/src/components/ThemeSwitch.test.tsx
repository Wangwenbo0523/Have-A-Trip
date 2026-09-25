import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it } from "vitest"

import { THEME_STORAGE_KEY, ThemeProvider } from "../theme"
import ThemeSwitch from "./ThemeSwitch"

const renderSwitch = () =>
  render(
    <ThemeProvider>
      <ThemeSwitch />
    </ThemeProvider>,
  )

beforeEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe("ThemeSwitch", () => {
  it("浅色界面上写的是目标主题「深色」, 并把可读标签说清楚", () => {
    renderSwitch()
    const button = screen.getByRole("button", { name: "切换到深色主题" })
    expect(button).toHaveTextContent("深色")
  })

  it("点一下切到深色: 按钮变成「浅色」, data-theme 与 localStorage 都跟着变", async () => {
    renderSwitch()

    await userEvent.click(screen.getByRole("button", { name: "切换到深色主题" }))

    expect(screen.getByRole("button", { name: "切换到浅色主题" })).toHaveTextContent("浅色")
    expect(document.documentElement.dataset.theme).toBe("dark")
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark")
  })
})