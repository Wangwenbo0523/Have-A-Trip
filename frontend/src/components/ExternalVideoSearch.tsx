import React from "react"

import { EXTERNAL_SEARCH_SITES, externalSearchText } from "../lib/externalSearch"
import "../styles/externalSearch.css"

interface Props {
  /** 搜索关键词, 用景点名 */
  keyword: string
}

/**
 * 站外视频搜索入口。
 *
 * 给的是搜索页链接而不是具体视频: 具体视频会死链, 而且等于替某条内容背书。
 * 也不做 iframe 内嵌 —— 那会把第三方脚本和 Cookie 引进来。
 */
const ExternalVideoSearch = ({ keyword }: Props) => {
  const trimmed = keyword.trim()
  if (!trimmed) return null

  return (
    <section className="detail__section" aria-labelledby="detail-external-search">
      <h3 className="section__title" id="detail-external-search">
        相关视频
      </h3>
      <ul className="externalSearch__list">
        {EXTERNAL_SEARCH_SITES.map((site) => (
          <li key={site.id}>
            <a
              className="externalSearch__link"
              href={site.searchUrl(trimmed)}
              target="_blank"
              rel="noreferrer noopener"
            >
              {externalSearchText(site, trimmed)}
            </a>
          </li>
        ))}
      </ul>
      <p className="externalSearch__note">
        点开是站外搜索页, 视频由平台与上传者提供, 与本应用无关;
        本应用不内嵌播放器, 也不抓取或转载这些内容。
      </p>
    </section>
  )
}

export default ExternalVideoSearch
