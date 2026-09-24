import type { MessageKey } from "../i18n/messages"

/**
 * 站外搜索入口。
 *
 * 只拼搜索页地址 —— 不内嵌播放器、不抓取、不转载, 也不替某条具体视频背书。
 *
 * 目前只放 B 站搜索页。每加一个站点都要确认: 搜索页地址可直接拼接, 且不需要
 * 登录、不需要开发者密钥。
 */

export interface ExternalSearchSite {
  id: string
  /** 站点名的**文案键**(文案在 i18n 里, 这里不写死中文) */
  nameKey: MessageKey
  /** 搜索页地址, 关键词由调用方负责 URL 编码前的 trim */
  searchUrl: (keyword: string) => string
}

export const EXTERNAL_SEARCH_SITES: ExternalSearchSite[] = [
  {
    id: "bilibili",
    nameKey: "external.site.bilibili",
    searchUrl: (keyword) =>
      `https://search.bilibili.com/all?keyword=${encodeURIComponent(keyword)}`,
  },
]
