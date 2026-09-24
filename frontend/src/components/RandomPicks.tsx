import React, { useCallback, useEffect, useRef, useState } from "react"

import { describeError, fetchRandomAttractions } from "../api/client"
import { useI18n } from "../i18n"
import type { Attraction } from "../types"
import AttractionCard from "./AttractionCard"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"
import "../styles/randomPicks.css"

/**
 * 打开首页时弹出来的三个随机地方。
 *
 * 为什么用 sessionStorage 记「弹过了」而不是每次进首页都弹: 从「全部景点」点回首页
 * 也算打开首页, 每一次都弹会把导航变成一串关窗动作。一次会话弹一次, 重开标签页或
 * 重开应用算新会话 —— 那时会真的再弹一次, 也正是「每次打开都不一样」的意思。
 *
 * 三条完全随机(后端不缓存), 与浏览记录无关。拿不到数据时**不弹**: 这是首页的
 * 锦上添花, 不该因为它没抽出来就给人一个报错弹窗。
 */
export const RANDOM_PICKS_SEEN = "have-a-trip:random-picks-seen"

const PICK_COUNT = 3

function alreadySeen(): boolean {
  try {
    return window.sessionStorage.getItem(RANDOM_PICKS_SEEN) === "1"
  } catch {
    // 无痕模式下 sessionStorage 会直接抛: 当作没弹过, 本次照常弹
    return false
  }
}

function markSeen(): void {
  try {
    window.sessionStorage.setItem(RANDOM_PICKS_SEEN, "1")
  } catch {
    // 记不住只影响「同一次会话里会不会重复弹」, 不影响功能
  }
}

const RandomPicks = () => {
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
      className="randomPicks"
      role="presentation"
      onClick={(event) => {
        // 点遮罩关掉; 点弹窗内部不关
        if (event.target === event.currentTarget) setOpen(false)
      }}
    >
      <div
        className="randomPicks__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="random-picks-title"
      >
        <div className="randomPicks__head">
          <div>
            <h2 className="randomPicks__title" id="random-picks-title">
              {t("home.random.title")}
            </h2>
            <p className="randomPicks__lead">{t("home.random.lead")}</p>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="randomPicks__close"
            aria-label={t("home.random.close")}
            onClick={() => setOpen(false)}
          >
            ✕
          </button>
        </div>

        {loading ? <Loader /> : null}

        {!loading && failure !== null && items.length === 0 ? (
          <StateMessage
            title={t("home.random.error.title")}
            detail={describeError(failure, lang)}
            tone="error"
            onRetry={() => void pick()}
          />
        ) : null}

        {items.length > 0 ? (
          <ul className="randomPicks__grid">
            {items.map((attraction) => (
              <li key={attraction.slug}>
                <AttractionCard attraction={attraction} />
              </li>
            ))}
          </ul>
        ) : null}

        <div className="randomPicks__foot">
          <button
            type="button"
            className="randomPicks__reroll"
            onClick={() => void pick()}
            disabled={loading}
          >
            {t("home.random.reroll")}
          </button>
          <p className="randomPicks__note">{t("home.random.note")}</p>
        </div>
      </div>
    </div>
  )
}

export default RandomPicks
