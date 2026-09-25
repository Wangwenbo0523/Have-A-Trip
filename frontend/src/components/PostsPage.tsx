import React, { useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { deletePost, describeError, fetchPosts, fetchPostsByAttraction } from "../api/client"
import { useApi } from "../hooks/useApi"
import { useI18n } from "../i18n"
import { fetchAllAttractions } from "../lib/attractions"
import { localizedName } from "../lib/display"
import type { Post } from "../types"
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
 * 这里**没有**账号、没有定位、没有图片: 匿名身份只是 localStorage 里一个随机串。
 */
const PostsPage = () => {
  const { t, lang } = useI18n()
  const [params, setParams] = useSearchParams()
  const [onlyMine, setOnlyMine] = useState(false)
  const [failure, setFailure] = useState("")

  const attraction = params.get("attraction") ?? ""
  const { data, loading, error, reload } = useApi(
    () => (attraction ? fetchPostsByAttraction(attraction, 20) : fetchPosts({ onlyMine })),
    [attraction, onlyMine],
  )
  // 景点选择器的候选: 全库已发布景点, 与对比页共用同一个加载器
  const spots = useApi(fetchAllAttractions, [])

  const filtered = useMemo(
    () => (attraction ? (spots.data ?? []).find((item) => item.slug === attraction) : undefined),
    [attraction, spots.data],
  )

  const remove = async (post: Post) => {
    setFailure("")
    try {
      await deletePost(post.id)
      reload()
    } catch (err) {
      setFailure(describeError(err, lang))
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
          items={data.items}
          onDelete={remove}
          empty={
            onlyMine
              ? { title: t("posts.emptyMine.title"), detail: t("posts.emptyMine.detail") }
              : { title: t("posts.empty.title"), detail: t("posts.empty.detail") }
          }
        />
      ) : null}

      {failure ? (
        <StateMessage title={t("posts.error.title")} detail={failure} tone="error" />
      ) : null}

      {data ? <p className="posts__disclaimer">{data.disclaimer}</p> : null}
    </section>
  )
}

export default PostsPage
