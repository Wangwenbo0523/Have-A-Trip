import React, { useCallback, useEffect, useRef, useState } from "react"

import { describeError, fetchRandomAttractions } from "../api/client"
import { useI18n } from "../i18n"
import type { Attraction } from "../types"
import AttractionCard from "./AttractionCard"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"
import "../styles/attractionPicks.css"

/**
 * 首页的「景区推荐」—— 打开首页时弹出三个景区。
 *
 * 名字叫推荐, 机制是**随机抽取**(后端不缓存), 与浏览记录无关: 首页最先看到的那一块
 * 不该是「因为你昨天点过什么」, 而是每次都不一样的一扇门。所以标题下与页脚都写明了
 * 「随机抽取」—— 叫推荐却不说明来源, 就成了一个说不清依据的推荐位。
 *
 * 为什么用 sessionStorage 记「弹过了」而不是每次进首页都弹: 从「全部景点」点回首页
 * 也算打开首页, 每一次都弹会把导航变成一串关窗动作。一次会话弹一次, 重开标签页或
 * 重开应用算新会话 —— 那时会真的再弹一次, 也正是「每次打开都不一样」的意思。
 *
 * 拿不到数据时**不弹**: 这是首页的锦上添花, 不该因为它没抽出来就给人一个报错弹窗。
 */
export const PICKS_SEEN_KEY = "have-a-trip:attraction-picks-seen"

const PICK_COUNT = 3

function alreadySeen(): boolean {
  try {
    return window.sessionStorage.getItem(PICKS_SEEN_KEY) === "1"
  } catch {
    // 无痕模式下 sessionStorage 会直接抛: 当作没弹过, 本次照常弹
    return false
  }
}

function markSeen(): void {
  try {
    window.sessionStorage.setItem(PICKS_SEEN_KEY, "1")
  } catch {
    // 记不住只影响「同一次会话里会不会重复弹」, 不影响功能
  }
}

const AttractionPicks = () => {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Attraction[]>([])
  const [loading, setLoading] = useState(false)
  const [failure, setFailure] = useState<unknown>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  const pick = useCallback(async () => {
    setLoading(true)
    setFailure(null)
    try {
      const data = await fetchRandomAttractions(PICK_COUNT)
      setItems(data)
      // 库是空的就别弹一个空窗出来
      if (data.length > 0) setOpen(true)
    } catch (error) {
      setFailure(error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (alreadySeen()) return
    // 先记账再请求: 抽失败也不该在下一次进首页时反复重试
    markSeen()
    void pick()
  }, [pick])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKeyDown)
    // 焦点移到关闭按钮: 键盘与读屏用户一进来就有明确的出口
    closeRef.current?.focus()
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [open])

  if (!open) return null

  return (
    <div
      className="attractionPicks"
      role="presentation"
      onClick={(event) => {
        // 点遮罩关掉; 点弹窗内部不关
        if (event.target === event.currentTarget) setOpen(false)
      }}
    >
      <div
        className="attractionPicks__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="attraction-picks-title"
      >
        <div className="attractionPicks__head">
          <div>
            <h2 className="attractionPicks__title" id="attraction-picks-title">
              {t("home.picks.title")}
            </h2>
            <p className="attractionPicks__lead">{t("home.picks.lead")}</p>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="attractionPicks__close"
            aria-label={t("home.picks.close")}
            onClick={() => setOpen(false)}
          >
            ✕
          </button>
        </div>

        {loading ? <Loader /> : null}

        {!loading && failure !== null && items.length === 0 ? (
          <StateMessage
            title={t("home.picks.error.title")}
            detail={describeError(failure, lang)}
            tone="error"
            onRetry={() => void pick()}
          />
        ) : null}

        {items.length > 0 ? (
          <ul className="attractionPicks__grid">
            {items.map((attraction) => (
              <li key={attraction.slug}>
                <AttractionCard attraction={attraction} />
              </li>
            ))}
          </ul>
        ) : null}

        <div className="attractionPicks__foot">
          <button
            type="button"
            className="attractionPicks__reroll"
            onClick={() => void pick()}
            disabled={loading}
          >
            {t("home.picks.reroll")}
          </button>
          <p className="attractionPicks__note">{t("home.picks.note")}</p>
        </div>
      </div>
    </div>
  )
}

export default AttractionPicks
