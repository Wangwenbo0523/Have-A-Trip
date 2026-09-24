import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it } from "vitest"

import { LANG_STORAGE_KEY, LanguageProvider } from "../i18n"
import LanguageSwitch from "./LanguageSwitch"

const renderSwitch = (initial: "zh" | "en" = "zh") =>
  render(
    <LanguageProvider initial={initial}>
      <LanguageSwitch />
    </LanguageProvider>,
  )

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.lang = ""
})

describe("LanguageSwitch", () => {
  it("中文界面上写的是目标语言 EN, 并把可读标签说清楚", () => {
    renderSwitch("zh")
    const button = screen.getByRole("button", { name: "切换到英文" })
    expect(button).toHaveTextContent("EN")
    // lang 跟着按钮文字走, 屏幕阅读器才不会用错发音
    expect(button).toHaveAttribute("lang", "en")
  })

  it("英文界面上写的是 中文", () => {
    renderSwitch("en")
    const button = screen.getByRole("button", { name: "切换到中文" })
    expect(button).toHaveTextContent("中文")
    expect(button).toHaveAttribute("lang", "zh-CN")
  })

  it("点一下切换语种, 并把选择写进 localStorage 与 <html lang>", async () => {
    renderSwitch("zh")
    await userEvent.click(screen.getByRole("button", { name: "切换到英文" }))

    expect(screen.getByRole("button", { name: "切换到中文" })).toBeInTheDocument()
    expect(window.localStorage.getItem(LANG_STORAGE_KEY)).toBe("en")
    expect(document.documentElement.lang).toBe("en")
  })
})
