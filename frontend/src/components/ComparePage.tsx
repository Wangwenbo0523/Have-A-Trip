import React, { useEffect, useMemo } from "react"
import { useSearchParams } from "react-router-dom"

import { fetchAttraction, fetchAttractions } from "../api/client"
import { useApi } from "../hooks/useApi"
import { useI18n, type MessageKey } from "../i18n"
import { localizedName, namesFor } from "../lib/display"
import { HERITAGE_TEXT } from "../lib/grade"
import type { Attraction, AttractionDetail } from "../types"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"

import "../styles/compare.css"

/**
 * 后端 `max_page_size` 是 100 —— 请求再大也会被压回这个数, 所以一次取不完整个库。
 * 这里跟 backend/app/config.py 对齐, 只用来减少往返次数, 不承担正确性。
 */
const PAGE_SIZE = 100

/**
 * 取回**全部**已发布景点。
 *
 * 对比页的下拉必须能选到全库。早先只取第一页, 于是排在第 100 名之后的景点既不在下拉里,
 * 别人发来的 `?a=<slug>` 链接还会被 known() 判成「已下架」, 静默换成别的景点 ——
 * 发出去的一条对比链接会悄悄变成另一条对比。
 *
 * 页数按响应里的 `size` 推, 而不是按上面请求的值: 服务端有权把 size 压小。
 */
async function fetchAllAttractions(): Promise<Attraction[]> {
  const first = await fetchAttractions({ page: 1, size: PAGE_SIZE, sort: "name" })
  const pages = first.size > 0 ? Math.ceil(first.total / first.size) : 1
  if (pages <= 1) return first.items

  const rest = await Promise.all(
    Array.from({ length: pages - 1 }, (_, index) =>
      fetchAttractions({ page: index + 2, size: PAGE_SIZE, sort: "name" }),
    ),
  )
  return [...first.items, ...rest.flatMap((page) => page.items)]
}

interface CompareRow {
  label: MessageKey
  left: string
  right: string
  /** 只有评分有客观高低, 其余字段没有 —— 见 rowsFor 里的说明 */
  better?: "left" | "right"
}

/**
 * 景点对比。
 *
 * 选中的两个景点记在 URL 查询串里(?a=...&b=...), 不放组件状态 —— 对比结果是一份可以
 * 直接发给别人的链接, 刷新一下也不该把挑好的两个白扔掉。
 *
 * 数据全走已有的 /attractions 与 /attractions/{slug}: 对比只是同一份档案换一种摆法,
 * 后端不需要为它开新接口, 前端也不做任何换算 —— 换算过的数字就不再是档案里的数字了。
 */
const ComparePage = () => {
  const { t, lang } = useI18n()
  const [params, setParams] = useSearchParams()

  const {
    data: items,
    loading: listLoading,
    error: listError,
    reload: reloadList,
  } = useApi(fetchAllAttractions, [])
  const options = useMemo(() => items ?? [], [items])

  const leftSlug = params.get("a") ?? ""
  const rightSlug = params.get("b") ?? ""
  const known = (slug: string) => options.some((item) => item.slug === slug)

  /**
   * 补默认选择。三种情况都要兜: 首次进来没带参数、链接里的 slug 已经被下架、
   * 只带了半边。用 replace 而不是 push —— 自动补的这一下不该在后退历史里留一步。
   */
  useEffect(() => {
    if (options.length < 2) return
    if (known(leftSlug) && known(rightSlug)) return
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        // 另一个位置已经占了这个 slug 就换下一个, 免得补出一个「两边一样」的死胡同
        const spare = (taken: string) =>
          options[0].slug !== taken ? options[0].slug : options[1].slug
        if (!known(leftSlug)) next.set("a", spare(known(rightSlug) ? rightSlug : ""))
        if (!known(rightSlug)) next.set("b", spare(known(leftSlug) ? leftSlug : next.get("a") ?? ""))
        return next
      },
      { replace: true },
    )
    // known() 每次渲染都是新函数, 所以不进依赖; 它只是 options 的派生, options 在依赖里
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options, leftSlug, rightSlug, setParams])

  const ready = Boolean(leftSlug && rightSlug && leftSlug !== rightSlug)
  /**
   * 取回的两份档案按 slug 存成一张表, 而不是按位置存成数组。
   *
   * 这样「对调两边」就只是换个顺序读同一张表 —— 依赖里放的是**排序后的 slug 对**,
   * 集合没变就不会重新请求。按位置存的话, 对调会让依赖变化, 白白再取两个一模一样的
   * 档案回来。
   */
  const slugPair = [leftSlug, rightSlug].sort().join("|")
  const { data: profiles, loading, error, reload } = useApi(
    () =>
      ready
        ? Promise.all([fetchAttraction(leftSlug), fetchAttraction(rightSlug)]).then(
            ([first, second]) =>
              ({ [first.slug]: first, [second.slug]: second }) as Record<string, AttractionDetail>,
          )
        : Promise.resolve(null),
    [ready, slugPair],
  )

  const pick = (side: "a" | "b") => (event: React.ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.set(side, value)
      return next
    })
  }

  const swap = () => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      const left = next.get("a")
      next.set("a", next.get("b") ?? "")
      next.set("b", left ?? "")
      return next
    })
  }

  const rowsFor = (left: AttractionDetail, right: AttractionDetail): CompareRow[] => {
    const place = (item: AttractionDetail) =>
      [item.city, item.province].filter(Boolean).join(" · ") || t("card.location.tbd")

    const rating = (item: AttractionDetail) =>
      item.rating_count > 0
        ? t("card.rating", { avg: item.rating_avg.toFixed(1), count: item.rating_count })
        : t("card.rating.none")

    /** 与卡片同一条口径: 库里没有币种字段, 所以只对境内写人民币符号。 */
    const price = (item: AttractionDetail) => {
      if (item.ticket_price === null) return t("card.price.tbd")
      if (item.ticket_price === 0) return t("card.price.free")
      return item.country_code === "CN" ? `¥${item.ticket_price}` : t("card.price.ticketed")
    }

    const hours = (item: AttractionDetail) =>
      item.suggested_hours === null
        ? t("detail.tbd")
        : t("detail.hours", { hours: item.suggested_hours })

    const level = (item: AttractionDetail) =>
      item.a_level ? t("grade.aLevel", { level: item.a_level }) : t("detail.tbd")

    const heritage = (item: AttractionDetail) =>
      item.heritage ? t(HERITAGE_TEXT[item.heritage].full) : t("detail.tbd")

    /**
     * 只有评分能标「更高」。票价低不等于更好(可能内容也少), 游玩时长长不等于更好
     * (可能只是走得慢), 季节更是各有所好 —— 那些字段标一个「更优」就是替用户下判断。
     * 两边都没人评分时也不比, 0 分不是「低分」而是「还没有评分」。
     */
    const better: "left" | "right" | undefined =
      left.rating_count > 0 && right.rating_count > 0 && left.rating_avg !== right.rating_avg
        ? left.rating_avg > right.rating_avg
          ? "left"
          : "right"
        : undefined

    return [
      { label: "compare.row.category", left: left.category.name, right: right.category.name },
      { label: "compare.row.city", left: place(left), right: place(right) },
      { label: "compare.row.rating", left: rating(left), right: rating(right), better },
      { label: "compare.row.price", left: price(left), right: price(right) },
      { label: "compare.row.hours", left: hours(left), right: hours(right) },
      { label: "compare.row.aLevel", left: level(left), right: level(right) },
      { label: "compare.row.heritage", left: heritage(left), right: heritage(right) },
      {
        label: "compare.row.season",
        left: left.best_season || t("detail.tbd"),
        right: right.best_season || t("detail.tbd"),
      },
      {
        label: "compare.row.tags",
        left: left.tags.map((tag) => tag.name).join(" / ") || t("detail.tbd"),
        right: right.tags.map((tag) => tag.name).join(" / ") || t("detail.tbd"),
      },
    ]
  }

  // 请求在飞的时候 profiles 里还是上一对, 缺了任何一边就什么都不渲染 —— 宁可不显示,
  // 也不把上一对的结果冒充这一对
  const leftItem = profiles?.[leftSlug] ?? null
  const rightItem = profiles?.[rightSlug] ?? null

  const picker = (side: "a" | "b", value: string, label: string) => (
    <label className="compare__pick">
      <span className="compare__pickLabel">{label}</span>
      <select className="compare__select" value={value} onChange={pick(side)}>
        {options.map((item) => (
          <option key={item.slug} value={item.slug}>
            {localizedName(lang, item)}
          </option>
        ))}
      </select>
    </label>
  )

  return (
    <main className="page">
      <h2 className="page__title">{t("router.compare.title")}</h2>
      <p className="page__subtitle">{t("router.compare.subtitle")}</p>

      {listError ? (
        <StateMessage
          tone="error"
          title={t("compare.error.title")}
          detail={listError}
          onRetry={reloadList}
        />
      ) : null}

      {listLoading ? <Loader /> : null}

      {/* 少于两个已发布景点时没什么可比的, 直接说清原因, 不摆两个空下拉框 */}
      {!listLoading && !listError && options.length < 2 ? (
        <StateMessage title={t("compare.empty.title")} detail={t("compare.empty.detail")} />
      ) : null}

      {!listLoading && options.length >= 2 ? (
        <div className="compare__pickers">
          {picker("a", leftSlug, t("compare.sideA"))}
          <button className="compare__swap" type="button" onClick={swap}>
            {t("compare.swap")}
          </button>
          {picker("b", rightSlug, t("compare.sideB"))}
        </div>
      ) : null}

      {ready ? null : (
        leftSlug && rightSlug ? <StateMessage tone="error" title={t("compare.same")} /> : null
      )}

      {ready && loading ? <Loader /> : null}

      {ready && error ? (
        <StateMessage
          tone="error"
          title={t("compare.error.title")}
          detail={error}
          onRetry={reload}
        />
      ) : null}

      {leftItem && rightItem ? (
        <>
          <div className="compare__scroll">
            <table className="compare__table">
              <thead>
                <tr>
                  <th scope="col">{t("compare.row")}</th>
                  <th scope="col">{namesFor(lang, leftItem).title}</th>
                  <th scope="col">{namesFor(lang, rightItem).title}</th>
                </tr>
              </thead>
              <tbody>
                {rowsFor(leftItem, rightItem).map((row) => (
                  <tr key={row.label}>
                    <th scope="row">{t(row.label)}</th>
                    <td className={row.better === "left" ? "compare__cell is-better" : "compare__cell"}>
                      {row.left}
                      {row.better === "left" ? (
                        <span className="compare__better">{t("compare.better")}</span>
                      ) : null}
                    </td>
                    <td className={row.better === "right" ? "compare__cell is-better" : "compare__cell"}>
                      {row.right}
                      {row.better === "right" ? (
                        <span className="compare__better">{t("compare.better")}</span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="compare__note">{t("compare.note")}</p>
        </>
      ) : null}
    </main>
  )
}

export default ComparePage
