import React, { useEffect, useState } from "react"

import { describeError, searchByAI } from "../api/client"
import { useAIStatus } from "../hooks/useAIStatus"
import { useI18n } from "../i18n"
import type { AISearchResult } from "../types"
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
 *
 * note 与 disclaimer 是后端(或模型)的输出, 属于内容不翻译; 界面文案走 i18n。
 */
const AiSearchPanel = ({ onActiveChange }: AiSearchPanelProps) => {
  const { t, lang } = useI18n()
  const status = useAIStatus()
  const [query, setQuery] = useState("")
  const [result, setResult] = useState<AISearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

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
      setError(describeError(err, lang))
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
          {t("ai.search.label")}
        </label>
        <div className="aiSearch__row">
          <input
            id="ai-search"
            className="aiSearch__input"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("ai.search.placeholder")}
            maxLength={200}
          />
          <button className="aiSearch__submit" type="submit" disabled={loading || !query.trim()}>
            {loading ? t("ai.search.loading") : t("ai.search.submit")}
          </button>
          {result || error ? (
            <button className="aiSearch__clear" type="button" onClick={clear}>
              {t("ai.search.clear")}
            </button>
          ) : null}
        </div>
      </form>

      {loading ? <Loader /> : null}

      {!loading && error ? (
        <StateMessage title={t("ai.search.error.title")} detail={error} tone="error" />
      ) : null}

      {!loading && !error && result ? (
        <div className="aiSearch__result">
          <p className="aiSearch__note">{result.note}</p>
          <p className="aiSearch__disclaimer">{result.disclaimer}</p>
          {result.items.length === 0 ? (
            <StateMessage
              title={t("ai.search.empty.title")}
              detail={t("ai.search.empty.detail", { query: result.query })}
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
