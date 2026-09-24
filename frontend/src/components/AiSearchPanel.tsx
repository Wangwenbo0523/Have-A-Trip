import React, { useEffect, useState } from "react"

import { describeError, fetchAIStatus, searchByAI } from "../api/client"
import type { AISearchResult, AIStatus } from "../types"
import AttractionList from "./AttractionList"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"
import "../styles/aiSearch.css"

interface AiSearchPanelProps {
  /**
   * 面板是否有结果。父组件据此把普通检索那条列表收起来 ——
   * 两份列表同时出现会让人分不清哪份才是自己要的。
   */
  onActiveChange?: (active: boolean) => void
}

/**
 * 「用一句话找景点」入口。
 *
 * 只在后端说 AI 可用时才渲染: 默认配置(LLM_PROVIDER=none)下这个组件什么都不显示,
 * 应用照常运行。模型未配置 / 超时 / 答得不合法时, 后端会降级成关键词检索并返回 200,
 * 所以这里必须把 degraded 与 note 显示出来 —— 不能让用户以为模型真的听懂了。
 */
const AiSearchPanel = ({ onActiveChange }: AiSearchPanelProps) => {
  const [status, setStatus] = useState<AIStatus | null>(null)
  const [query, setQuery] = useState("")
  const [result, setResult] = useState<AISearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    let alive = true
    fetchAIStatus()
      .then((data) => {
        if (alive) setStatus(data)
      })
      // 拿不到状态就当作不可用: 宁可不显示这个入口, 也不要给一个点了没反应的按钮
      .catch(() => {
        if (alive) setStatus({ available: false, provider: "unknown", model: null, disclaimer: "" })
      })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    onActiveChange?.(result !== null)
  }, [result, onActiveChange])

  if (!status || !status.available) return null

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || loading) return
    setLoading(true)
    setError("")
    try {
      setResult(await searchByAI(trimmed))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  const clear = () => {
    setResult(null)
    setError("")
  }

  return (
    <section className="aiSearch">
      <form className="aiSearch__form" onSubmit={submit}>
        <label className="aiSearch__label" htmlFor="ai-search">
          用一句话找景点
        </label>
        <div className="aiSearch__row">
          <input
            id="ai-search"
            className="aiSearch__input"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如: 杭州适合慢慢逛的古迹"
            maxLength={200}
          />
          <button className="aiSearch__submit" type="submit" disabled={loading || !query.trim()}>
            {loading ? "解析中…" : "找一下"}
          </button>
          {result || error ? (
            <button className="aiSearch__clear" type="button" onClick={clear}>
              清除
            </button>
          ) : null}
        </div>
      </form>

      {loading ? <Loader /> : null}

      {!loading && error ? <StateMessage title="AI 检索失败" detail={error} tone="error" /> : null}

      {!loading && !error && result ? (
        <div className="aiSearch__result">
          <p className="aiSearch__note">{result.note}</p>
          <p className="aiSearch__disclaimer">{result.disclaimer}</p>
          {result.items.length === 0 ? (
            <StateMessage
              title="没有匹配的景点"
              detail={`没有找到和「${result.query}」相关的景点, 换个说法试试`}
            />
          ) : (
            <AttractionList attractions={result.items} />
          )}
        </div>
      ) : null}
    </section>
  )
}

export default AiSearchPanel