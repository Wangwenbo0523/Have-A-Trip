import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, useLocation } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchAttraction, fetchAttractions } from "../api/client"
import type { Attraction, AttractionDetail } from "../types"
import ComparePage from "./ComparePage"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchAttractions: vi.fn(), fetchAttraction: vi.fn() }
})

const mockedList = vi.mocked(fetchAttractions)
const mockedDetail = vi.mocked(fetchAttraction)

const listItem = (id: number, slug: string, name: string): Attraction => ({
  id,
  slug,
  name,
  name_en: null,
  summary: null,
  category: { slug: "nature", name: "自然风光" },
  city: null,
  province: null,
  tags: [],
  cover_image: null,
  rating_avg: 0,
  rating_count: 0,
  ticket_price: null,
  suggested_hours: null,
  country_code: "CN",
  a_level: null,
  heritage: null,
})

const WEST_LAKE = listItem(1, "west-lake", "西湖")
const PALACE = listItem(2, "palace-museum", "故宫博物院")
const TERRACOTTA = listItem(3, "terracotta-army", "秦始皇兵马俑")

const detail = (over: Partial<AttractionDetail>): AttractionDetail => ({
  ...WEST_LAKE,
  description: null,
  address: null,
  lat: null,
  lon: null,
  best_season: null,
  images: [],
  plans: [],
  source: "测试夹具",
  license: "MIT",
  source_url: null,
  updated_at: "2026-09-25T10:00:00+08:00",
  ...over,
})

const DETAILS: Record<string, AttractionDetail> = {
  "west-lake": detail({
    slug: "west-lake",
    name: "西湖",
    city: "杭州市",
    province: "浙江省",
    tags: [{ slug: "free", name: "免票" }],
    rating_avg: 4.9,
    rating_count: 200,
    ticket_price: 0,
    suggested_hours: 4,
    a_level: "5A",
    heritage: "cultural",
    best_season: "春秋",
  }),
  "palace-museum": detail({
    slug: "palace-museum",
    name: "故宫博物院",
    category: { slug: "museum", name: "博物馆" },
    city: "北京市",
    province: "北京市",
    rating_avg: 4.5,
    rating_count: 50,
    ticket_price: 60,
    suggested_hours: 3,
    heritage: "cultural",
  }),
  "terracotta-army": detail({
    slug: "terracotta-army",
    name: "秦始皇兵马俑",
    category: { slug: "history", name: "历史古迹" },
  }),
}

const LocationProbe = () => {
  const location = useLocation()
  return <span data-testid="search">{location.search}</span>
}

const renderCompare = (initial = "/compare") =>
  render(
    <MemoryRouter initialEntries={[initial]}>
      <ComparePage />
      <LocationProbe />
    </MemoryRouter>,
  )

beforeEach(() => {
  mockedList.mockReset()
  mockedDetail.mockReset()
  mockedList.mockResolvedValue({
    items: [WEST_LAKE, PALACE, TERRACOTTA],
    page: 1,
    size: 100,
    total: 3,
  })
  mockedDetail.mockImplementation(async (slug: string) => DETAILS[slug])
})

describe("ComparePage", () => {
  it("没带参数时自动挑前两个, 并把选择写进 URL", async () => {
    renderCompare()

    expect(await screen.findByRole("columnheader", { name: "西湖" })).toBeInTheDocument()
    expect(screen.getByRole("columnheader", { name: "故宫博物院" })).toBeInTheDocument()
    // 对比结果是一条可以直接发出去的链接, 所以选择必须落在 URL 上而不是组件状态里
    await waitFor(() => {
      expect(screen.getByTestId("search")).toHaveTextContent("a=west-lake")
      expect(screen.getByTestId("search")).toHaveTextContent("b=palace-museum")
    })
    expect(mockedList).toHaveBeenCalledTimes(1)
  })

  it("链接里给好了两边就照它显示, 不改写 URL", async () => {
    renderCompare("/compare?a=palace-museum&b=west-lake")

    expect(await screen.findByRole("columnheader", { name: "故宫博物院" })).toBeInTheDocument()
    expect(screen.getByLabelText("景点 A")).toHaveValue("palace-museum")
    expect(screen.getByTestId("search")).toHaveTextContent("?a=palace-museum&b=west-lake")
  })

  it("景点多到一页装不下时把后面几页也取回来 —— 下拉里要能选到全部", async () => {
    // 后端 max_page_size = 100, 所以 156 个景点不可能一页取完
    const firstPage = Array.from({ length: 100 }, (_, index) =>
      listItem(index + 1, `first-${index + 1}`, `第一页第 ${index + 1} 个`),
    )
    const deepCut = listItem(101, "deep-cut", "第 101 个景点")
    mockedList.mockImplementation(async (query = {}) =>
      (query.page ?? 1) === 1
        ? { items: firstPage, page: 1, size: 100, total: 101 }
        : { items: [deepCut], page: 2, size: 100, total: 101 },
    )
    mockedDetail.mockImplementation(async (slug) => detail({ slug, name: slug }))

    renderCompare("/compare?a=deep-cut&b=first-1")

    // 第二页的景点要出现在候选里, 链接里给的选择也不能被改写成第一页的。
    // 两个下拉框都铺全部选项, 所以断言要收在 A 那个 select 里, 否则同名 option 会有两个
    const pickerA = await screen.findByLabelText("景点 A")
    expect(await within(pickerA).findByRole("option", { name: "第 101 个景点" })).toBeInTheDocument()
    expect(pickerA).toHaveValue("deep-cut")
    expect(await screen.findByRole("columnheader", { name: "deep-cut" })).toBeInTheDocument()

    // 翻页是串行的: 第二页的请求要等第一页回来才知道有没有, 所以断言放在等待之后
    expect(mockedList).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }))
    expect(mockedList).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
  })

  it("对调是同一份档案换边显示, 不重新取数据", async () => {
    renderCompare("/compare?a=west-lake&b=palace-museum")
    await screen.findByRole("columnheader", { name: "西湖" })
    const callsBefore = mockedDetail.mock.calls.length

    await userEvent.click(screen.getByRole("button", { name: "对调" }))

    await waitFor(() => expect(screen.getByLabelText("景点 A")).toHaveValue("palace-museum"))
    const headers = screen.getAllByRole("columnheader")
    expect(headers[1]).toHaveTextContent("故宫博物院")
    expect(headers[2]).toHaveTextContent("西湖")
    // 依赖里放的是排序后的 slug 对, 所以对调不会让 useApi 再打两个请求
    expect(mockedDetail.mock.calls.length).toBe(callsBefore)
  })

  it("换一个景点会去取那一份档案", async () => {
    renderCompare("/compare?a=west-lake&b=palace-museum")
    await screen.findByRole("columnheader", { name: "西湖" })

    await userEvent.selectOptions(screen.getByLabelText("景点 A"), "terracotta-army")

    await waitFor(() => expect(mockedDetail).toHaveBeenCalledWith("terracotta-army"))
    expect(screen.getByTestId("search")).toHaveTextContent("a=terracotta-army")
  })

  it("逐字段并排显示, 只有评分标「更高」", async () => {
    renderCompare("/compare?a=west-lake&b=palace-museum")
    const table = await screen.findByRole("table")

    // 八行字段都在, 且用的是同一套文案键
    for (const name of ["分类", "城市", "评分", "票价", "建议游览", "景区等级", "世界遗产", "最佳季节", "标签"]) {
      expect(within(table).getByRole("rowheader", { name })).toBeInTheDocument()
    }
    expect(within(table).getByRole("cell", { name: "免费" })).toBeInTheDocument()
    expect(within(table).getByRole("cell", { name: "¥60" })).toBeInTheDocument()
    // 4.9 / 200 人 对 4.5 / 50 人
    expect(within(table).getByText("评分更高")).toBeInTheDocument()
    expect(within(table).getAllByText("评分更高")).toHaveLength(1)
  })

  it("两边都没人评分时不比高低 —— 0 分不是低分, 是还没有评分", async () => {
    mockedDetail.mockImplementation(async (slug) =>
      detail({ slug, name: slug === "west-lake" ? "西湖" : "故宫博物院" }),
    )
    renderCompare("/compare?a=west-lake&b=palace-museum")

    const table = await screen.findByRole("table")
    expect(within(table).getAllByText("暂无评分")).toHaveLength(2)
    expect(within(table).queryByText("评分更高")).not.toBeInTheDocument()
  })

  it("两边选同一个景点时说清楚, 不显示一份自己跟自己比的表", async () => {
    renderCompare("/compare?a=west-lake&b=west-lake")

    expect(await screen.findByText("两边选的是同一个景点, 换一个再看")).toBeInTheDocument()
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
  })

  it("少于两个已发布景点时说明原因, 不摆两个空下拉框", async () => {
    mockedList.mockResolvedValue({ items: [WEST_LAKE], page: 1, size: 100, total: 1 })
    renderCompare()

    expect(await screen.findByText("库里还没有已发布的景点")).toBeInTheDocument()
    expect(screen.queryByLabelText("景点 A")).not.toBeInTheDocument()
  })

  it("接口挂掉时给错误态与重试", async () => {
    mockedList.mockRejectedValueOnce(new Error("连不上后端"))
    renderCompare()

    expect(await screen.findByText("对比加载失败")).toBeInTheDocument()
    expect(screen.getByText("连不上后端")).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "重试" }))
    expect(await screen.findByRole("columnheader", { name: "西湖" })).toBeInTheDocument()
  })
})
