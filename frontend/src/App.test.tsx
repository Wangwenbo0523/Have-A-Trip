import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchAttractions, fetchCategories, fetchRecommendations } from "./api/client"
import App from "./App"

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
    expect(screen.getByText("景点加载失败")).toBeInTheDocument()
    expect(screen.getByText("分类还没加载出来")).toBeInTheDocument()
  })
})