import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchAIStatus, fetchRecommendNotes } from "../api/client"
import type { AIRecommendNotes, AIStatus, Attraction, Recommendation } from "../types"
import RecommendationGrid from "./RecommendationGrid"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchAIStatus: vi.fn(), fetchRecommendNotes: vi.fn() }
})

const mockedStatus = vi.mocked(fetchAIStatus)
const mockedNotes = vi.mocked(fetchRecommendNotes)

const available: AIStatus = {
  available: true,
  provider: "ollama",
  model: "qwen2.5:7b-instruct",
  disclaimer: "结果全部来自本站景点档案, AI 只参与理解你这句需求。",
}

const attraction = (slug: string, name: string): Attraction => ({
  id: 1,
  slug,
  name,
  name_en: null,
  summary: "一句话简介",
  category: { slug: "nature", name: "自然风光" },
  city: "杭州",
  province: "浙江",
  tags: [],
  cover_image: null,
  rating_avg: 4.6,
  rating_count: 120,
  ticket_price: 0,
  suggested_hours: 4,
  country_code: "CN",
  a_level: "5A",
  heritage: null,
})

const recommendation = (slug: string, name: string, reason: string): Recommendation => ({
  attraction: attraction(slug, name),
  rank: 1,
  score: 0.9,
  algo: "content-based",
  reason,
})

const items = [
  recommendation("west-lake", "西湖", "和你刚看过的灵隐寺同属自然风光。"),
  recommendation("palace", "故宫", "评分很高的热门景点。"),
]

const notes = (overrides: Partial<AIRecommendNotes> = {}): AIRecommendNotes => ({
  polished: true,
  degraded: false,
  model: "qwen2.5:7b-instruct",
  note: "",
  reasons: [
    { slug: "west-lake", note: "和你刚看的灵隐寺是一类风景。" },
    { slug: "palace", note: "评分高, 很多人在看。" },
  ],
  dropped: [],
  disclaimer: "推荐结果由本站的推荐算法给出, AI 只负责把理由写得更顺, 不参与挑选。",
  ...overrides,
})

const renderGrid = (list = items) =>
  render(
    <MemoryRouter>
      <RecommendationGrid items={list} />
    </MemoryRouter>,
  )

beforeEach(() => {
  mockedStatus.mockReset()
  mockedNotes.mockReset()
})

describe("RecommendationGrid", () => {
  it("模型不可用时直接用后端的理由, 也不发润色请求", async () => {
    mockedStatus.mockResolvedValue({ available: false, provider: "none", model: null, disclaimer: "" })
    renderGrid()

    expect(await screen.findByText(items[0].reason)).toBeInTheDocument()
    expect(mockedNotes).not.toHaveBeenCalled()
    expect(screen.queryByText("AI 润色")).not.toBeInTheDocument()
  })

  it("润色成功时换成新文案, 并标出 AI 润色与免责声明", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedNotes.mockResolvedValue(notes())
    renderGrid()

    expect(await screen.findByText("和你刚看的灵隐寺是一类风景。")).toBeInTheDocument()
    expect(screen.queryByText(items[0].reason)).not.toBeInTheDocument()
    expect(screen.getByText("AI 润色")).toBeInTheDocument()
    expect(screen.getByText(notes().disclaimer)).toBeInTheDocument()
  })

  it("只润色了一部分时, 没润色的那条仍是原来的理由", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedNotes.mockResolvedValue(
      notes({ reasons: [{ slug: "west-lake", note: "和你刚看的灵隐寺是一类风景。" }] }),
    )
    renderGrid()

    expect(await screen.findByText("和你刚看的灵隐寺是一类风景。")).toBeInTheDocument()
    expect(screen.getByText(items[1].reason)).toBeInTheDocument()
  })

  it("降级时用后端兜底的理由, 并说明这次没润色", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedNotes.mockResolvedValue(
      notes({
        polished: false,
        degraded: true,
        model: null,
        note: "未配置模型, 沿用原来的推荐理由。",
        reasons: [{ slug: "west-lake", note: items[0].reason }],
      }),
    )
    renderGrid()

    expect(await screen.findByText("未配置模型, 沿用原来的推荐理由。")).toBeInTheDocument()
    expect(screen.getByText(items[0].reason)).toBeInTheDocument()
    expect(screen.queryByText("AI 润色")).not.toBeInTheDocument()
  })

  it("润色接口报错也不影响推荐本身", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedNotes.mockRejectedValue(new Error("连不上后端"))
    renderGrid()

    expect(await screen.findByText(items[0].reason)).toBeInTheDocument()
    expect(screen.getByText(items[1].reason)).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("按列表长度请求, 并在状态回来后发起", async () => {
    mockedStatus.mockResolvedValue(available)
    mockedNotes.mockResolvedValue(notes())
    renderGrid()

    await waitFor(() => expect(mockedNotes).toHaveBeenCalledWith(2))
  })
})
