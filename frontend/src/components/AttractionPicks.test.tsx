import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { fetchNearbyAttractions } from "../api/client"
import { LanguageProvider } from "../i18n"
import type { Attraction, NearbyResult } from "../types"
import AttractionPicks, { PICKS_SEEN_KEY } from "./AttractionPicks"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return { ...actual, fetchNearbyAttractions: vi.fn() }
})

const mockedNearby = vi.mocked(fetchNearbyAttractions)

const attraction = (slug: string, name: string, city = "杭州市"): Attraction => ({
  id: 1,
  slug,
  name,
  name_en: null,
  summary: "一句话简介",
  category: { slug: "nature", name: "自然风光" },
  city,
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

/** 三个都在同城 —— 后端那三级里最容易的一种。 */
const inHangzhou: NearbyResult = {
  items: [
    attraction("west-lake", "西湖"),
    attraction("lingyin-temple", "灵隐寺"),
    attraction("xixi-wetland", "西溪湿地"),
  ],
  located: true,
  scope: "city",
  city: "杭州市",
  region: "浙江省",
}

const secondBatch: NearbyResult = {
  items: [
    attraction("tianyi-pavilion", "天一阁", "宁波市"),
    attraction("putuo-mountain", "普陀山", "舟山市"),
    attraction("ocean-world", "海洋世界", "上海市"),
  ],
  located: true,
  scope: "region",
  city: "杭州市",
  region: "浙江省",
}

const renderPicks = () =>
  render(
    <MemoryRouter>
      <AttractionPicks />
    </MemoryRouter>,
  )

beforeEach(() => {
  mockedNearby.mockReset()
  window.sessionStorage.clear()
})

describe("AttractionPicks", () => {
  it("打开首页就弹, 标题是「出去走走」, 一次要三个", async () => {
    mockedNearby.mockResolvedValue(inHangzhou)
    renderPicks()

    const dialog = await screen.findByRole("dialog")
    expect(dialog).toBeInTheDocument()
    // 标题是产品名(出去走走); 依据(就近/猜的) 由标题下那一行与页脚说明, 两者不能只有其一
    expect(screen.getByRole("heading", { name: "出去走走" })).toBeInTheDocument()
    expect(mockedNearby).toHaveBeenCalledWith(3)
    for (const item of inHangzhou.items) {
      expect(screen.getByText(item.name)).toBeInTheDocument()
    }
  })

  it("三个都在同城时就说「猜你在杭州市」", async () => {
    mockedNearby.mockResolvedValue(inHangzhou)
    renderPicks()

    await screen.findByRole("dialog")
    const line = await screen.findByText(/^猜你在/)
    expect(line).toHaveTextContent("猜你在杭州市 —— 这三个就在附近。")
    // 那一行只有一种说法: 说了在同城就不能又说「国内/全部」(页脚那一段另算)
    expect(line).not.toHaveTextContent("全国")
  })

  it("同城不够用同省补齐时说清是哪一级补的", async () => {
    mockedNearby.mockResolvedValue(secondBatch)
    renderPicks()

    await screen.findByRole("dialog")
    expect(
      await screen.findByText("猜你在浙江省。同城不够三个, 用省内的补齐了。"),
    ).toBeInTheDocument()
  })

  it("位置认出来了但附近不够时, 明说其余是国内补的", async () => {
    mockedNearby.mockResolvedValue({
      items: [attraction("west-lake", "西湖"), attraction("palace-museum", "故宫博物院", "北京市")],
      located: true,
      scope: "nation",
      city: "杭州市",
      region: "浙江省",
    })
    renderPicks()

    await screen.findByRole("dialog")
    expect(
      await screen.findByText("猜你在杭州市, 但这一带收录的还不到三个, 其余是国内各地补的。"),
    ).toBeInTheDocument()
  })

  it("认不出位置时如实说「没认出你在哪儿」, 且说清三个是国内抽的", async () => {
    mockedNearby.mockResolvedValue({
      items: [attraction("palace-museum", "故宫博物院", "北京市")],
      located: false,
      scope: "nation",
      city: null,
      region: null,
    })
    renderPicks()

    await screen.findByRole("dialog")
    expect(
      await screen.findByText("没认出你在哪儿 —— 这三个是国内各地随机抽的。"),
    ).toBeInTheDocument()
  })

  it("连国内都不够时就直说这批是从全部景点里抽的, 不说成国内", async () => {
    mockedNearby.mockResolvedValue({
      items: [
        attraction("banff", "班夫国家公园"),
        attraction("marrakech-medina", "马拉喀什老城"),
        attraction("daocheng-yading", "稻城亚丁", "甘孜藏族自治州"),
      ],
      located: false,
      scope: "world",
      city: null,
      region: null,
    })
    renderPicks()

    await screen.findByRole("dialog")
    const line = await screen.findByText(/^就近和国内都没凑够/)
    expect(line).toHaveTextContent("就近和国内都没凑够三个, 剩下的是从全部景点里抽的。")
    // world 与 nation 的说法正相反: 判断顺序写反了这里就会说成「国内各地」
    expect(line).not.toHaveTextContent("国内各地")
  })

  it("页脚说明就近是按 IP 估的, 且不保存位置", async () => {
    mockedNearby.mockResolvedValue(inHangzhou)
    renderPicks()

    await screen.findByRole("dialog")
    const note = screen.getByText(/就近是按 IP 估到城市级的/)
    expect(note).toBeInTheDocument()
    expect(note).toHaveTextContent("不保存你的位置")
  })

  it("英文界面下同样说清依据, 不是换一句含糊话", async () => {
    mockedNearby.mockResolvedValue(inHangzhou)
    render(
      <MemoryRouter>
        <LanguageProvider initial="en">
          <AttractionPicks />
        </LanguageProvider>
      </MemoryRouter>,
    )

    await screen.findByRole("dialog")
    expect(screen.getByRole("heading", { name: "Out and about" })).toBeInTheDocument()
    // 库内取值是中文(杭州市), 英文界面下也照原样显示 —— 景点档案只有中文, 见 README
    expect(
      await screen.findByText("We think you are in 杭州市 — these three are close by."),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Nearby picks are estimated from your IP down to the city/),
    ).toBeInTheDocument()
  })

  it("一次会话只弹一次: 记过标记就不再请求, 也不再弹", async () => {
    window.sessionStorage.setItem(PICKS_SEEN_KEY, "1")
    mockedNearby.mockResolvedValue(inHangzhou)
    renderPicks()

    await waitFor(() => expect(mockedNearby).not.toHaveBeenCalled())
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("弹过之后会记下标记, 免得从别的页面切回首页时又弹一次", async () => {
    mockedNearby.mockResolvedValue(inHangzhou)
    renderPicks()

    await screen.findByRole("dialog")
    expect(window.sessionStorage.getItem(PICKS_SEEN_KEY)).toBe("1")
  })

  it("点关闭按钮就收起来", async () => {
    mockedNearby.mockResolvedValue(inHangzhou)
    renderPicks()

    await screen.findByRole("dialog")
    await userEvent.click(screen.getByRole("button", { name: "关闭" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("按 Esc 也能关", async () => {
    mockedNearby.mockResolvedValue(inHangzhou)
    renderPicks()

    await screen.findByRole("dialog")
    await userEvent.keyboard("{Escape}")
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("「换一批」重新抽一次, 内容与位置说明跟着换", async () => {
    mockedNearby.mockResolvedValueOnce(inHangzhou).mockResolvedValueOnce(secondBatch)
    renderPicks()

    await screen.findByText("西湖")
    await userEvent.click(screen.getByRole("button", { name: "换一批" }))

    expect(await screen.findByText("天一阁")).toBeInTheDocument()
    expect(screen.queryByText("西湖")).not.toBeInTheDocument()
    expect(screen.getByText(/用省内的补齐了/)).toBeInTheDocument()
    expect(mockedNearby).toHaveBeenCalledTimes(2)
  })

  it("接口挂了就不弹, 也不在首页上留一个报错", async () => {
    mockedNearby.mockRejectedValue(new Error("连不上后端"))
    renderPicks()

    await waitFor(() => expect(mockedNearby).toHaveBeenCalled())
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("库里没有景点时不弹一个空窗", async () => {
    mockedNearby.mockResolvedValue({
      items: [], located: false, scope: "nation", city: null, region: null,
    })
    renderPicks()

    await waitFor(() => expect(mockedNearby).toHaveBeenCalled())
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })
})
