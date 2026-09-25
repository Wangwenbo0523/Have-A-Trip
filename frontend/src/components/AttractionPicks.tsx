import React, { useCallback, useEffect, useRef, useState } from "react"

import { describeError, fetchNearbyAttractions } from "../api/client"
import { useI18n, type Translate } from "../i18n"
import type { NearbyResult } from "../types"
import AttractionCard from "./AttractionCard"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"
import "../styles/attractionPicks.css"

/**
 * 首页的「出去走走」—— 打开首页弹出三个景点, 尽量挑近的。
 *
 * 「近」只到城市级: 后端按 IP 猜一次归属地, 同城不够用同省补, 再不够才全国随机。
 * 猜出来的位置**必须写在脸上** —— 标题、位置那一行与页脚都要说清依据(见 nearbyLine):
 * 不说清来源的「给你推荐」比随机更糟, 用户会以为我们真知道他在哪儿。
 * 产品本身不做地图与精确定位, 这一点在页脚与 README 里都写明。
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

/**
 * 位置那一行该说什么。四种, 每一种都是真话:
 *
 * - scope=city: 猜到你在 X, 三个都在附近
 * - scope=region: 猜到你在 X, 同城不够三个, 用省内的补齐了
 * - 其余但 located: 位置猜到了, 可这一带收录的不到三个, 剩下的是全国随机补的
 * - 没位置: 没认出你在哪儿, 三个都是全国随机
 *
 * 后端给的是**库内取值**(杭州市 / 浙江省), 直接显示即可, 前端不再自己拼「市」。
 * 单独一个函数是因为这段话最容易被改糊, 而它恰恰是这一块唯一能说明依据的地方。
 */
export function nearbyLine(result: NearbyResult, t: Translate): string {
  // scope=region 说的是「省内的补齐了」, 这里就得报省份 —— 报城市会自相矛盾
  // (「猜你在杭州市。同城不够三个」), 而这两种写法差一个字, 极容易写错
  if (result.scope === "city" && result.city) {
    return t("home.picks.nearCity", { city: result.city })
  }
  if (result.scope === "region" && (result.region ?? result.city)) {
    return t("home.picks.nearRegion", { region: result.region ?? result.city })
  }
  const place = result.city ?? result.region
  if (place) return t("home.picks.mixed", { place })
  return t("home.picks.unknown")
}

const AttractionPicks = () => {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const [result, setResult] = useState<NearbyResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [failure, setFailure] = useState<unknown>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const items = result?.items ?? []

  const pick = useCallback(async () => {
    setLoading(true)
    setFailure(null)
    try {
      const data = await fetchNearbyAttractions(PICK_COUNT)
      setResult(data)
      // 库是空的就别弹一个空窗出来
      if (data.items.length > 0) setOpen(true)
    } catch (error) {
      // 换一批失败时保留上一次的三个: 总比把已经看到的东西撤掉强
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
            {result ? (
              <p className="attractionPicks__where">{nearbyLine(result, t)}</p>
            ) : null}
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
