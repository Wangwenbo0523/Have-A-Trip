import React from "react"

import { useI18n } from "../i18n"
import { EXTERNAL_SEARCH_SITES } from "../lib/externalSearch"
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
  const { t } = useI18n()
  const trimmed = keyword.trim()
  if (!trimmed) return null

  return (
    <section className="detail__section" aria-labelledby="detail-external-search">
      <h3 className="section__title" id="detail-external-search">
        {t("external.title")}
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
              {t("external.link", { site: t(site.nameKey), keyword: trimmed })}
            </a>
          </li>
        ))}
      </ul>
      <p className="externalSearch__note">{t("external.note")}</p>
    </section>
  )
}

export default ExternalVideoSearch
