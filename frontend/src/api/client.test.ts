import { AxiosError } from "axios"
import { describe, expect, it } from "vitest"

import { API_BASE, describeError, getDeviceId } from "./client"

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