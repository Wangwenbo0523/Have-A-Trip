/**
 * 站外搜索入口。
 *
 * 只拼搜索页地址 —— 不内嵌播放器、不抓取正文、不下载素材。详情页给的是
 * 「去站外找相关内容」的入口, 内容本身仍归平台与上传者, 与本应用无关。
 *
 * 新增站点只改下面这个数组。每加一个都要先确认那条搜索地址能直接打开,
 * 且不需要登录、不需要申请密钥。
 */

export interface ExternalSearchSite {
  id: string
  /** 站点名, 同时也出现在链接文案里 */
  name: string
  /** 搜索页地址。关键词由调用方负责 URL 编码前的 trim */
  searchUrl: (keyword: string) => string
}

export const EXTERNAL_SEARCH_SITES: ExternalSearchSite[] = [
  {
    id: "bilibili",
    name: "哔哩哔哩",
    searchUrl: (keyword) =>
      `https://search.bilibili.com/all?keyword=${encodeURIComponent(keyword)}`,
  },
]

/** 链接文案。keyword 为空时不渲染, 由组件守住这条, 这里不兜底。 */
export const externalSearchText = (site: ExternalSearchSite, keyword: string) =>
  `去${site.name}搜「${keyword}」`
