import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchRandomAttractions } from "../api/client"
import type { Attraction } from "../types"
import RandomPicks, { RANDOM_PICKS_SEEN } from "./RandomPicks"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchRandomAttractions: vi.fn() }
})

const mockedRandom = vi.mocked(fetchRandomAttractions)

const attraction = (slug: string, name: string): Attraction => ({
  id: 1,
  slug,
  name,
  name_en: null,
  summary: "一句话简介",
  category: { slug: "nature", name: "自然风光" },
  city: "杭州市",
  province: "浙江省",
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

const firstBatch = [
  attraction("west-lake", "西湖"),
  attraction("palace-museum", "故宫博物院"),
  attraction("terracotta-army", "秦始皇兵马俑"),
]

const secondBatch = [
  attraction("lingyin-temple", "灵隐寺"),
  attraction("ocean-world", "海洋世界"),
  attraction("draft-spot", "未发布景点"),
]

const renderPicks = () =>
  render(
    <MemoryRouter>
      <RandomPicks />
    </MemoryRouter>,
  )

beforeEach(() => {
  mockedRandom.mockReset()
  window.sessionStorage.clear()
})

describe("RandomPicks", () => {
  it("打开首页就弹, 一次要三个随机地点", async () => {
    mockedRandom.mockResolvedValue(firstBatch)
    renderPicks()

    const dialog = await screen.findByRole("dialog")
    expect(dialog).toBeInTheDocument()
    expect(mockedRandom).toHaveBeenCalledWith(3)
    for (const item of firstBatch) {
      expect(screen.getByText(item.name)).toBeInTheDocument()
    }
  })

  it("一次会话只弹一次: 记过标记就不再请求, 也不再弹", async () => {
    window.sessionStorage.setItem(RANDOM_PICKS_SEEN, "1")
    mockedRandom.mockResolvedValue(firstBatch)
    renderPicks()

    await waitFor(() => expect(mockedRandom).not.toHaveBeenCalled())
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("弹过之后会记下标记, 免得从别的页面切回首页时又弹一次", async () => {
    mockedRandom.mockResolvedValue(firstBatch)
    renderPicks()

    await screen.findByRole("dialog")
    expect(window.sessionStorage.getItem(RANDOM_PICKS_SEEN)).toBe("1")
  })

  it("点关闭按钮就收起来", async () => {
    mockedRandom.mockResolvedValue(firstBatch)
    renderPicks()

    await screen.findByRole("dialog")
    await userEvent.click(screen.getByRole("button", { name: "关闭" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("按 Esc 也能关", async () => {
    mockedRandom.mockResolvedValue(firstBatch)
    renderPicks()

    await screen.findByRole("dialog")
    await userEvent.keyboard("{Escape}")
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("「换一批」重新抽一次, 内容跟着换", async () => {
    mockedRandom.mockResolvedValueOnce(firstBatch).mockResolvedValueOnce(secondBatch)
    renderPicks()

    await screen.findByText("西湖")
    await userEvent.click(screen.getByRole("button", { name: "换一批" }))

    expect(await screen.findByText("灵隐寺")).toBeInTheDocument()
    expect(screen.queryByText("西湖")).not.toBeInTheDocument()
    expect(mockedRandom).toHaveBeenCalledTimes(2)
  })

  it("接口挂了就不弹, 也不在首页上留一个报错", async () => {
    mockedRandom.mockRejectedValue(new Error("连不上后端"))
    renderPicks()

    await waitFor(() => expect(mockedRandom).toHaveBeenCalled())
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("库里没有景点时不弹一个空窗", async () => {
    mockedRandom.mockResolvedValue([])
    renderPicks()

    await waitFor(() => expect(mockedRandom).toHaveBeenCalled())
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })
})
