/**
 * 后端 API 客户端。
 *
 * 契约来源: backend/app/schemas.py —— 改这里之前先改后端, 反之亦然。
 * 请求地址取自 VITE_API_BASE, 默认同源 /api/v1(开发时由 vite 代理转发)。
 */
import axios from "axios"

import { translate, type Lang } from "../i18n"
import type {
  AIAskResult,
  AIRecommendNotes,
  AISearchResult,
  AIStatus,
  Attraction,
  AttractionDetail,
  CategoryWithCount,
  EventPayload,
  Itinerary,
  ItineraryAccepted,
  ItineraryRejection,
  NearbyResult,
  Page,
  PageQuery,
  Recommendation,
  SemanticSearchResult,
  SourcesResponse,
  StatsResponse,
  TagWithCount,
} from "../types"

export const API_BASE = (import.meta.env.VITE_API_BASE || "/api/v1").replace(/\/+$/, "")

const http = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: { Accept: "application/json" },
})

/**
 * 把各种报错翻译成一句可以直接显示给用户的话。
 *
 * 默认中文。后端返回的 detail 是**内容**(见 src/i18n/messages.ts 的口径), 原样透传;
 * 只有前端自己拼的这几句(连不上、超时、状态码)才走文案表, 好跟着语种切换。
 */
export function describeError(error: unknown, lang: Lang = "zh"): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === "string") return detail
    if (error.code === "ECONNABORTED") return translate(lang, "api.timeout")
    if (!error.response) return translate(lang, "api.offline", { base: API_BASE })
    return translate(lang, "api.status", { status: error.response.status })
  }
  if (error instanceof Error) return error.message
  return translate(lang, "api.unknown")
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

/**
 * 随机抽几个景点, **不问你在哪儿**。
 *
 * 与 /recommendations 的区别: 那条按 (用户, 条数) 缓存, 同一个人的结果稳定;
 * 这一条后端**不缓存**(响应上写了 no-store), 每次调用都是一组新的 —— 所以
 * 「换一批」直接再调一次即可, 不需要什么刷新参数。
 *
 * 首页的「出去走走」走的是下面那条 fetchNearbyAttractions(它认不出来时会自己退回
 * 全国随机); 这条留给不需要位置的入口。
 */
export async function fetchRandomAttractions(limit = 3): Promise<Attraction[]> {
  const { data } = await http.get<Attraction[]>("/attractions/random", { params: { limit } })
  return data
}

/**
 * 按 IP 猜你在哪儿, 尽量抽附近的三个 —— 首页「出去走走」用这个。
 *
 * 认不出位置**不是错误**: 后端照常返回全国随机并把 scope 标成 nation, 所以拿到的
 * 一定是三个(库非空时), 调用方只需按 scope / located 如实说明依据。
 * 与随机那条一样**不缓存**, 「换一批」再调一次即可(每次都会重新猜一次位置)。
 */
export async function fetchNearbyAttractions(limit = 3): Promise<NearbyResult> {
  const { data } = await http.get<NearbyResult>("/attractions/nearby", { params: { limit } })
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

/** 看板原料。后端现算, 前端不写死任何一个数字。 */
export async function fetchStats(): Promise<StatsResponse> {
  const { data } = await http.get<StatsResponse>("/stats")
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

/**
 * 按意思找景点。向量不可用时后端**就地退回关键词检索**并照样返回条目,
 * 只是会带 degraded=true —— 调用方照常渲染, 只需要决定要不要提示一句。
 */
export async function searchSemantic(query: string, limit?: number): Promise<SemanticSearchResult> {
  const { data } = await http.post<SemanticSearchResult>(
    "/search/semantic",
    { query, limit },
    { timeout: AI_TIMEOUT_MS },
  )
  return data
}

/**
 * 提交一次行程生成。后端只落一行 pending 就返回, 生成在后台跑 ——
 * 所以这里拿到的 status 基本一定是 pending, 之后要用 token 轮询。
 */
export async function createItinerary(requestText: string, days: number): Promise<ItineraryAccepted> {
  const { data } = await http.post<ItineraryAccepted>(
    "/itineraries",
    { request_text: requestText, days, device_id: getDeviceId() },
    { timeout: AI_TIMEOUT_MS },
  )
  return data
}

/** 按 token 取行程。token 不匹配一律 404。 */
export async function fetchItinerary(token: string): Promise<Itinerary> {
  const { data } = await http.get<Itinerary>(`/itineraries/${encodeURIComponent(token)}`)
  return data
}

/**
 * 把 429 的结构化 detail 抠出来。不是限额拒绝就返回 null, 由调用方走普通报错路径。
 * 单独一个函数是因为「今日次数用完」需要完全不同的提示语与一个「什么时候再来」的时间。
 */
export function itineraryRejection(error: unknown): ItineraryRejection | null {
  if (!axios.isAxiosError(error)) return null
  const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
  if (detail && typeof detail === "object" && "reason" in detail) {
    return detail as ItineraryRejection
  }
  return null
}

/** 上报一条行为。埋点失败不该挡住阅读, 调用方自行决定要不要 catch。 */
export async function reportEvent(payload: EventPayload): Promise<void> {
  await http.post("/events", payload)
}

export { http }
