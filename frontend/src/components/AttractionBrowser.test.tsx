import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchAIStatus, fetchAttractions, searchByAI } from "../api/client"
import type { AISearchResult, AIStatus, Attraction } from "../types"
import AttractionBrowser from "./AttractionBrowser"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchAttractions: vi.fn(), fetchAIStatus: vi.fn(), searchByAI: vi.fn() }
})

const mockedFetch = vi.mocked(fetchAttractions)
const mockedAIStatus = vi.mocked(fetchAIStatus)
const mockedAISearch = vi.mocked(searchByAI)

/** 默认配置下后端说 AI 不可用, 面板整个不渲染 —— 多数用例按这个来。 */
const aiOff: AIStatus = { available: false, provider: "none", model: null, disclaimer: "" }

const item: Attraction = {
  id: 1,
  slug: "west-lake",
  name: "西湖",
  name_en: "West Lake",
  summary: "三面云山一面城的淡水湖。",
  category: { slug: "nature", name: "自然风光" },
  city: "杭州",
  province: "浙江",
  tags: [],
  cover_image: null,
  rating_avg: 4.7,
  rating_count: 128,
  ticket_price: 0,
  suggested_hours: 4,
  country_code: "CN",
  a_level: null,
  heritage: null,
}

const page = (items: Attraction[], total = items.length) => ({
  items,
  page: 1,
  size: 12,
  total,
})

const renderBrowser = (props: { category?: string } = {}) =>
  render(
    <MemoryRouter>
      <AttractionBrowser {...props} />
    </MemoryRouter>,
  )

beforeEach(() => {
  mockedFetch.mockReset()
  mockedAIStatus.mockReset()
  mockedAISearch.mockReset()
  mockedAIStatus.mockResolvedValue(aiOff)
})

describe("AttractionBrowser", () => {
  it("拿到数据后渲染卡片与总数", async () => {
    mockedFetch.mockResolvedValue(page([item]))
    renderBrowser()
    expect(await screen.findByRole("heading", { name: "西湖" })).toBeInTheDocument()
    expect(screen.getByText(/共 1 个景点/)).toBeInTheDocument()
  })

  it("分类筛选会带进请求参数", async () => {
    mockedFetch.mockResolvedValue(page([item]))
    renderBrowser({ category: "nature" })
    await screen.findByRole("heading", { name: "西湖" })
    expect(mockedFetch).toHaveBeenCalledWith(
      expect.objectContaining({ category: "nature", page: 1 }),
    )
  })

  it("空结果给的是空态, 不是错误态", async () => {
    mockedFetch.mockResolvedValue(page([]))
    renderBrowser()
    expect(await screen.findByText("没有匹配的景点")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("请求失败显示错误态, 点重试会重新请求", async () => {
    mockedFetch.mockRejectedValueOnce(new Error("连不上后端"))
    mockedFetch.mockResolvedValueOnce(page([item]))
    renderBrowser()

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent("景点加载失败")
    expect(alert).toHaveTextContent("连不上后端")

    await userEvent.click(screen.getByRole("button", { name: "重试" }))
    expect(await screen.findByRole("heading", { name: "西湖" })).toBeInTheDocument()
  })

  it("搜索会防抖, 打字过程中不发请求", async () => {
    mockedFetch.mockResolvedValue(page([item]))
    renderBrowser()
    await screen.findByRole("heading", { name: "西湖" })
    mockedFetch.mockClear()

    await userEvent.type(screen.getByRole("searchbox"), "West")
    // 防抖 300ms, 输入阶段不应该触发请求
    expect(mockedFetch).not.toHaveBeenCalled()

    await waitFor(
      () => {
        expect(mockedFetch).toHaveBeenCalledWith(expect.objectContaining({ q: "West" }))
      },
      { timeout: 2000 },
    )
  })

  it("等级筛选会带进请求参数, 并回到第一页", async () => {
    mockedFetch.mockResolvedValue(page([item]))
    renderBrowser()
    await screen.findByRole("heading", { name: "西湖" })

    await userEvent.click(screen.getByRole("button", { name: "世界遗产" }))
    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith(
        expect.objectContaining({ grade: "heritage", page: 1 }),
      )
    })

    // 选回「全部」时不带 grade 参数
    await userEvent.click(screen.getByRole("button", { name: "全部" }))
    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith(
        expect.objectContaining({ grade: undefined }),
      )
    })
  })

  it("等级下没有景点时给的是筛选空态, 不是「去跑种子脚本」", async () => {
    mockedFetch.mockResolvedValue(page([item]))
    renderBrowser()
    await screen.findByRole("heading", { name: "西湖" })

    mockedFetch.mockResolvedValue(page([]))
    await userEvent.click(screen.getByRole("button", { name: "3A" }))
    expect(await screen.findByText("这个等级下暂时还没有已发布的景点")).toBeInTheDocument()
  })

  it("多页时翻页按钮按边界禁用", async () => {
    mockedFetch.mockResolvedValue(page([item], 30))
    renderBrowser()
    await screen.findByRole("heading", { name: "西湖" })
    expect(screen.getByRole("button", { name: "上一页" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "下一页" })).toBeEnabled()
    expect(screen.getByText(/第 1 \/ 3 页/)).toBeInTheDocument()
  })

  it("AI 可用且出了结果时, 普通检索那条列表收起来", async () => {
    const disclaimer = "结果全部来自本站景点档案, AI 只参与理解你这句需求。"
    mockedAIStatus.mockResolvedValue({
      available: true,
      provider: "ollama",
      model: "qwen2.5:7b-instruct",
      disclaimer,
    })
    const aiResult: AISearchResult = {
      query: "杭州的古迹",
      interpreted: true,
      degraded: false,
      model: "qwen2.5:7b-instruct",
      note: "已按你的描述筛选。",
      filters: { category: "history", tag: null, grade: null, city: "杭州市", q: null, sort: "rating" },
      items: [{ ...item, id: 2, slug: "lingyin-temple", name: "灵隐寺" }],
      page: 1,
      size: 20,
      total: 1,
      disclaimer,
    }
    mockedAISearch.mockResolvedValue(aiResult)
    mockedFetch.mockResolvedValue(page([item]))
    renderBrowser()

    await screen.findByRole("heading", { name: "西湖" })
    // 面板的输入与普通搜索框都是 searchbox, 用 label 区分
    await userEvent.type(screen.getByLabelText("用一句话找景点"), "杭州的古迹")
    await userEvent.click(screen.getByRole("button", { name: "找一下" }))

    expect(await screen.findByRole("heading", { name: "灵隐寺" })).toBeInTheDocument()
    // 普通检索那条列表与它那套筛选按钮都收起来了, 不会两份列表同时出现
    expect(screen.queryByRole("heading", { name: "西湖" })).not.toBeInTheDocument()
    expect(screen.queryByRole("group", { name: "等级筛选" })).not.toBeInTheDocument()
  })
})