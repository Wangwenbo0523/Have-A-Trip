import React, { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"

import { createItinerary, describeError, fetchItinerary, itineraryRejection } from "../api/client"
import type { Itinerary, ItineraryItem, ItineraryRejection } from "../types"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"
import "../styles/itinerary.css"

/** 轮询间隔。生成要 10~30 秒, 2 秒一次既不会让用户觉得卡, 也不会打爆后端。 */
const POLL_INTERVAL_MS = 2000

const DAY_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 10, 14]

/** 后端只给 retry_after(ISO), 显示成「明天 0 点」比一串时间戳有用。 */
function formatRetry(iso: string): string {
  const when = new Date(iso)
  if (Number.isNaN(when.getTime())) return "稍后再试"
  return when.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })
}

function groupByDay(items: ItineraryItem[]): [number, ItineraryItem[]][] {
  const grouped = new Map<number, ItineraryItem[]>()
  for (const item of items) {
    const bucket = grouped.get(item.day_index)
    if (bucket) bucket.push(item)
    else grouped.set(item.day_index, [item])
  }
  return [...grouped.entries()].sort((left, right) => left[0] - right[0])
}

/**
 * 「让 AI 排行程」页。
 *
 * 三段式: 提交拿 token -> 轮询 -> 展示。后端把生成放在后台跑, 所以这里必须自己轮询,
 * 而且要在 max_poll_seconds 之内停下来 —— 一直转圈的加载动画比一句「再试一次」更让人难受。
 *
 * 失败的三种情形分开显示: failed(调用了模型但失败)给人话, rejected(被限额拦下)
 * 给「什么时候再来」, 网络错给 describeError。混成一句会让用户以为是自己的输入有问题。
 */
const ItineraryPlanner = () => {
  const [requestText, setRequestText] = useState("")
  const [days, setDays] = useState(3)
  const [itinerary, setItinerary] = useState<Itinerary | null>(null)
  const [rejection, setRejection] = useState<ItineraryRejection | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  const poll = async (token: string, deadline: number) => {
    while (alive.current && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
      if (!alive.current) return
      let next: Itinerary
      try {
        next = await fetchItinerary(token)
      } catch (err) {
        if (alive.current) setError(describeError(err))
        return
      }
      if (!alive.current) return
      setItinerary(next)
      if (next.status !== "pending" && next.status !== "generating") return
    }
    // 到这里说明超过了后端给的轮询上限。行程可能还在跑, 提示用户刷新而不是继续等。
    if (alive.current) {
      setError("等得有点久了。行程可能还在生成, 稍后刷新看看。")
    }
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = requestText.trim()
    if (!trimmed || busy) return
    setBusy(true)
    setError("")
    setRejection(null)
    setItinerary(null)
    try {
      const accepted = await createItinerary(trimmed, days)
      // 先取一次: 命中已有行程时后端直接返回 200, 不用白等一轮轮询
      const first = await fetchItinerary(accepted.token)
      if (!alive.current) return
      setItinerary(first)
      if (first.status === "pending" || first.status === "generating") {
        await poll(accepted.token, Date.now() + first.max_poll_seconds * 1000)
      }
    } catch (err) {
      if (!alive.current) return
      const blocked = itineraryRejection(err)
      if (blocked) setRejection(blocked)
      else setError(describeError(err))
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  const reset = () => {
    setItinerary(null)
    setRejection(null)
    setError("")
  }

  const waiting = busy && itinerary !== null && (itinerary.status === "pending" || itinerary.status === "generating")

  return (
    <section className="planner">
      <form className="planner__form" onSubmit={submit}>
        <label className="planner__label" htmlFor="planner-request">
          说说你想怎么玩
        </label>
        <textarea
          id="planner-request"
          className="planner__input"
          value={requestText}
          onChange={(event) => setRequestText(event.target.value)}
          placeholder="例如: 带小孩去杭州玩三天, 不想爬山, 预算两千"
          maxLength={300}
          rows={3}
        />
        <div className="planner__row">
          <label className="planner__days" htmlFor="planner-days">
            天数
            <select
              id="planner-days"
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
            >
              {DAY_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value} 天
                </option>
              ))}
            </select>
          </label>
          <button className="planner__submit" type="submit" disabled={busy || !requestText.trim()}>
            {busy ? "生成中…" : "帮我排一下"}
          </button>
          {itinerary || rejection || error ? (
            <button className="planner__clear" type="button" onClick={reset}>
              清除
            </button>
          ) : null}
        </div>
      </form>

      {waiting ? <Loader /> : null}

      {!busy && rejection ? (
        <StateMessage
          title="今天排得够多了"
          detail={
            rejection.limit
              ? `每个设备每天最多 ${rejection.limit} 次, ${formatRetry(rejection.retry_after)} 之后可以再来。`
              : `${formatRetry(rejection.retry_after)} 之后可以再来。`
          }
          tone="error"
        />
      ) : null}

      {!busy && !rejection && error ? (
        <StateMessage title="没能排出行程" detail={error} tone="error" />
      ) : null}

      {!busy && itinerary && itinerary.status === "failed" ? (
        <StateMessage
          title="这次没排出来"
          detail={itinerary.error || "再试一次, 或者把需求说得具体一点。"}
          tone="error"
        />
      ) : null}

      {!busy && itinerary && itinerary.status === "succeeded" ? (
        <div className="planner__result">
          {itinerary.note ? <p className="planner__note">{itinerary.note}</p> : null}
          {groupByDay(itinerary.items).map(([day, items]) => (
            <article className="planner__day" key={day}>
              <h3 className="planner__dayTitle">第 {day} 天</h3>
              <ol className="planner__stops">
                {items.map((item) => (
                  <li className="planner__stop" key={`${item.day_index}-${item.seq}`}>
                    <Link className="planner__stopName" to={`/attraction/${item.attraction_id}`}>
                      {item.name}
                    </Link>
                    <p className="planner__stopNote">{item.note}</p>
                    <p className="planner__stopReason">{item.reason}</p>
                  </li>
                ))}
              </ol>
            </article>
          ))}
          <p className="planner__disclaimer">{itinerary.disclaimer}</p>
        </div>
      ) : null}
    </section>
  )
}

export default ItineraryPlanner
