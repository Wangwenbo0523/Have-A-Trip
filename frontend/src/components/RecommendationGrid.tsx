import React, { useEffect, useState } from "react"

import { fetchRecommendNotes } from "../api/client"
import { useAIStatus } from "../hooks/useAIStatus"
import { useI18n } from "../i18n"
import type { AIRecommendNotes, Recommendation } from "../types"
import AttractionCard from "./AttractionCard"
import "../styles/recommendNotes.css"

/**
 * 推荐位。
 *
 * 条目、顺序、分数全部来自 /recommendations, 这里只多一层文案: 模型可用时把
 * 「为什么推荐它」那句话改写得更顺, 不可用或润色失败时原样显示后端给的理由。
 * 润色是锦上添花, 拿不到就不显示, 绝不让推荐位变成报错页。
 *
 * 理由正文是后端(或模型)产出的内容, 不翻译; 只有「AI 润色」这个标签是界面文案。
 */
const RecommendationGrid = ({ items }: { items: Recommendation[] }) => {
  const { t } = useI18n()
  const status = useAIStatus()
  const [notes, setNotes] = useState<AIRecommendNotes | null>(null)

  const available = status?.available ?? false
  // items 每次渲染都是新数组, 所以用 slug 串当依赖; 长度顺带就是请求的 limit
  const slugs = items.map((item) => item.attraction.slug).join(",")

  useEffect(() => {
    if (!available || !slugs) return
    let alive = true
    fetchRecommendNotes(slugs.split(",").length)
      .then((data) => {
        if (alive) setNotes(data)
      })
      .catch(() => {
        // 润色拿不到就退回原来的理由, 不在推荐位上显示错误
        if (alive) setNotes(null)
      })
    return () => {
      alive = false
    }
  }, [available, slugs])

  const polished = notes?.polished ?? false
  const reasonOf = (item: Recommendation) =>
    notes?.reasons.find((entry) => entry.slug === item.attraction.slug)?.note || item.reason

  return (
    <>
      <ul className="attractionGrid">
        {items.map((item) => (
          <li key={`${item.rank}-${item.attraction.slug}`}>
            <AttractionCard attraction={item.attraction} />
            {/* 每条推荐都要能解释「为什么是它」, 这是 S2 的硬性约定 */}
            <p className={polished ? "reason reason--ai" : "reason"}>{reasonOf(item)}</p>
          </li>
        ))}
      </ul>

      {notes?.polished ? (
        <p className="recommendNotes__foot">
          <span className="recommendNotes__chip">{t("recommend.chip")}</span>
          <span>{notes.disclaimer}</span>
        </p>
      ) : null}

      {!notes?.polished && notes?.note ? (
        <p className="recommendNotes__fallback">{notes.note}</p>
      ) : null}
    </>
  )
}

export default RecommendationGrid
