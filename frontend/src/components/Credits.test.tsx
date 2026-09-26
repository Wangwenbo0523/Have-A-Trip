import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchSources } from "../api/client"
import type { ImageAttribution, SourcesResponse } from "../types"
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
  attributions: [],
  attraction_total: 50,
  image_total: 0,
  needs_attention: false,
  ...over,
})

/** Credits 里有站内链接(景点详情页), 所以渲染时要套一个路由。 */
const renderCredits = () =>
  render(
    <MemoryRouter>
      <Credits />
    </MemoryRouter>,
  )

/** 一条逐图署名: 实拍照片那一类, 带来源页与 CC BY-SA 许可。 */
const attribution = (over: Partial<ImageAttribution> = {}): ImageAttribution => ({
  attraction_slug: "west-lake",
  attraction_name: "西湖",
  url: "/images/covers/west-lake.jpg",
  caption: "#001 · 西湖.jpg",
  credit: "Black Dragon Society",
  license: "CC BY-SA 4.0",
  license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
  source_url: "https://commons.wikimedia.org/wiki/File:West_Lake.jpg",
  modification: "modified",
  ...over,
})

beforeEach(() => {
  mocked.mockReset()
})

describe("Credits", () => {
  it("来源清单来自接口, 不写死在前端", async () => {
    mocked.mockResolvedValue(payload())
    renderCredits()

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
    renderCredits()

    expect(await screen.findByText("目前一张配图都没有")).toBeInTheDocument()
    expect(screen.queryByRole("table", { name: /张图/ })).not.toBeInTheDocument()
  })

  it("有图片时按 (署名, 许可) 聚合显示", async () => {
    mocked.mockResolvedValue(
      payload({
        images: [
          {
            credit: "张三",
            license: "CC0 1.0",
            license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
            image_count: 3,
          },
        ],
        image_total: 3,
      }),
    )
    renderCredits()

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
    renderCredits()

    expect(await screen.findByText("有 share-alike 来源没有登记修改状态")).toBeInTheDocument()
    expect(screen.getByText("未登记")).toBeInTheDocument()
  })

  it("接口挂掉时给错误态与重试, 代码与素材那一块照常显示", async () => {
    mocked.mockRejectedValue(new Error("连不上后端"))
    renderCredits()

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
    renderCredits()

    await userEvent.click(await screen.findByRole("button", { name: "重试" }))
    expect(await screen.findByRole("table", { name: "共 50 条已发布景点" })).toBeInTheDocument()
    expect(mocked).toHaveBeenCalledTimes(2)
  })

  it("没有已发布景点时不编造一行", async () => {
    mocked.mockResolvedValue(payload({ sources: [], attraction_total: 0 }))
    renderCredits()

    expect(await screen.findByText("暂无已发布的景点数据")).toBeInTheDocument()
  })

  it("有外部来源的图逐张署名: 缩略图 / 景点 / 署名 / 许可 / 来源页 / 修改状态", async () => {
    mocked.mockResolvedValue(
      payload({
        attributions: [attribution()],
      }),
    )
    renderCredits()

    const table = await screen.findByRole("table", { name: "共 1 张有外部来源的图, 逐张列出" })
    const rows = within(table)
    expect(rows.getByRole("cell", { name: "Black Dragon Society" })).toBeInTheDocument()
    expect(rows.getByRole("cell", { name: "#001 · 西湖.jpg" })).toBeInTheDocument()
    expect(rows.getByText("已修改")).toBeInTheDocument()
    // 署名要能点回原图: 来源页与许可全文都是 CC BY-SA 的硬要求, 不是装饰
    expect(rows.getByRole("link", { name: "Wikimedia Commons 上的原图" })).toHaveAttribute(
      "href",
      "https://commons.wikimedia.org/wiki/File:West_Lake.jpg",
    )
    expect(rows.getByRole("link", { name: "CC BY-SA 4.0" })).toHaveAttribute(
      "href",
      "https://creativecommons.org/licenses/by-sa/4.0/",
    )
    // 编号那一格点开就是站内那张图, 读者能核对「标的是不是这张」
    expect(rows.getByRole("link", { name: "#001 · 西湖.jpg" })).toHaveAttribute(
      "href",
      "/images/covers/west-lake.jpg",
    )
    expect(rows.getByRole("link", { name: "西湖" })).toHaveAttribute(
      "href",
      "/attraction/west-lake",
    )
  })

  it("没有外部来源时不编造逐图署名", async () => {
    mocked.mockResolvedValue(
      payload({
        images: [
          { credit: "Have-A-Trip 自绘", license: "MIT", license_url: null, image_count: 5 },
        ],
        image_total: 5,
      }),
    )
    renderCredits()

    expect(await screen.findByText("没有需要逐图署名的图")).toBeInTheDocument()
  })

  it("认不出来的许可只给字面, 不给链接", async () => {
    mocked.mockResolvedValue(
      payload({
        images: [{ credit: "某人", license: "自定义许可", license_url: null, image_count: 1 }],
        image_total: 1,
      }),
    )
    renderCredits()

    const table = await screen.findByRole("table", { name: "共 1 张图" })
    expect(within(table).getByRole("cell", { name: "自定义许可" })).toBeInTheDocument()
    expect(within(table).queryByRole("link", { name: "自定义许可" })).not.toBeInTheDocument()
  })
})
