import React, { useState } from "react"
import { Link } from "react-router-dom"

import { useI18n, type Lang } from "../i18n"
import { localizedName } from "../lib/display"
import type { Post } from "../types"
import StateMessage from "./StateMessage"

/**
 * 后端给的是带时区的 ISO 串。显示成"9/25 14:30" —— 动态是**公开内容**,
 * 精确到秒没有意义, 相对时间(几分钟前)又要处理跨语种的复数, 不值得。
 */
function formatPostedAt(iso: string, lang: Lang, fallback: string): string {
  const when = new Date(iso)
  if (Number.isNaN(when.getTime())) return fallback
  return when.toLocaleString(lang === "en" ? "en-US" : "zh-CN", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

interface PostListProps {
  items: Post[]
  /** 给了才显示删除按钮(只有自己的动态会显示), 见下面的 post.mine */
  onDelete?: (post: Post) => void
  /** 空列表时的说法。动态区与详情页那两块的空态不是同一句话 */
  empty: { title: string; detail?: string }
}

/**
 * 动态列表。动态区与景点详情页共用同一个渲染 —— 同一批数据在哪儿都该长一个样。
 *
 * 正文是用户写的**内容**, 原样显示不翻译; 排版上保留换行(见 styles/posts.css 的
 * white-space: pre-wrap), 否则用户打的分段会挤成一坨。
 */
const PostList = ({ items, onDelete, empty }: PostListProps) => {
  const { t, lang } = useI18n()
  // 删除先问一次再删。就地二段确认, 不用 window.confirm:
  // 那个弹窗在测试里要打桩、在移动端长得也不像这个应用
  const [confirming, setConfirming] = useState<number | null>(null)

  if (items.length === 0) {
    return <StateMessage title={empty.title} detail={empty.detail} />
  }

  return (
    <ul className="posts__list">
      {items.map((post) => (
        <li className="post" key={post.id}>
          <div className="post__head">
            <span className="post__author">{post.author.name}</span>
            <time className="post__time" dateTime={post.created_at}>
              {formatPostedAt(post.created_at, lang, t("posts.time.unknown"))}
            </time>
          </div>

          <p className="post__body">{post.body}</p>

          {post.attraction ? (
            post.attraction.slug ? (
              <Link className="post__spot" to={"/attraction/" + post.attraction.slug}>
                {t("posts.on", { name: localizedName(lang, post.attraction) })}
              </Link>
            ) : (
              // 景点下架了: 名字快照还在, 但没有能打开的页面
              <span className="post__spot post__spot--gone">
                {t("posts.on", { name: post.attraction.name })}
              </span>
            )
          ) : null}

          {onDelete && post.mine ? (
            confirming === post.id ? (
              <span className="post__actions">
                <button
                  type="button"
                  className="post__delete post__delete--confirm"
                  onClick={() => {
                    setConfirming(null)
                    onDelete(post)
                  }}
                >
                  {t("posts.delete.confirm")}
                </button>
                <button
                  type="button"
                  className="post__cancel"
                  onClick={() => setConfirming(null)}
                >
                  {t("posts.delete.cancel")}
                </button>
              </span>
            ) : (
              <button
                type="button"
                className="post__delete"
                onClick={() => setConfirming(post.id)}
              >
                {t("posts.delete")}
              </button>
            )
          ) : null}
        </li>
      ))}
    </ul>
  )
}

export default PostList
