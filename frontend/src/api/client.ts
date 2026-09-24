/**
 * 后端 API 客户端。
 *
 * 契约来源: backend/app/schemas.py —— 改这里之前先改后端, 反之亦然。
 * 请求地址取自 VITE_API_BASE, 默认同源 /api/v1(开发时由 vite 代理转发)。
 */
import axios from "axios"

import type {
  Attraction,
  AttractionDetail,
  CategoryWithCount,
  EventPayload,
  Page,
  PageQuery,
  Recommendation,
  TagWithCount,
} from "../types"

export const API_BASE = (import.meta.env.VITE_API_BASE || "/api/v1").replace(/\/+$/, "")

const http = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: { Accept: "application/json" },
})

/** 把各种报错翻译成一句可以直接显示给用户的中文。 */
export function describeError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === "string") return detail
    if (error.code === "ECONNABORTED") return "请求超时, 后端可能没在运行"
    if (!error.response) return `连不上后端 ${API_BASE}, 请先启动 FastAPI 服务`
    return `后端返回 ${error.response.status}`
  }
  if (error instanceof Error) return error.message
  return "未知错误"
}

const DEVICE_ID_KEY = "have-a-trip.device_id"

/**
 * 匿名设备号: 一期没有账号体系, 用它区分「谁的行为数据」。
 * 这不是定位 —— 只是一个本地生成的随机串, 不含任何位置信息。
 * localStorage 在隐私模式下可能抛异常, 所以整体兜底。
 */
export function getDeviceId(): string {
  try {
    const existing = window.localStorage.getItem(DEVICE_ID_KEY)
    if (existing) return existing
    const generated =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `dev-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
    window.localStorage.setItem(DEVICE_ID_KEY, generated)
    return generated
  } catch {
    return "anonymous"
  }
}

export async function fetchCategories(): Promise<CategoryWithCount[]> {
  const { data } = await http.get<CategoryWithCount[]>("/categories")
  return data
}

export async function fetchTags(): Promise<TagWithCount[]> {
  const { data } = await http.get<TagWithCount[]>("/tags")
  return data
}

export async function fetchAttractions(query: PageQuery = {}): Promise<Page<Attraction>> {
  const { data } = await http.get<Page<Attraction>>("/attractions", { params: query })
  return data
}

export async function fetchAttraction(slug: string): Promise<AttractionDetail> {
  const { data } = await http.get<AttractionDetail>(`/attractions/${encodeURIComponent(slug)}`)
  return data
}

export async function fetchSimilar(slug: string, limit = 6): Promise<Attraction[]> {
  const { data } = await http.get<Attraction[]>(
    `/attractions/${encodeURIComponent(slug)}/similar`,
    { params: { limit } },
  )
  return data
}

/**
 * 推荐。后端保证不返回空列表: rec_result 离线结果 -> 内容相似度 -> 热门兜底,
 * 三级降级链, 新用户也有东西可看。
 */
export async function fetchRecommendations(limit = 6): Promise<Recommendation[]> {
  const { data } = await http.get<Recommendation[]>("/recommendations", {
    params: { device_id: getDeviceId(), limit },
  })
  return data
}

/** 上报一条行为。埋点失败不该挡住阅读, 调用方自行决定要不要 catch。 */
export async function reportEvent(payload: EventPayload): Promise<void> {
  await http.post("/events", payload)
}

export { http }
