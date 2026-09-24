import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchStats } from "../api/client"
import type { StatsResponse } from "../types"
import StatsPage from "./StatsPage"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchStats: vi.fn() }
})

const mocked = vi.mocked(fetchStats)

/** 一份真实形状的响应: 分类名与许可都是内容, 取值是机器码。 */
const payload = (over: Partial<StatsResponse> = {}): StatsResponse => ({
  attraction_total: 5,
  image_total: 3,
  plan_total: 2,
  province_total: 4,
  by_country: [
    { key: "CN", label: "CN", count: 4 },
    { key: "JP", label: "JP", count: 1 },
  ],
  by_category: [
    { key: "history", label: "历史古迹", count: 3 },
    { key: "nature", label: "自然风光", count: 2 },
  ],
  by_a_level: [
    { key: "5A", label: "5A", count: 2 },
    { key: "unknown", label: "unknown", count: 3 },
  ],
  by_heritage: [
    { key: "cultural", label: "cultural", count: 1 },
    { key: "unknown", label: "unknown", count: 4 },
  ],
  sources: [
    {
      source: "Have-A-Trip 自采（公开事实信息）",
      license: "MIT",
      attraction_count: 5,
      province_count: 4,
      share_alike: false,
      modification: "not-applicable",
    },
  ],
  needs_attention: false,
  ...over,
})

const renderPage = () =>
  render(
    <MemoryRouter>
      <StatsPage />
    </MemoryRouter>,
  )

beforeEach(() => {
  mocked.mockReset()
})

describe("StatsPage", () => {
  it("总数与分布都来自接口, 前端不写死", async () => {
    mocked.mockResolvedValue(payload())
    renderPage()

    const kpis = await screen.findByText("已发布景点")
    expect(kpis.closest("li")).toHaveTextContent("5")
    expect(screen.getByText("配图").closest("li")).toHaveTextContent("3")
    expect(screen.getByText("旅游方案").closest("li")).toHaveTextContent("2")
    expect(screen.getByText("覆盖省级行政区").closest("li")).toHaveTextContent("4")
    expect(mocked).toHaveBeenCalledTimes(1)
  })

  it("分类名按库里的原名显示, 等级与遗产取值翻成人话", async () => {
    mocked.mockResolvedValue(payload())
    renderPage()

    // 分类名是内容, 不翻译
    expect(await screen.findByText("历史古迹")).toBeInTheDocument()
    expect(screen.getByText("自然风光")).toBeInTheDocument()
    // A 级是国家标准里的固定写法, 原样显示
    expect(screen.getByText("5A")).toBeInTheDocument()
    // cultural 是机器取值, 必须翻成「世界文化遗产」
    expect(screen.getByText("世界文化遗产")).toBeInTheDocument()
  })

  it("档案里没填的取值显示成「未核实」而不是被丢掉", async () => {
    mocked.mockResolvedValue(payload())
    renderPage()

    await screen.findByText("景区质量等级")
    const aLevel = screen.getByRole("heading", { name: "景区质量等级" }).closest("section")
    const heritage = screen.getByRole("heading", { name: "世界遗产" }).closest("section")

    // unknown 是「未核实」, 不是「没有等级」, 而且必须留在分布里
    expect(within(aLevel as HTMLElement).getByText("未核实")).toBeInTheDocument()
    expect(within(heritage as HTMLElement).getByText("未核实")).toBeInTheDocument()
    // 各档之和等于总数: A 级 2 + 未核实 3 = 5, 没有景点在图上凭空消失
    expect(within(aLevel as HTMLElement).getByText("2 个")).toBeInTheDocument()
    expect(within(aLevel as HTMLElement).getByText("3 个")).toBeInTheDocument()
  })

  it("境内与境外由 country_code 分出来, 不看国名", async () => {
    mocked.mockResolvedValue(payload())
    renderPage()

    expect(await screen.findByText("境内")).toBeInTheDocument()
    expect(screen.getByText("境外")).toBeInTheDocument()
    expect(screen.getByText("境内 4 个 · 境外 1 个, 按 country_code 分组")).toBeInTheDocument()
  })

  it("来源分布复用声明页的聚合, share-alike 的行单独标出来", async () => {
    mocked.mockResolvedValue(payload())
    renderPage()

    const table = await screen.findByRole("table", { name: "共 5 个已发布景点, 来自 1 个来源" })
    expect(
      within(table).getByRole("cell", { name: "Have-A-Trip 自采（公开事实信息）" }),
    ).toBeInTheDocument()
    expect(within(table).getByRole("cell", { name: "MIT" })).toBeInTheDocument()
    expect(screen.queryByText("相同方式共享")).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: "数据来源与许可" })).toHaveAttribute(
      "href",
      "/credits",
    )
  })

  it("share-alike 来源没登记修改状态时, 看板也亮告警", async () => {
    mocked.mockResolvedValue(
      payload({
        needs_attention: true,
        sources: [
          {
            source: "OpenStreetMap",
            license: "ODbL 1.0",
            attraction_count: 5,
            province_count: 4,
            share_alike: true,
            modification: "unregistered",
          },
        ],
      }),
    )
    renderPage()

    expect(
      await screen.findByText("有 share-alike 来源还没登记修改状态"),
    ).toBeInTheDocument()
    expect(screen.getByText("相同方式共享")).toBeInTheDocument()
  })

  it("一条已发布景点都没有时说明原因, 不画一排空条", async () => {
    mocked.mockResolvedValue(
      payload({
        attraction_total: 0,
        province_total: 0,
        by_country: [],
        by_category: [],
        by_a_level: [],
        by_heritage: [],
        sources: [],
        image_total: 0,
        plan_total: 0,
      }),
    )
    renderPage()

    expect(await screen.findByText("库里还没有已发布的景点")).toBeInTheDocument()
    expect(screen.queryByText("5A")).not.toBeInTheDocument()
  })

  it("接口挂掉时给错误态, 重试会真的再请求一次", async () => {
    mocked.mockRejectedValueOnce(new Error("连不上后端"))
    mocked.mockResolvedValueOnce(payload())
    renderPage()

    expect(await screen.findByText("看板加载失败")).toBeInTheDocument()
    expect(screen.getByText("连不上后端")).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "重试" }))
    expect(await screen.findByText("已发布景点")).toBeInTheDocument()
    expect(mocked).toHaveBeenCalledTimes(2)
  })
})
