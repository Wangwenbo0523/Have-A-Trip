import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchAttractions } from "../api/client"
import type { Attraction } from "../types"
import AttractionBrowser from "./AttractionBrowser"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchAttractions: vi.fn() }
})

const mockedFetch = vi.mocked(fetchAttractions)

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
})