import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchAttractions, fetchCategories, fetchRecommendations } from "./api/client"
import App from "./App"
import { LANG_STORAGE_KEY } from "./i18n"

vi.mock("./api/client", async () => {
  const actual = await vi.importActual<typeof import("./api/client")>("./api/client")
  return {
    ...actual,
    fetchCategories: vi.fn(),
    fetchAttractions: vi.fn(),
    fetchRecommendations: vi.fn(),
  }
})

const mockedCategories = vi.mocked(fetchCategories)
const mockedAttractions = vi.mocked(fetchAttractions)
const mockedRecommendations = vi.mocked(fetchRecommendations)

beforeEach(() => {
  mockedCategories.mockReset()
  mockedAttractions.mockReset()
  mockedRecommendations.mockReset()
  // 语种存在 localStorage 里, 清掉才不会让上一个用例的选择串到下一个
  window.localStorage.clear()
  // 首页会同时打这三个接口, 给一组空数据当默认值, 免得未 mock 的 promise 变成 undefined
  mockedAttractions.mockResolvedValue({ items: [], page: 1, size: 6, total: 0 })
  mockedRecommendations.mockResolvedValue([])
})

describe("App", () => {
  it("能挂载, 品牌名与导航都在", async () => {
    mockedCategories.mockResolvedValue([
      { slug: "nature", name: "自然风光", attraction_count: 2 },
    ])
    render(<App />)

    expect(await screen.findByText("Have-A-Trip")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "全部景点" })).toBeInTheDocument()
    // 分类来自接口, 所以导航是动态生成的
    expect(await screen.findByRole("link", { name: "自然风光" })).toBeInTheDocument()
  })

  it("分类接口挂掉时导航降级, 不白屏", async () => {
    mockedCategories.mockRejectedValue(new Error("连不上后端"))
    render(<App />)

    expect(await screen.findByText("Have-A-Trip")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "首页" })).toBeInTheDocument()
  })

  it("后端全挂时首页给出错误态而不是白屏", async () => {
    mockedCategories.mockRejectedValue(new Error("连不上后端"))
    mockedAttractions.mockRejectedValue(new Error("连不上后端"))
    mockedRecommendations.mockRejectedValue(new Error("连不上后端"))
    render(<App />)

    expect(await screen.findByText("推荐暂时拿不到")).toBeInTheDocument()
    expect(screen.getByText("最新收录加载失败")).toBeInTheDocument()
    expect(screen.getByText("分类还没加载出来")).toBeInTheDocument()
  })

  it("点页头右上角的按钮就能切换中英双语", async () => {
    mockedCategories.mockResolvedValue([
      { slug: "nature", name: "自然风光", attraction_count: 2 },
    ])
    render(<App />)

    // 默认中文
    expect(await screen.findByRole("link", { name: "全部景点" })).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "切换到英文" }))

    expect(screen.getByRole("link", { name: "All attractions" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument()
    // 分类名来自数据库, 是内容不是文案: 英文界面下仍然显示原名
    expect(screen.getByRole("link", { name: "自然风光" })).toBeInTheDocument()
    expect(window.localStorage.getItem(LANG_STORAGE_KEY)).toBe("en")

    // 再点一次切回中文, 按钮上写的是目标语言的名字
    await userEvent.click(screen.getByRole("button", { name: "切换到中文" }))
    expect(screen.getByRole("link", { name: "全部景点" })).toBeInTheDocument()
  })
})
