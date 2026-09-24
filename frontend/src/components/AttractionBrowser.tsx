import React, { useEffect, useState } from "react"

import { fetchAttractions } from "../api/client"
import { useApi } from "../hooks/useApi"
import { useDebouncedValue } from "../hooks/useDebouncedValue"
import type { GradeFilter, PageQuery } from "../types"
import AiSearchPanel from "./AiSearchPanel"
import AttractionList from "./AttractionList"
import SearchBox from "./SearchBox"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"

type SortKey = NonNullable<PageQuery["sort"]>

const SORTS: { value: SortKey; label: string }[] = [
  { value: "rating", label: "评分优先" },
  { value: "newest", label: "最新收录" },
  { value: "name", label: "按名称" },
]

/**
 * 等级筛选。A 级(中国景区质量等级)与世界遗产是两套刻度, 所以在同一组按钮里各占
 * 一项, 空字符串表示「全部」。
 */
const GRADES: { value: GradeFilter | ""; label: string }[] = [
  { value: "", label: "全部" },
  { value: "5A", label: "5A" },
  { value: "4A", label: "4A" },
  { value: "3A", label: "3A" },
  { value: "heritage", label: "世界遗产" },
]

/** 空态文案要能区分「筛没了」和「库是空的」, 否则会误导人去跑种子脚本。 */
const emptyDetail = (keyword: string, grade: GradeFilter | "") => {
  if (keyword) return `没有找到和「${keyword}」相关的景点, 换个词试试`
  if (grade) return "这个等级下暂时还没有已发布的景点"
  return "这里还没有已发布的景点, 先执行 db/seed/seed.sql 导入种子数据"
}

interface AttractionBrowserProps {
  /** 分类 slug, 不传就是全部景点 */
  category?: string
  pageSize?: number
}

/** 景点列表: 关键字搜索 + 排序 + 分页。首页、分类页、全部景点页共用。 */
const AttractionBrowser = ({ category, pageSize = 12 }: AttractionBrowserProps) => {
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
              placeholder="搜索景点名称或简介…"
            />
            <div className="browser__controls">
              <div className="browser__grades" role="group" aria-label="等级筛选">
                {GRADES.map((item) => (
                  <button
                    key={item.value || "all"}
                    type="button"
                    className={`browser__sort${grade === item.value ? " is-active" : ""}`}
                    aria-pressed={grade === item.value}
                    onClick={() => setGrade(item.value)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="browser__sorts" role="group" aria-label="排序方式">
                {SORTS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    className={`browser__sort${sort === item.value ? " is-active" : ""}`}
                    aria-pressed={sort === item.value}
                    onClick={() => setSort(item.value)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {loading ? <Loader /> : null}

          {!loading && error ? (
            <StateMessage
              title="景点加载失败"
              detail={error}
              tone="error"
              onRetry={reload}
            />
          ) : null}

          {!loading && !error && data && data.items.length === 0 ? (
            <StateMessage
              title="没有匹配的景点"
              detail={emptyDetail(debouncedKeyword, grade)}
            />
          ) : null}

          {!loading && !error && data && data.items.length > 0 ? (
            <>
              <AttractionList attractions={data.items} />
              <div className="browser__pager">
                <button type="button" disabled={page <= 1} onClick={() => setPage((n) => n - 1)}>
                  上一页
                </button>
                <span>
                  第 {data.page} / {totalPages} 页 · 共 {data.total} 个景点
                </span>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((n) => n + 1)}
                >
                  下一页
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