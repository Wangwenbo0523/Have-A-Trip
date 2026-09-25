import React, { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { deletePost, describeError, fetchPosts, fetchPostsByAttraction } from "../api/client"
import { useApi } from "../hooks/useApi"
import { useI18n } from "../i18n"
import { fetchAllAttractions } from "../lib/attractions"
import { localizedName } from "../lib/display"
import type { Post, PostPage } from "../types"
import PostComposer from "./PostComposer"
import PostList from "./PostList"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"
import "../styles/posts.css"

/**
 * 动态区。
 *
 * 一条接口两种用法: 看全站大家说了什么, 或者只看自己的(多带一个 device_id)。
 * ?attraction=<slug> 进来时只显示挂在这个景点下的 —— 景点详情页那个「大家在这儿
 * 说了什么」就是带着这个参数跳过来的。
 *
 * 列表按 id 倒序, 一页一页往后接: 「加载更多」拿上一页的 next_cursor 当游标再要一页。
 *
 * 这里**没有**账号、没有定位、没有图片: 匿名身份只是 localStorage 里一个随机串。
 */
const PostsPage = () => {
  const { t, lang } = useI18n()
  const [params, setParams] = useSearchParams()
  const [onlyMine, setOnlyMine] = useState(false)
  const [failure, setFailure] = useState("")
  // 「加载更多」翻出来的后续页与第一页分开存: 第一页归 useApi 管(重试、切筛选、发完
  // 刷新都走它), 这里只负责往后接。存整页而不是摊平的数组, 是为了拿到每页自己的
  // next_cursor: 一页还没翻时游标直接读第一页回的那个, 不必先进 state 再等一次 effect
  // —— 否则按钮会比列表晚一帧才出现, 而"晚一帧"在测试里就是竞态
  const [pages, setPages] = useState<PostPage[]>([])
  const [moreLoading, setMoreLoading] = useState(false)
  const [moreFailure, setMoreFailure] = useState("")

  const attraction = params.get("attraction") ?? ""
  const { data, loading, error, reload } = useApi(
    () => (attraction ? fetchPostsByAttraction(attraction, 20) : fetchPosts({ onlyMine })),
    [attraction, onlyMine],
  )
  // 景点选择器的候选: 全库已发布景点, 与对比页共用同一个加载器
  const spots = useApi(fetchAllAttractions, [])

  // 有后续页时游标以最后一页为准(它可能就是 null = 到底了), 否则用第一页回的那个
  const cursor = pages.length > 0 ? pages[pages.length - 1].next_cursor : (data?.next_cursor ?? null)

  // 第一页换了(刚发过、刚删过、切了筛选)就把翻出来的后续页丢掉, 游标也跟着重来:
  // 那时位置已经变了, 接着往下接只会把看过的东西再摆一遍
  useEffect(() => {
    setPages([])
    setMoreFailure("")
  }, [data])

  const filtered = useMemo(
    () => (attraction ? (spots.data ?? []).find((item) => item.slug === attraction) : undefined),
    [attraction, spots.data],
  )

  // 第一页是权威顺序: 后续页与它有重合时(刚删过一条, 后面整体上移一格)以第一页为准;
  // 后续页之间也逐个去过重, 免得同一页被接了两次
  const items = useMemo(() => {
    const head = data?.items ?? []
    const seen = new Set(head.map((item) => item.id))
    const merged = [...head]
    for (const page of pages) {
      for (const item of page.items) {
        if (seen.has(item.id)) continue
        seen.add(item.id)
        merged.push(item)
      }
    }
    return merged
  }, [data, pages])

  const remove = async (post: Post) => {
    setFailure("")
    try {
      await deletePost(post.id)
      // 名额在响应里, 所以删完从头拉一次; 已经翻出来的后续页会一并丢掉 —— 少了一条之后
      // 偏移与游标都会错位, 与其拼不如重来
      reload()
    } catch (err) {
      setFailure(describeError(err, lang))
    }
  }

  const loadMore = async () => {
    if (cursor === null || moreLoading) return
    setMoreLoading(true)
    setMoreFailure("")
    try {
      const next = await fetchPosts({
        attraction: attraction || undefined,
        onlyMine,
        before: cursor,
      })
      setPages((prev) => [...prev, next])
    } catch (err) {
      // 出错就停在原地: 游标没动, 再点一次还是这一页
      setMoreFailure(describeError(err, lang))
    } finally {
      setMoreLoading(false)
    }
  }

  return (
    <section className="posts">
      <PostComposer
        options={spots.data ?? []}
        presetSlug={attraction}
        onPosted={reload}
      />

      <div className="posts__bar">
        <label className="posts__mine" htmlFor="posts-only-mine">
          <input
            id="posts-only-mine"
            type="checkbox"
            checked={onlyMine}
            onChange={(event) => setOnlyMine(event.target.checked)}
          />
          {t("posts.mine.toggle")}
        </label>

        {filtered ? (
          <span className="posts__filter">
            {t("posts.filter.note", { name: localizedName(lang, filtered) })}
            <button type="button" className="posts__filterClear" onClick={() => setParams({})}>
              {t("posts.filter.clear")}
            </button>
          </span>
        ) : null}

        {/* 名额只对自己有意义: 没带身份时后端回 null, 那就不显示 */}
        {data && data.used_today !== null ? (
          <span className="posts__quota">
            {data.used_today >= data.daily_limit
              ? t("posts.quota.full", { limit: data.daily_limit })
              : t("posts.quota.left", { left: data.daily_limit - data.used_today })}
          </span>
        ) : null}
      </div>

      {loading ? <Loader /> : null}

      {!loading && error ? (
        <StateMessage title={t("posts.error.title")} detail={error} tone="error" onRetry={reload} />
      ) : null}

      {!loading && !error && data ? (
        <PostList
          items={items}
          onDelete={remove}
          empty={
            onlyMine
              ? { title: t("posts.emptyMine.title"), detail: t("posts.emptyMine.detail") }
              : { title: t("posts.empty.title"), detail: t("posts.empty.detail") }
          }
        />
      ) : null}

      {/* 还有更旧的就给按钮; 翻到底又说了一句「没有更多了」, 免得用户以为还能点 */}
      {!loading && !error && data && items.length > 0 ? (
        cursor !== null ? (
          <div className="posts__moreRow">
            <button
              type="button"
              className="posts__more"
              onClick={loadMore}
              disabled={moreLoading}
            >
              {moreLoading ? t("posts.more.busy") : t("posts.more")}
            </button>
            {moreFailure ? <span className="posts__moreError">{moreFailure}</span> : null}
          </div>
        ) : pages.length > 0 ? (
          <p className="posts__end">{t("posts.more.end")}</p>
        ) : null
      ) : null}

      {failure ? (
        <StateMessage title={t("posts.error.title")} detail={failure} tone="error" />
      ) : null}

      {data ? <p className="posts__disclaimer">{data.disclaimer}</p> : null}
    </section>
  )
}

export default PostsPage
