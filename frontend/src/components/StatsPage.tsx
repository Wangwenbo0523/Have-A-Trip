import React from "react"
import { Link } from "react-router-dom"

import { fetchStats } from "../api/client"
import { useApi } from "../hooks/useApi"
import { useI18n, type MessageKey } from "../i18n"
import { HERITAGE_TEXT } from "../lib/grade"
import type { Heritage, StatSlice } from "../types"
import StateMessage from "./StateMessage"

import "../styles/stats.css"

/** 条形按**本组内最大档**归一化。跨组比长度没有意义, 所以每组各自算满格。 */
const barWidth = (count: number, peak: number): string => {
  if (peak <= 0 || count <= 0) return "0%"
  // 极小的一档也要留一条看得见的细线, 否则 1 和 0 在图上分不出来
  return `${Math.max((count / peak) * 100, 1.5)}%`
}

/**
 * 条形。手写 SVG 而不是引图表库: 需求只是几条水平条, 引一个图表库要多背几百 KB
 * 和一个许可证风险(依赖卡口见 CONTRIBUTING.md), 不划算。
 *
 * 名称与数字用真实文本渲染, 只有条形本身 aria-hidden —— 屏幕阅读器听到的是
 * 「自然风光 12 个」, 而不是一串没有意义的图形。
 */
const Bar = ({ count, peak }: { count: number; peak: number }) => (
  <svg className="stats__bar" width="100%" height="10" aria-hidden="true">
    <rect className="stats__barTrack" x="0" y="0" width="100%" height="10" rx="5" />
    <rect
      className="stats__barFill"
      x="0"
      y="0"
      width={barWidth(count, peak)}
      height="10"
      rx="5"
    />
  </svg>
)

/** 世界遗产的取值 -> 文案键。库里存的是 cultural 这类机器取值, 得翻成人话。 */
const HERITAGE_LABEL: Record<Heritage, MessageKey> = {
  cultural: HERITAGE_TEXT.cultural.full,
  natural: HERITAGE_TEXT.natural.full,
  mixed: HERITAGE_TEXT.mixed.full,
}

/**
 * 数据看板。
 *
 * 页面上的每个数字都是后端现算的(见 backend/app/api/stats.py), 前端一个都不写死 ——
 * 写死的数字迟早会和数据库对不上, 而且没人会发现。
 *
 * 三处刻意的口径, 页面上都要说清楚, 否则读图的人会自己脑补:
 * - 只统计已发布景点, 下架与草稿不进任何数字。
 * - 配图与方案也只统计已发布景点名下的。
 * - 档案里没填的取值显示为「未核实」并计入总数, 不丢档 —— 各档之和一定等于总数。
 */
const StatsPage = () => {
  const { t } = useI18n()
  const { data, loading, error, reload } = useApi(() => fetchStats(), [])

  const distribution = (
    title: string,
    detail: string | null,
    slices: StatSlice[],
    labelOf: (slice: StatSlice) => string,
  ) => {
    const peak = slices.reduce((highest, slice) => Math.max(highest, slice.count), 0)
    return (
      <section className="section">
        <h3 className="section__title">{title}</h3>
        {detail ? <p className="stats__detail">{detail}</p> : null}
        {slices.length === 0 ? (
          <p className="stats__empty">{t("stats.empty.bar")}</p>
        ) : (
          <ul className="stats__rows">
            {slices.map((slice) => (
              <li className="stats__row" key={slice.key}>
                <span className="stats__rowLabel" title={labelOf(slice)}>
                  {labelOf(slice)}
                </span>
                <Bar count={slice.count} peak={peak} />
                <span className="stats__rowCount">
                  {t("stats.count", { count: slice.count })}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    )
  }

  /** 分布里的取值: 分类用库里的分类名(内容, 不翻译), 其余取值按 key 翻。 */
  const labelFor = (slice: StatSlice, kind: "category" | "aLevel" | "heritage" | "country") => {
    if (kind === "category") return slice.label
    if (slice.key === "unknown") return t("stats.unknown")
    if (kind === "heritage") {
      return slice.key in HERITAGE_LABEL ? t(HERITAGE_LABEL[slice.key as Heritage]) : slice.label
    }
    if (kind === "country") return slice.key === "CN" ? t("stats.domestic") : t("stats.overseas")
    return slice.label
  }

  // 境内/境外是这一页唯一一处需要在前端再算一步的地方: 后端给的是按 country_code
  // 分组, 而看板要的是「境内 vs 境外」两分。加总而不是重查一遍, 免得又多一套口径。
  const byCountry = data?.by_country ?? []
  const domestic = byCountry
    .filter((slice) => slice.key === "CN")
    .reduce((sum, slice) => sum + slice.count, 0)
  const overseas = byCountry
    .filter((slice) => slice.key !== "CN")
    .reduce((sum, slice) => sum + slice.count, 0)

  return (
    <main className="page">
      <h2 className="page__title">{t("router.stats.title")}</h2>
      <p className="page__subtitle">{t("router.stats.subtitle")}</p>

      {error ? (
        <StateMessage
          tone="error"
          title={t("stats.error.title")}
          detail={error}
          onRetry={reload}
        />
      ) : null}

      {data?.needs_attention ? (
        <StateMessage
          tone="error"
          title={t("stats.attention.title")}
          detail={t("stats.attention.detail")}
        />
      ) : null}

      {loading ? <StateMessage title={t("stats.loading")} /> : null}

      {!loading && data && data.attraction_total === 0 ? (
        <StateMessage title={t("stats.empty.title")} detail={t("stats.empty.detail")} />
      ) : null}

      {!loading && data && data.attraction_total > 0 ? (
        <>
          <ul className="stats__kpis">
            {[
              { label: t("stats.total"), value: data.attraction_total },
              { label: t("stats.images"), value: data.image_total },
              { label: t("stats.plans"), value: data.plan_total },
              { label: t("stats.provinces"), value: data.province_total },
            ].map((kpi) => (
              <li className="stats__kpi" key={kpi.label}>
                <span className="stats__kpiValue">{kpi.value}</span>
                <span className="stats__kpiLabel">{kpi.label}</span>
              </li>
            ))}
          </ul>

          <section className="section">
            <h3 className="section__title">{t("stats.scope.title")}</h3>
            <p className="stats__detail">
              {t("stats.scope.detail", { domestic, overseas })}
            </p>
            <ul className="stats__rows">
              {[
                { key: "domestic", label: t("stats.domestic"), count: domestic },
                { key: "overseas", label: t("stats.overseas"), count: overseas },
              ].map((row) => (
                <li className="stats__row" key={row.key}>
                  <span className="stats__rowLabel">{row.label}</span>
                  <Bar count={row.count} peak={Math.max(domestic, overseas)} />
                  <span className="stats__rowCount">
                    {t("stats.count", { count: row.count })}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {distribution(t("stats.category.title"), null, data.by_category, (slice) =>
            labelFor(slice, "category"),
          )}
          {distribution(
            t("stats.aLevel.title"),
            t("stats.aLevel.detail"),
            data.by_a_level,
            (slice) => labelFor(slice, "aLevel"),
          )}
          {distribution(
            t("stats.heritage.title"),
            t("stats.heritage.detail"),
            data.by_heritage,
            (slice) => labelFor(slice, "heritage"),
          )}

          <section className="section">
            <h3 className="section__title">{t("stats.sources.title")}</h3>
            <div className="stats__scroll">
              <table className="stats__table">
                <caption className="stats__caption">
                  {t("stats.sources.caption", {
                    total: data.attraction_total,
                    sources: data.sources.length,
                  })}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">{t("credits.table.source")}</th>
                    <th scope="col">{t("credits.table.license")}</th>
                    <th scope="col">{t("credits.table.attractions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sources.map((record) => (
                    <tr key={`${record.source}::${record.license}`}>
                      <td>
                        {record.source}
                        {record.share_alike ? (
                          <span className="stats__flag">{t("stats.shareAlike")}</span>
                        ) : null}
                      </td>
                      <td>{record.license}</td>
                      <td>{record.attraction_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="stats__more">
              {t("stats.sources.more")}{" "}
              <Link className="stats__link" to="/credits">
                {t("credits.title")}
              </Link>
            </p>
          </section>
        </>
      ) : null}
    </main>
  )
}

export default StatsPage
