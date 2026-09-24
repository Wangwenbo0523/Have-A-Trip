import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { createItinerary, fetchItinerary, itineraryRejection } from "../api/client"
import type { Itinerary, ItineraryAccepted } from "../types"
import ItineraryPlanner from "./ItineraryPlanner"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return {
    ...actual,
    createItinerary: vi.fn(),
    fetchItinerary: vi.fn(),
    itineraryRejection: vi.fn(() => null),
  }
})

const mockedCreate = vi.mocked(createItinerary)
const mockedFetch = vi.mocked(fetchItinerary)
const mockedRejection = vi.mocked(itineraryRejection)

const ACCEPTED: ItineraryAccepted = { token: "itn_test", status: "pending" }

const itinerary = (overrides: Partial<Itinerary> = {}): Itinerary => ({
  token: "itn_test",
  status: "succeeded",
  days: 2,
  items: [
    { day_index: 1, seq: 1, attraction_id: 9, name: "灵隐寺", note: "上午出发", reason: "不爬山" },
    { day_index: 2, seq: 1, attraction_id: 3, name: "西湖", note: "慢慢逛", reason: "符合你的节奏" },
  ],
  error: null,
  note: null,
  model: "qwen2.5:7b-instruct",
  usage: { prompt_tokens: 100, completion_tokens: 50 },
  generated_at: "2026-09-25T10:00:00+08:00",
  created_at: "2026-09-25T09:59:00+08:00",
  max_poll_seconds: 90,
  disclaimer: "行程由 AI 按本站景点档案编排, 出行前请核实开放时间与票价。",
  ...overrides,
})

const renderPlanner = () =>
  render(
    <MemoryRouter>
      <ItineraryPlanner />
    </MemoryRouter>,
  )

const submit = async (text = "带小孩去杭州玩两天, 不想爬山") => {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText("说说你想怎么玩"), text)
  await user.click(screen.getByRole("button", { name: "帮我排一下" }))
}

describe("ItineraryPlanner", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedRejection.mockReturnValue(null)
  })

  it("把生成结果按天分组显示", async () => {
    mockedCreate.mockResolvedValue(ACCEPTED)
    mockedFetch.mockResolvedValue(itinerary())
    renderPlanner()

    await submit()

    await waitFor(() => expect(screen.getByText("第 1 天")).toBeInTheDocument())
    expect(screen.getByText("第 2 天")).toBeInTheDocument()
    expect(screen.getByText("灵隐寺")).toBeInTheDocument()
    expect(screen.getByText("上午出发")).toBeInTheDocument()
    expect(screen.getByText("不爬山")).toBeInTheDocument()
    expect(screen.getByText(itinerary().disclaimer)).toBeInTheDocument()
  })

  it("景点名链到详情页, 用 attraction_id 而不是 slug", async () => {
    mockedCreate.mockResolvedValue(ACCEPTED)
    mockedFetch.mockResolvedValue(itinerary())
    renderPlanner()

    await submit()

    await waitFor(() => expect(screen.getByText("灵隐寺")).toBeInTheDocument())
    expect(screen.getByText("灵隐寺").closest("a")).toHaveAttribute("href", "/attraction/9")
  })

  it("生成中会继续轮询, 直到拿到终态", async () => {
    mockedCreate.mockResolvedValue(ACCEPTED)
    mockedFetch
      .mockResolvedValueOnce(itinerary({ status: "pending", items: [] }))
      .mockResolvedValueOnce(itinerary())
    renderPlanner()

    await submit()

    await waitFor(() => expect(screen.getByText("第 1 天")).toBeInTheDocument(), { timeout: 5000 })
    expect(mockedFetch.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it("失败时显示后端给的可读原因, 不是报错页", async () => {
    mockedCreate.mockResolvedValue(ACCEPTED)
    mockedFetch.mockResolvedValue(itinerary({ status: "failed", error: "模型返回了 0 条行程", items: [] }))
    renderPlanner()

    await submit()

    await waitFor(() => expect(screen.getByText("这次没排出来")).toBeInTheDocument())
    expect(screen.getByText("模型返回了 0 条行程")).toBeInTheDocument()
  })

  it("被限额拦下时告诉用户什么时候能再来", async () => {
    mockedCreate.mockRejectedValue(new Error("429"))
    mockedRejection.mockReturnValue({
      status: "rejected",
      reason: "daily_limit_exceeded",
      retry_after: "2026-09-26T00:00:00+08:00",
      limit: 5,
    })
    renderPlanner()

    await submit()

    await waitFor(() => expect(screen.getByText("今天排得够多了")).toBeInTheDocument())
    expect(screen.getByText(/每天最多 5 次/)).toBeInTheDocument()
  })

  it("没有终态时不显示结果区", async () => {
    mockedCreate.mockResolvedValue(ACCEPTED)
    mockedFetch.mockResolvedValue(itinerary({ status: "generating", items: [] }))
    renderPlanner()

    await submit()

    await waitFor(() => expect(mockedCreate).toHaveBeenCalled())
    expect(screen.queryByText("第 1 天")).not.toBeInTheDocument()
  })

  it("排好之后给一个打印行程单的入口, 并说明打印会去掉哪些东西", async () => {
    mockedCreate.mockResolvedValue(ACCEPTED)
    mockedFetch.mockResolvedValue(itinerary())
    renderPlanner()

    await submit()

    await waitFor(() => expect(screen.getByText("第 1 天")).toBeInTheDocument())
    expect(screen.getByRole("button", { name: "打印行程单" })).toBeInTheDocument()
    expect(screen.getByText("打印时自动去掉页头、页脚与表单, 只留行程正文")).toBeInTheDocument()
  })
})
