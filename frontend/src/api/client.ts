/**
 * 后端 API 客户端。
 *
 * 契约来源: backend/app/schemas.py —— 改这里之前先改后端, 反之亦然。
 * 请求地址取自 VITE_API_BASE, 默认同源 /api/v1(开发时由 vite 代理转发)。
 */
import axios from "axios"

import type {
  AIAskResult,
  AIRecommendNotes,
  AISearchResult,
  AIStatus,
  Attraction,
  AttractionDetail,
  CategoryWithCount,
  EventPayload,
  Page,
  PageQuery,
  Recommendation,
  SourcesResponse,
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

/** 数据来源与许可声明页的原料。后端从 attraction / attraction_image 聚合, 前端不写死。 */
export async function fetchSources(): Promise<SourcesResponse> {
  const { data } = await http.get<SourcesResponse>("/sources")
  return data
}

/**
 * 模型调用比普通查询慢得多(后端 LLM_TIMEOUT_SECONDS 默认 20 秒)。
 * 用 axios 那个 10 秒的默认超时会把一次正常的解析掐断, 所以单独给一个更宽的值。
 */
const AI_TIMEOUT_MS = 30000

/**
 * AI 入口是否可用。默认配置下后端返回 available=false。
 * 拿不到就当不可用 —— 宁可不显示入口, 也不给一个点了没反应的按钮。
 */
export async function fetchAIStatus(): Promise<AIStatus> {
  const { data } = await http.get<AIStatus>("/ai/status")
  return data
}

/**
 * 用一句话找景点。后端把这句话解析成筛选条件, 再用库内档案检索。
 * 模型不可用 / 超时时仍然返回 200 并带 degraded=true, 不是错误 —— 调用方按正常结果处理。
 */
export async function searchByAI(query: string): Promise<AISearchResult> {
  const { data } = await http.post<AISearchResult>(
    "/ai/search",
    { query },
    { timeout: AI_TIMEOUT_MS },
  )
  return data
}

/**
 * 就某个景点追问一句。答案只依据这个景点的档案字段;
 * 模型不可用或说法查不到依据时, 后端降级成档案摘录并返回 200, 不是错误。
 */
export async function askAboutAttraction(slug: string, question: string): Promise<AIAskResult> {
  const { data } = await http.post<AIAskResult>(
    "/ai/ask",
    { slug, question },
    { timeout: AI_TIMEOUT_MS },
  )
  return data
}

/**
 * 润色推荐位的「为什么推荐它」。条目与顺序仍由 /recommendations 决定 ——
 * 这里只多拿一层文案, 模型碰不到推荐结果本身。
 *
 * 未配置模型或说法查不到依据时后端返回 200 并带 polished=false, 此时 reasons
 * 就是原来的理由, 调用方照常显示即可, 不是错误。
 */
export async function fetchRecommendNotes(limit = 6): Promise<AIRecommendNotes> {
  const { data } = await http.post<AIRecommendNotes>(
    "/ai/recommend-notes",
    { device_id: getDeviceId(), limit },
    { timeout: AI_TIMEOUT_MS },
  )
  return data
}

/** 上报一条行为。埋点失败不该挡住阅读, 调用方自行决定要不要 catch。 */
export async function reportEvent(payload: EventPayload): Promise<void> {
  await http.post("/events", payload)
}

export { http }
