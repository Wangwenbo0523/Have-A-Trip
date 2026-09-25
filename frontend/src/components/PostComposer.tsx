import React, { useState } from "react"

import { createPost, describeError, postRejection } from "../api/client"
import { useI18n, type Lang } from "../i18n"
import { localizedName } from "../lib/display"
import type { Attraction, ItineraryRejection } from "../types"
import AttractionPicker from "./AttractionPicker"
import StateMessage from "./StateMessage"

/** 正文上限。与后端 schemas.py 的 POST_BODY_MAX 一致 —— 两边都拦, 前端拦是为了即时反馈。 */
export const BODY_MAX = 500

/** 署名存在本地, 下次进来直接填好; 真正记住它的是后端的 app_user.nickname。 */
const NICKNAME_KEY = "have-a-trip.nickname"

function readNickname(): string {
  try {
    return window.localStorage.getItem(NICKNAME_KEY) ?? ""
  } catch {
    return ""
  }
}

function saveNickname(name: string): void {
  try {
    if (name) window.localStorage.setItem(NICKNAME_KEY, name)
  } catch {
    // 存不下就算了, 不影响这次发布
  }
}

/** 与行程那条路同款: 后端只给 ISO, 显示成「9/26 00:00」比一串时间戳有用。 */
function formatRetry(iso: string, lang: Lang, fallback: string): string {
  const when = new Date(iso)
  if (Number.isNaN(when.getTime())) return fallback
  return when.toLocaleString(lang === "en" ? "en-US" : "zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

interface PostComposerProps {
  /** 全库已发布景点, 用来挂景点 */
  options: Attraction[]
  /** 从详情页过来时先挂好那个景点 */
  presetSlug?: string
  onPosted: () => void
}

/**
 * 发一条动态。
 *
 * 三件事按顺序说清楚: 写什么(正文) -> 署名谁(可选) -> 挂在哪个景点(可选)。
 * 没有账号, 也没有图片上传 —— 一期用「挂景点」代替晒图(见 docs/PLAN.md 的 v4.0)。
 */
const PostComposer = ({ options, presetSlug = "", onPosted }: PostComposerProps) => {
  const { t, lang } = useI18n()
  const [body, setBody] = useState("")
  const [nickname, setNickname] = useState(readNickname)
  const [slug, setSlug] = useState(presetSlug)
  const [busy, setBusy] = useState(false)
  const [rejection, setRejection] = useState<ItineraryRejection | null>(null)
  const [error, setError] = useState("")

  const trimmed = body.trim()

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!trimmed || busy) return
    setBusy(true)
    setError("")
    setRejection(null)
    try {
      await createPost({
        body: trimmed,
        nickname: nickname.trim() || undefined,
        attraction_slug: slug || undefined,
      })
      saveNickname(nickname.trim())
      // 正文清掉, 署名与景点留着: 连发两条同一个地方是常见用法
      setBody("")
      onPosted()
    } catch (err) {
      const blocked = postRejection(err)
      if (blocked) setRejection(blocked)
      else setError(describeError(err, lang))
    } finally {
      setBusy(false)
    }
  }

  const retryDetail = (blocked: ItineraryRejection) => {
    const when = formatRetry(blocked.retry_after, lang, t("posts.retry.fallback"))
    return blocked.limit
      ? t("posts.rejected.withLimit", { limit: blocked.limit, when })
      : t("posts.rejected.withoutLimit", { when })
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label className="composer__label" htmlFor="post-body">
        {t("posts.composer.label")}
      </label>
      <textarea
        id="post-body"
        className="composer__input"
        value={body}
        onChange={(event) => setBody(event.target.value)}
        placeholder={t("posts.composer.placeholder")}
        maxLength={BODY_MAX}
        rows={4}
      />
      <p className="composer__counter">
        {t("posts.composer.counter", { used: body.length, max: BODY_MAX })}
      </p>

      <div className="composer__row">
        <label className="composer__nickname" htmlFor="post-nickname">
          {t("posts.composer.nickname")}
          <input
            id="post-nickname"
            type="text"
            value={nickname}
            onChange={(event) => setNickname(event.target.value)}
            placeholder={t("posts.composer.nicknamePlaceholder")}
            maxLength={24}
          />
        </label>
        <button className="composer__submit" type="submit" disabled={busy || !trimmed}>
          {busy ? t("posts.composer.busy") : t("posts.composer.submit")}
        </button>
      </div>

      {/* 挂景点是**可选**的: 不选就是纯文字, 所以列表里第一位是"不挂" */}
      <div className="composer__spot">
        <AttractionPicker
          id="post-spot"
          label={t("posts.composer.spot")}
          value={slug}
          options={options}
          onChange={setSlug}
        />
        {slug ? (
          <button type="button" className="composer__unspot" onClick={() => setSlug("")}>
            {t("posts.composer.unspot")}
          </button>
        ) : null}
      </div>

      {rejection ? (
        <StateMessage title={t("posts.rejected.title")} detail={retryDetail(rejection)} tone="error" />
      ) : null}
      {!rejection && error ? (
        <StateMessage title={t("posts.error.title")} detail={error} tone="error" />
      ) : null}
    </form>
  )
}

export default PostComposer
