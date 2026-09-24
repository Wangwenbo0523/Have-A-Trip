import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchAIStatus, searchByAI } from "../api/client"
import type { AISearchResult, AIStatus, Attraction } from "../types"
import AiSearchPanel from "./AiSearchPanel"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchAIStatus: vi.fn(), searchByAI: vi.fn() }
})

const mockedStatus = vi.mocked(fetchAIStatus)
const mockedSearch = vi.mocked(searchByAI)

const available: AIStatus = {
  available: true,
  provider: "ollama",
  model: "qwen2.5:7b-instruct",
  disclaimer: "结果全部来自本站景点档案, AI 只参与理解你这句需求。",
}

const unavailable: AIStatus = { available: false, provider: "none", model: null, disclaimer: "" }

const item: Attraction = {
  id: 9,
  slug: "lingyin-temple",
  name: "灵隐寺",
  name_en: "Lingyin Temple",
  summary: "杭州最早的佛教寺院之一",
  category: { slug: "history", name: "历史古迹" },
  city: "杭州市",
  province: "浙江省",
  tags: [],
  cover_image: null,
  rating_avg: 0,
  rating_count: 0,
  ticket_price: null,
  suggested_hours: null,
  country_code: "CN",
  a_level: null,
  heritage: null,
}

const result = (overrides: Partial<AISearchResult> = {}): AISearchResult => ({
  query: "杭州的古迹",
  interpreted: true,
  degraded: false,
  model: "qwen2.5:7b-instruct",
  note: "已按你的描述筛选。",
  filters: { category: "history", tag: null, grade: null, city: "杭州市", q: null, sort: "rating" },
  items: [item],
  page: 1,
  size: 20,
  total: 1,
  relaxed: [],
  semantic_fallback: false,
  disclaimer: available.disclaimer,
  ...overrides,
})

const renderPanel = (onActiveChange?: (active: boolean) => void) =>
  render(
    <MemoryRouter>
      <AiSearchPanel onActiveChange={onActiveChange} />
    </MemoryRouter>,
  )

const submit = async (text: string) => {
  await userEvent.type(screen.getByRole("searchbox"), text)
  await userEvent.click(screen.getByRole("button", { name: "找一下" }))
}

beforeEach(() => {
  mockedStatus.mockReset()
  mockedSearch.mockReset()
})

describe("AiSearchPanel", () => {
  it("后端说不可用时, 整个入口不渲染", async () => {
    mockedStatus.mockResolvedValue(unavailable)
    renderPanel()
    await waitFor(() => expect(mockedStatus).toHaveBeenCalled())
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument()
    expect(screen.queryByText("用一句话找景点")).not.toBeInTheDocument()
  })

  it("状态接口失败也当作不可用, 不给点了没反应的按钮", async () => {
    mockedStatus.mockRejectedValue(new Error("连不上后端"))
    renderPanel()
    await waitFor(() => expect(mockedStatus).toHaveBeenCalled())
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument()
  })

  it("可用时渲染入口, 提交后显示结果与免责声明", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedSearch.mockResolvedValue(result())
    renderPanel()

    await screen.findByRole("searchbox")
    await submit("杭州的古迹")

    expect(mockedSearch).toHaveBeenCalledWith("杭州的古迹")
    expect(await screen.findByRole("heading", { name: "灵隐寺" })).toBeInTheDocument()
    expect(screen.getByText("已按你的描述筛选。")).toBeInTheDocument()
    expect(screen.getByText(available.disclaimer)).toBeInTheDocument()
  })

  it("降级时仍然当正常结果处理, 并把说明显示出来", async () => {
    // 后端未配置模型时会返回 200 + degraded=true, 这是降级不是错误
    mockedStatus.mockResolvedValue(available)
    mockedSearch.mockResolvedValue(
      result({
        interpreted: false,
        degraded: true,
        model: null,
        note: "未配置模型, 已退回关键词检索。",
        filters: { category: null, tag: null, grade: null, city: null, q: "杭州的古迹", sort: "rating" },
      }),
    )
    renderPanel()

    await screen.findByRole("searchbox")
    await submit("杭州的古迹")

    expect(await screen.findByText("未配置模型, 已退回关键词检索。")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "灵隐寺" })).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("没有命中时给空态, 不是错误态", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedSearch.mockResolvedValue(result({ items: [], total: 0 }))
    renderPanel()

    await screen.findByRole("searchbox")
    await submit("不存在的地方")

    expect(await screen.findByText("没有匹配的景点")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("请求失败显示错误态", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedSearch.mockRejectedValue(new Error("连不上后端"))
    renderPanel()

    await screen.findByRole("searchbox")
    await submit("杭州的古迹")

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent("AI 检索失败")
    expect(alert).toHaveTextContent("连不上后端")
  })

  it("有结果时通知父组件, 清除后通知收回", async () => {
    const onActiveChange = vi.fn()
    mockedStatus.mockResolvedValue(available)
    mockedSearch.mockResolvedValue(result())
    renderPanel(onActiveChange)

    await screen.findByRole("searchbox")
    await submit("杭州的古迹")
    await waitFor(() => expect(onActiveChange).toHaveBeenLastCalledWith(true))

    await userEvent.click(screen.getByRole("button", { name: "清除" }))
    await waitFor(() => expect(onActiveChange).toHaveBeenLastCalledWith(false))
    expect(screen.queryByRole("heading", { name: "灵隐寺" })).not.toBeInTheDocument()
  })

  it("空输入不发起请求", async () => {
    mockedStatus.mockResolvedValue(available)
    renderPanel()
    const button = await screen.findByRole("button", { name: "找一下" })
    expect(button).toBeDisabled()
    expect(mockedSearch).not.toHaveBeenCalled()
  })
})