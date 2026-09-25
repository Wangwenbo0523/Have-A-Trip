import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError } from "axios"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  createPost,
  deletePost,
  fetchAttractions,
  fetchPosts,
  fetchPostsByAttraction,
} from "../api/client"
import type { Attraction, Post, PostPage } from "../types"
import PostsPage from "./PostsPage"

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client")
  return {
    ...actual,
    fetchAttractions: vi.fn(),
    fetchPosts: vi.fn(),
    fetchPostsByAttraction: vi.fn(),
    createPost: vi.fn(),
    deletePost: vi.fn(),
  }
})

const mockedList = vi.mocked(fetchPosts)
const mockedBySpot = vi.mocked(fetchPostsByAttraction)
const mockedSpots = vi.mocked(fetchAttractions)
const mockedCreate = vi.mocked(createPost)
const mockedDelete = vi.mocked(deletePost)

const WEST_LAKE: Attraction = {
  id: 1,
  slug: "west-lake",
  name: "西湖",
  name_en: "West Lake",
  summary: null,
  category: { slug: "nature", name: "自然风光" },
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

const post = (over: Partial<Post> = {}): Post => ({
  id: 1,
  author: { name: "小北" },
  body: "湖边光正好。",
  attraction: { slug: "west-lake", name: "西湖", name_en: "West Lake" },
  created_at: "2026-09-25T14:30:00+08:00",
  mine: false,
  ...over,
})

const page = (items: Post[], over: Partial<PostPage> = {}): PostPage => ({
  items,
  page: 1,
  size: 20,
  total: items.length,
  daily_limit: 10,
  used_today: 0,
  disclaimer: "动态由用户发布。",
  // 默认没有更旧的: 只有明确要翻页的用例才给游标
  next_cursor: null,
  ...over,
})

/** 后端的 429 结构化 detail, 形状见 backend/app/api/posts.py 的 _rejected。 */
const rejection429 = (detail: Record<string, unknown>) =>
  new AxiosError("boom", undefined, {} as never, {} as never, {
    data: { detail },
    status: 429,
    statusText: "",
    headers: {},
    config: {},
  } as never)

const renderPosts = (initial = "/posts") =>
  render(
    <MemoryRouter initialEntries={[initial]}>
      <PostsPage />
    </MemoryRouter>,
  )

beforeEach(() => {
  mockedList.mockReset()
  mockedBySpot.mockReset()
  mockedSpots.mockReset()
  mockedCreate.mockReset()
  mockedDelete.mockReset()
  window.localStorage.clear()
  mockedSpots.mockResolvedValue({ items: [WEST_LAKE], page: 1, size: 100, total: 1 })
  mockedList.mockResolvedValue(page([post()]))
  mockedBySpot.mockResolvedValue(page([post()]))
})

describe("PostsPage", () => {
  it("把大家发的动态列出来: 署名、正文、时间、挂的景点", async () => {
    mockedList.mockResolvedValue(
      page([
        post(),
        post({ id: 2, author: { name: "游客" }, body: "故宫很大。", attraction: null }),
      ]),
    )
    renderPosts()

    expect(await screen.findByText("湖边光正好。")).toBeInTheDocument()
    expect(screen.getByText("小北")).toBeInTheDocument()
    expect(screen.getByText("故宫很大。")).toBeInTheDocument()
    // 挂了景点的那条给链接, 没挂的没有
    const links = screen.getAllByRole("link", { name: /挂在/ })
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute("href", "/attraction/west-lake")
  })

  it("一条都没有时给空态而不是空白页", async () => {
    mockedList.mockResolvedValue(page([]))
    renderPosts()

    expect(await screen.findByText("还没有人说话")).toBeInTheDocument()
  })

  it("只有自己的动态才有删除按钮", async () => {
    mockedList.mockResolvedValue(
      page([
        post({ id: 1, mine: false, body: "别人的动态" }),
        post({ id: 2, mine: true, body: "我的动态" }),
      ]),
    )
    renderPosts()

    await screen.findByText("我的动态")
    expect(screen.getAllByRole("button", { name: "删除" })).toHaveLength(1)
  })

  it("写一条发出去: 带署名与挂上的景点, 发完重新取列表", async () => {
    mockedList.mockResolvedValue(page([]))
    mockedCreate.mockResolvedValue(post())
    renderPosts()

    await userEvent.type(await screen.findByLabelText("说点什么"), "傍晚到的湖边")
    await userEvent.type(screen.getByLabelText("署名"), "小北")
    await userEvent.click(screen.getByRole("combobox"))
    await userEvent.click(await screen.findByRole("option", { name: /西湖/ }))
    await userEvent.click(screen.getByRole("button", { name: "发出去" }))

    await waitFor(() =>
      expect(mockedCreate).toHaveBeenCalledWith({
        body: "傍晚到的湖边",
        nickname: "小北",
        attraction_slug: "west-lake",
      }),
    )
    // 发完要重新拉一次, 否则新动态不在列表里
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2))
  })

  it("不选景点也能发, 正文为空时按钮点不动", async () => {
    mockedList.mockResolvedValue(page([]))
    renderPosts()

    const submit = await screen.findByRole("button", { name: "发出去" })
    expect(submit).toBeDisabled()

    await userEvent.type(screen.getByLabelText("说点什么"), "只写两句")
    await userEvent.click(submit)
    await waitFor(() =>
      expect(mockedCreate).toHaveBeenCalledWith({
        body: "只写两句",
        nickname: undefined,
        attraction_slug: undefined,
      }),
    )
  })

  it("被限额拦下时说清「每天几条、什么时候能再来」", async () => {
    mockedCreate.mockRejectedValue(
      rejection429({
        status: "rejected",
        reason: "daily_limit_exceeded",
        retry_after: "2026-09-26T00:00:00+08:00",
        limit: 10,
      }),
    )
    renderPosts()

    await userEvent.type(await screen.findByLabelText("说点什么"), "再发一条")
    await userEvent.click(screen.getByRole("button", { name: "发出去" }))

    expect(await screen.findByText("今天先到这儿")).toBeInTheDocument()
    expect(screen.getByText(/每天最多发 10 条/)).toBeInTheDocument()
  })

  it("发帖报别的错时给普通错误提示", async () => {
    mockedCreate.mockRejectedValue(new Error("连不上后端"))
    renderPosts()

    await userEvent.type(await screen.findByLabelText("说点什么"), "再发一条")
    await userEvent.click(screen.getByRole("button", { name: "发出去" }))

    expect(await screen.findByText("没能发出去")).toBeInTheDocument()
    expect(screen.getByText("连不上后端")).toBeInTheDocument()
  })

  it("勾上「只看我的」只取自己的, 空的时候说法也不一样", async () => {
    mockedList.mockImplementation(async (params = {}) =>
      params.onlyMine
        ? page([])
        : page([
            post({ id: 1, mine: false, body: "别人的动态" }),
            post({ id: 2, mine: true, body: "我的动态" }),
          ]),
    )
    renderPosts()

    await screen.findByText("我的动态")
    await userEvent.click(screen.getByLabelText("只看我的"))

    await waitFor(() => expect(mockedList).toHaveBeenLastCalledWith({ onlyMine: true }))
    expect(await screen.findByText("你还没发过动态")).toBeInTheDocument()
  })

  it("今天剩几条名额来自后端, 用完时换一句话", async () => {
    mockedList.mockResolvedValue(page([post()], { used_today: 8, daily_limit: 10 }))
    renderPosts()

    expect(await screen.findByText("今天还能发 2 条")).toBeInTheDocument()
  })

  it("删自己的动态要先确认一次, 删完重新取列表", async () => {
    mockedList.mockResolvedValue(page([post({ id: 7, mine: true })]))
    mockedDelete.mockResolvedValue(undefined)
    renderPosts()

    await userEvent.click(await screen.findByRole("button", { name: "删除" }))
    // 只是进入确认态, 还没删
    expect(mockedDelete).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole("button", { name: "确认删除" }))
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith(7))
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2))
  })

  it("确认删除前可以取消", async () => {
    mockedList.mockResolvedValue(page([post({ id: 7, mine: true })]))
    renderPosts()

    await userEvent.click(await screen.findByRole("button", { name: "删除" }))
    await userEvent.click(screen.getByRole("button", { name: "取消" }))

    expect(screen.getByRole("button", { name: "删除" })).toBeInTheDocument()
    expect(mockedDelete).not.toHaveBeenCalled()
  })

  it("删除失败时给出提示, 不装作删掉了", async () => {
    mockedList.mockResolvedValue(page([post({ id: 7, mine: true })]))
    mockedDelete.mockRejectedValue(new Error("后端返回 404"))
    renderPosts()

    await userEvent.click(await screen.findByRole("button", { name: "删除" }))
    await userEvent.click(screen.getByRole("button", { name: "确认删除" }))

    expect(await screen.findByText("后端返回 404")).toBeInTheDocument()
  })

  it("带 ?attraction= 进来只看这个景点, 并且能一键看全部", async () => {
    renderPosts("/posts?attraction=west-lake")

    expect(await screen.findByText(/只看「西湖」/, { selector: ".posts__filter" })).toBeInTheDocument()
    expect(mockedBySpot).toHaveBeenCalledWith("west-lake", 20)

    await userEvent.click(screen.getByRole("button", { name: "看全部" }))
    await waitFor(() => expect(mockedList).toHaveBeenCalled())
  })

  it("还有更旧的时候才给「加载更多」, 翻到底就说一句没有更多了", async () => {
    mockedList.mockResolvedValueOnce(page([post({ id: 9 })], { next_cursor: 5 }))
    renderPosts()
    await screen.findByText("湖边光正好。")

    // 第一页的游标拿在手上, 按钮就该在
    const more = screen.getByRole("button", { name: "加载更多" })

    // 第二页就是最后一页: 按钮收起, 换成一句收尾
    mockedList.mockResolvedValueOnce(
      page([post({ id: 5, body: "更旧的" })], { next_cursor: null }),
    )
    await userEvent.click(more)

    expect(await screen.findByText("更旧的")).toBeInTheDocument()
    // 两页拼在一起, 第一页的不能被顶掉
    expect(screen.getByText("湖边光正好。")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "加载更多" })).not.toBeInTheDocument()
    expect(screen.getByText("没有更多了")).toBeInTheDocument()
  })

  it("「加载更多」把上一页的游标原样带回去, 取到的还是更旧的那一批", async () => {
    mockedList.mockResolvedValueOnce(page([post({ id: 9 })], { next_cursor: 9 }))
    renderPosts()
    await screen.findByText("湖边光正好。")

    mockedList.mockResolvedValueOnce(
      page([post({ id: 4, body: "更旧的 A" })], { next_cursor: 4 }),
    )
    await userEvent.click(screen.getByRole("button", { name: "加载更多" }))

    await waitFor(() =>
      expect(mockedList).toHaveBeenLastCalledWith({
        attraction: undefined,
        onlyMine: false,
        before: 9,
      }),
    )
    expect(await screen.findByText("更旧的 A")).toBeInTheDocument()
  })

  it("要下一页失败时说清错误, 按钮留着能再点一次", async () => {
    mockedList.mockResolvedValueOnce(page([post({ id: 9 })], { next_cursor: 5 }))
    renderPosts()
    await screen.findByText("湖边光正好。")

    mockedList.mockRejectedValueOnce(new Error("连不上后端"))
    await userEvent.click(screen.getByRole("button", { name: "加载更多" }))

    expect(await screen.findByText("连不上后端")).toBeInTheDocument()
    // 游标没动, 所以按钮还在, 再点还是这一页
    expect(screen.getByRole("button", { name: "加载更多" })).toBeInTheDocument()
  })

  it("后续页与第一页撞上时按 id 去重, 不把同一条摆两遍", async () => {
    mockedList.mockResolvedValueOnce(
      page([post({ id: 9 }), post({ id: 8, body: "第二条" })], { next_cursor: 8 }),
    )
    renderPosts()
    await screen.findByText("第二条")

    // 第二页把第一页已出现过的 id=8 又吐了一遍(删一条之后整体上移就会这样)
    mockedList.mockResolvedValueOnce(
      page([post({ id: 8, body: "第二条" }), post({ id: 7, body: "更旧的 B" })], { next_cursor: null }),
    )
    await userEvent.click(screen.getByRole("button", { name: "加载更多" }))

    expect(await screen.findByText("更旧的 B")).toBeInTheDocument()
    expect(screen.getAllByText("第二条")).toHaveLength(1)
  })

  it("第一页换了(切筛选、发完重拉)就把翻出来的后续页丢掉", async () => {
    mockedList.mockResolvedValueOnce(page([post({ id: 9 })], { next_cursor: 5 }))
    renderPosts()
    await screen.findByText("湖边光正好。")

    mockedList.mockResolvedValueOnce(page([post({ id: 5, body: "更旧的" })], { next_cursor: null }))
    await userEvent.click(screen.getByRole("button", { name: "加载更多" }))
    await screen.findByText("更旧的")

    // 勾「只看我的」= 换了一批数据: 位置已经变了, 接着往下接没有意义
    mockedList.mockResolvedValue(page([post({ id: 9 })], { next_cursor: null }))
    await userEvent.click(screen.getByLabelText("只看我的"))

    await waitFor(() => expect(screen.queryByText("更旧的")).not.toBeInTheDocument())
  })

  it("按景点看的时候, 翻页也带着这个景点", async () => {
    mockedBySpot.mockResolvedValueOnce(page([post({ id: 9 })], { next_cursor: 3 }))
    renderPosts("/posts?attraction=west-lake")
    await screen.findByText("湖边光正好。")

    mockedList.mockResolvedValueOnce(page([post({ id: 3, body: "更旧的 C" })], { next_cursor: null }))
    await userEvent.click(screen.getByRole("button", { name: "加载更多" }))

    await waitFor(() =>
      expect(mockedList).toHaveBeenLastCalledWith({
        attraction: "west-lake",
        onlyMine: false,
        before: 3,
      }),
    )
    expect(await screen.findByText("更旧的 C")).toBeInTheDocument()
  })
})
