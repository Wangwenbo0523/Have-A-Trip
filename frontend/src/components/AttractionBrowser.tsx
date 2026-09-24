import React, { useEffect, useState } from "react"

import { fetchAttractions } from "../api/client"
import { useApi } from "../hooks/useApi"
import { useDebouncedValue } from "../hooks/useDebouncedValue"
import type { PageQuery } from "../types"
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

interface AttractionBrowserProps {
  /** 分类 slug, 不传就是全部景点 */
  category?: string
  pageSize?: number
}

/** 景点列表: 关键字搜索 + 排序 + 分页。首页、分类页、全部景点页共用。 */
const AttractionBrowser = ({ category, pageSize = 12 }: AttractionBrowserProps) => {
  const [keyword, setKeyword] = useState("")
  const [sort, setSort] = useState<SortKey>("rating")
  const [page, setPage] = useState(1)
  const debouncedKeyword = useDebouncedValue(keyword, 300)

  // 换分类 / 换关键字 / 换排序之后原页码可能越界, 一律回到第一页
  useEffect(() => {
    setPage(1)
  }, [category, debouncedKeyword, sort])

  const { data, loading, error, reload } = useApi(
    () => fetchAttractions({ page, size: pageSize, category, q: debouncedKeyword, sort }),
    [page, pageSize, category, debouncedKeyword, sort],
  )

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1

  return (
    <div className="browser">
      <div className="browser__toolbar">
        <SearchBox
          value={keyword}
          onChange={setKeyword}
          placeholder="搜索景点名称或简介…"
        />
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
          detail={
            debouncedKeyword
              ? `没有找到和「${debouncedKeyword}」相关的景点, 换个词试试`
              : "这里还没有已发布的景点, 先执行 db/seed/seed.sql 导入种子数据"
          }
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
    </div>
  )
}

export default AttractionBrowser
