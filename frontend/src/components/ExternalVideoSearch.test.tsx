import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import ExternalVideoSearch from "./ExternalVideoSearch"

describe("ExternalVideoSearch", () => {
  it("渲染站外搜索链接, 关键词做 URL 编码", () => {
    render(<ExternalVideoSearch keyword="西湖" />)
    const link = screen.getByRole("link", { name: "去哔哩哔哩搜「西湖」" })
    expect(link).toHaveAttribute(
      "href",
      `https://search.bilibili.com/all?keyword=${encodeURIComponent("西湖")}`,
    )
  })

  it("新窗口打开并切断 referrer", () => {
    render(<ExternalVideoSearch keyword="西湖" />)
    const link = screen.getByRole("link", { name: "去哔哩哔哩搜「西湖」" })
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noreferrer noopener")
  })

  it("明说是站外内容, 且不内嵌 iframe", () => {
    const { container } = render(<ExternalVideoSearch keyword="西湖" />)
    expect(screen.getByText(/站外搜索页/)).toBeInTheDocument()
    expect(container.querySelector("iframe")).toBeNull()
  })

  it("关键词只有空白时不渲染", () => {
    const { container } = render(<ExternalVideoSearch keyword="   " />)
    expect(container).toBeEmptyDOMElement()
  })
})
