import React, { useEffect, useState } from "react"

import { fetchAttractions } from "../api/client"
import { useApi } from "../hooks/useApi"
import { useDebouncedValue } from "../hooks/useDebouncedValue"
import { useI18n, type MessageKey } from "../i18n"
import type { GradeFilter, PageQuery } from "../types"
import AiSearchPanel from "./AiSearchPanel"
import AttractionList from "./AttractionList"
import SearchBox from "./SearchBox"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"

type SortKey = NonNullable<PageQuery["sort"]>

/**
 * 排序按钮的文字是界面文案, 所以这里只存 **文案键**, 渲染时按当前语种查表 ——
 * 模块级常量存不了语种, 写死中文串的话英文界面下按钮不会跟着变。
 */
const SORTS: { value: SortKey; labelKey: MessageKey }[] = [
  { value: "rating", labelKey: "browser.sort.rating" },
  { value: "newest", labelKey: "browser.sort.newest" },
  { value: "name", labelKey: "browser.sort.name" },
]

/**
 * 等级筛选。A 级(中国景区质量等级)与世界遗产是两套刻度, 所以在同一组按钮里各占
 * 一项, 空字符串表示「全部」。
 *
 * 5A / 4A / 3A 两种语种下写法相同, 但仍然走文案表: 将来英文界面想写成
 * “5A (China)” 只需要改文案, 不用动这个数组。
 */
const GRADES: { value: GradeFilter | ""; labelKey: MessageKey }[] = [
  { value: "", labelKey: "browser.grade.all" },
  { value: "5A", labelKey: "browser.grade.a5" },
  { value: "4A", labelKey: "browser.grade.a4" },
  { value: "3A", labelKey: "browser.grade.a3" },
  { value: "heritage", labelKey: "browser.grade.heritage" },
]

interface AttractionBrowserProps {
  /** 分类 slug, 不传就是全部景点 */
  category?: string
  pageSize?: number
}

/** 景点列表: 关键字搜索 + 排序 + 分页。首页、分类页、全部景点页共用。 */
const AttractionBrowser = ({ category, pageSize = 12 }: AttractionBrowserProps) => {
  const { t } = useI18n()
  const [keyword, setKeyword] = useState("")
  const [sort, setSort] = useState<SortKey>("rating")
  const [grade, setGrade] = useState<GradeFilter | "">("")
  const [page, setPage] = useState(1)
  const [aiActive, setAiActive] = useState(false)
  const debouncedKeyword = useDebouncedValue(keyword, 300)

  // 换分类 / 换关键字 / 换排序 / 换等级之后原页码可能越界, 一律回到第一页
  useEffect(() => {
    setPage(1)
  }, [category, debouncedKeyword, sort, grade])

  const { data, loading, error, reload } = useApi(
    () =>
      fetchAttractions({
        page,
        size: pageSize,
        category,
        q: debouncedKeyword,
        sort,
        // 空串不是合法取值, 不筛选时干脆不带这个参数
        grade: grade || undefined,
      }),
    [page, pageSize, category, debouncedKeyword, sort, grade],
  )

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1

  /** 空态文案要能区分「筛没了」和「库是空的」, 否则会误导人去跑种子脚本。 */
  const emptyDetail = () => {
    if (debouncedKeyword) return t("browser.empty.keyword", { keyword: debouncedKeyword })
    if (grade) return t("browser.empty.grade")
    return t("browser.empty.default")
  }

  return (
    <div className="browser">
      {/*
        AI 一句话检索只在「全部景点」页出现 —— 分类页自己已经限定了分类,
        再叠一个跨分类的自然语言检索只会让人困惑。
        后端说不可用(默认配置)时这个组件整个不渲染, 页面与以前完全一样。
      */}
      {category ? null : <AiSearchPanel onActiveChange={setAiActive} />}

      {/* AI 结果在显示时, 把下面这条普通检索收起来: 两份列表同时出现分不清哪份是目标 */}
      {aiActive ? null : (
        <>
          <div className="browser__toolbar">
            <SearchBox
              value={keyword}
              onChange={setKeyword}
              placeholder={t("search.placeholder")}
            />
            <div className="browser__controls">
              <div className="browser__grades" role="group" aria-label={t("browser.grade.aria")}>
                {GRADES.map((item) => (
                  <button
                    key={item.value || "all"}
                    type="button"
                    className={`browser__sort${grade === item.value ? " is-active" : ""}`}
                    aria-pressed={grade === item.value}
                    onClick={() => setGrade(item.value)}
                  >
                    {t(item.labelKey)}
                  </button>
                ))}
              </div>
              <div className="browser__sorts" role="group" aria-label={t("browser.sort.aria")}>
                {SORTS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    className={`browser__sort${sort === item.value ? " is-active" : ""}`}
                    aria-pressed={sort === item.value}
                    onClick={() => setSort(item.value)}
                  >
                    {t(item.labelKey)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {loading ? <Loader /> : null}

          {!loading && error ? (
            <StateMessage
              title={t("browser.error.title")}
              detail={error}
              tone="error"
              onRetry={reload}
            />
          ) : null}

          {!loading && !error && data && data.items.length === 0 ? (
            <StateMessage title={t("browser.empty.title")} detail={emptyDetail()} />
          ) : null}

          {!loading && !error && data && data.items.length > 0 ? (
            <>
              <AttractionList attractions={data.items} />
              <div className="browser__pager">
                <button type="button" disabled={page <= 1} onClick={() => setPage((n) => n - 1)}>
                  {t("browser.pager.prev")}
                </button>
                <span>
                  {t("browser.pager.status", {
                    page: data.page,
                    totalPages,
                    count: data.total,
                  })}
                </span>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((n) => n + 1)}
                >
                  {t("browser.pager.next")}
                </button>
              </div>
            </>
          ) : null}
        </>
      )}
    </div>
  )
}

export default AttractionBrowser
