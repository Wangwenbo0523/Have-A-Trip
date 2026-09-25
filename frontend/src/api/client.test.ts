import { AxiosError } from "axios"
import { describe, expect, it, vi } from "vitest"

import {
  API_BASE,
  createPost,
  deletePost,
  describeError,
  fetchPosts,
  getDeviceId,
  http,
} from "./client"

const axiosError = (options: { code?: string; status?: number; detail?: unknown }) => {
  const response =
    options.status === undefined
      ? undefined
      : {
          data: options.detail === undefined ? {} : { detail: options.detail },
          status: options.status,
          statusText: "",
          headers: {},
          config: {},
        }
  return new AxiosError("boom", options.code, {} as never, {} as never, response as never)
}

describe("describeError", () => {
  it("把后端的 detail 原样透给用户", () => {
    expect(describeError(axiosError({ status: 404, detail: "景点不存在或未发布" }))).toBe(
      "景点不存在或未发布",
    )
  })

  it("没有响应体时给出「后端没起」的指引, 而不是一句 failed", () => {
    const message = describeError(axiosError({ code: "ERR_NETWORK" }))
    expect(message).toContain("连不上后端")
    expect(message).toContain(API_BASE)
  })

  it("超时单独识别", () => {
    expect(describeError(axiosError({ code: "ECONNABORTED" }))).toContain("超时")
  })

  it("有响应但没有 detail 时退回状态码", () => {
    expect(describeError(axiosError({ status: 500 }))).toBe("后端返回 500")
  })

  it("非 axios 错误也能给出文字", () => {
    expect(describeError(new Error("炸了"))).toBe("炸了")
    expect(describeError("字符串")).toBe("未知错误")
  })
})

describe("getDeviceId", () => {
  it("同一个浏览器只生成一次, 并落进 localStorage", () => {
    window.localStorage.clear()
    const first = getDeviceId()
    expect(first).toBeTruthy()
    expect(getDeviceId()).toBe(first)
    expect(window.localStorage.getItem("have-a-trip.device_id")).toBe(first)
  })
})

describe("动态接口", () => {
  const emptyPage = {
    items: [],
    page: 1,
    size: 20,
    total: 0,
    daily_limit: 10,
    used_today: 0,
    disclaimer: "动态由用户发布。",
  }

  it("列表把设备号当 viewer 带上, 勾了「只看我的」才传 device_id", async () => {
    const get = vi.spyOn(http, "get").mockResolvedValue({ data: emptyPage })
    window.localStorage.clear()
    const device = getDeviceId()

    await fetchPosts({ onlyMine: true, attraction: "west-lake" })
    expect(get).toHaveBeenCalledWith("/posts", {
      params: {
        attraction: "west-lake",
        device_id: device,
        viewer: device,
        page: undefined,
        size: undefined,
      },
    })

    // 没勾「只看我的」时不传 device_id —— 一个参数是"给谁看", 另一个是"看谁的"
    get.mockClear()
    await fetchPosts()
    expect(get.mock.calls[0][1]?.params.device_id).toBeUndefined()
    get.mockRestore()
  })

  it("发帖只带正文/署名/景点, 不带任何定位", async () => {
    const post = vi.spyOn(http, "post").mockResolvedValue({ data: {} })
    window.localStorage.clear()

    await createPost({ body: "湖边光正好", nickname: "小北", attraction_slug: "west-lake" })
    expect(post).toHaveBeenCalledWith("/posts", {
      device_id: getDeviceId(),
      body: "湖边光正好",
      nickname: "小北",
      attraction_slug: "west-lake",
    })
    post.mockRestore()
  })

  it("删除是 DELETE 并带上设备号 —— 后端拿它判断是不是作者", async () => {
    const del = vi.spyOn(http, "delete").mockResolvedValue({ data: null })
    window.localStorage.clear()

    await deletePost(7)
    expect(del).toHaveBeenCalledWith("/posts/7", { params: { device_id: getDeviceId() } })
    del.mockRestore()
  })
})
