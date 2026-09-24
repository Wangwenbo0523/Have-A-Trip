import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchSources } from "../api/client"
import type { SourcesResponse } from "../types"
import Credits from "./Credits"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchSources: vi.fn() }
})

const mocked = vi.mocked(fetchSources)

/** 一期真实的样子: 50 条全自采 + MIT, 一张图都没有。 */
const payload = (over: Partial<SourcesResponse> = {}): SourcesResponse => ({
  sources: [
    {
      source: "Have-A-Trip 自采（公开事实信息）",
      license: "MIT",
      attraction_count: 50,
      province_count: 21,
      share_alike: false,
      modification: "not-applicable",
    },
  ],
  images: [],
  attraction_total: 50,
  image_total: 0,
  needs_attention: false,
  ...over,
})

beforeEach(() => {
  mocked.mockReset()
})

describe("Credits", () => {
  it("来源清单来自接口, 不写死在前端", async () => {
    mocked.mockResolvedValue(payload())
    render(<Credits />)

    const table = await screen.findByRole("table", { name: "共 50 条已发布景点" })
    const rows = within(table)
    expect(rows.getByRole("cell", { name: "Have-A-Trip 自采（公开事实信息）" })).toBeInTheDocument()
    expect(rows.getByRole("cell", { name: "MIT" })).toBeInTheDocument()
    expect(rows.getByRole("cell", { name: "50" })).toBeInTheDocument()
    expect(rows.getByRole("cell", { name: "21" })).toBeInTheDocument()
    expect(rows.getByText("无需标注")).toBeInTheDocument()
    expect(mocked).toHaveBeenCalledTimes(1)
  })

  it("一张图都没有时说明原因, 而不是给一张空表格", async () => {
    mocked.mockResolvedValue(payload())
    render(<Credits />)

    expect(await screen.findByText("目前一张配图都没有")).toBeInTheDocument()
    expect(screen.queryByRole("table", { name: /张图/ })).not.toBeInTheDocument()
  })

  it("有图片时按 (署名, 许可) 聚合显示", async () => {
    mocked.mockResolvedValue(
      payload({ images: [{ credit: "张三", license: "CC0 1.0", image_count: 3 }], image_total: 3 }),
    )
    render(<Credits />)

    const table = await screen.findByRole("table", { name: "共 3 张图" })
    expect(within(table).getByRole("cell", { name: "张三" })).toBeInTheDocument()
    expect(within(table).getByRole("cell", { name: "CC0 1.0" })).toBeInTheDocument()
  })

  it("share-alike 来源没登记修改状态时亮告警, 不含糊过去", async () => {
    mocked.mockResolvedValue(
      payload({
        sources: [
          {
            source: "OpenStreetMap",
            license: "ODbL 1.0",
            attraction_count: 4,
            province_count: 2,
            share_alike: true,
            modification: "unregistered",
          },
        ],
        attraction_total: 4,
        needs_attention: true,
      }),
    )
    render(<Credits />)

    expect(await screen.findByText("有 share-alike 来源没有登记修改状态")).toBeInTheDocument()
    expect(screen.getByText("未登记")).toBeInTheDocument()
  })

  it("接口挂掉时给错误态与重试, 代码与素材那一块照常显示", async () => {
    mocked.mockRejectedValue(new Error("连不上后端"))
    render(<Credits />)

    expect(await screen.findByText("来源清单加载失败")).toBeInTheDocument()
    expect(screen.getByText("连不上后端")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument()
    // 这一段是仓库里的文件, 不依赖接口, 所以离线也该看得到
    expect(
      screen.getByRole("link", { name: "前端基底 zero-to-mastery/travel-guide" }),
    ).toBeInTheDocument()
  })

  it("重试会真的再请求一次", async () => {
    mocked.mockRejectedValueOnce(new Error("连不上后端"))
    mocked.mockResolvedValueOnce(payload())
    render(<Credits />)

    await userEvent.click(await screen.findByRole("button", { name: "重试" }))
    expect(await screen.findByRole("table", { name: "共 50 条已发布景点" })).toBeInTheDocument()
    expect(mocked).toHaveBeenCalledTimes(2)
  })

  it("没有已发布景点时不编造一行", async () => {
    mocked.mockResolvedValue(payload({ sources: [], attraction_total: 0 }))
    render(<Credits />)

    expect(await screen.findByText("暂无已发布的景点数据")).toBeInTheDocument()
  })
})