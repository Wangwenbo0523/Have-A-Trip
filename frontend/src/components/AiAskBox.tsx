import React, { useState } from "react"

import { askAboutAttraction, describeError } from "../api/client"
import { useAIStatus } from "../hooks/useAIStatus"
import { useI18n, type MessageKey } from "../i18n"
import type { AIAskResult } from "../types"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"
import "../styles/aiAsk.css"

/** 几个常见问题。用户往往不知道该问什么, 给几个能点开的例子比空输入框友好。 */
const SUGGESTIONS: MessageKey[] = [
  "ai.ask.suggestion.1",
  "ai.ask.suggestion.2",
  "ai.ask.suggestion.3",
]

interface AiAskBoxProps {
  slug: string
  /** 景点名, 只用在占位文案里 */
  name: string
}

/**
 * 详情页的「问一句」。
 *
 * 答案只能来自这个景点的档案字段, 所以它是**复述**而不是知识问答 —— 档案里没有的
 * (开放时间、天气、交通)后端会明确说不作答。降级时后端返回档案摘录并仍然 200,
 * 所以这里把 note 显示出来, 让人知道这句话是模型写的还是档案里现成的。
 *
 * answer / note / disclaimer 都是后端的输出(内容), 原样显示不翻译。
 */
const AiAskBox = ({ slug, name }: AiAskBoxProps) => {
  const { t, lang } = useI18n()
  const status = useAIStatus()
  const [question, setQuestion] = useState("")
  const [result, setResult] = useState<AIAskResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  if (!status || !status.available) return null

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || loading) return
    setLoading(true)
    setError("")
    try {
      setResult(await askAboutAttraction(slug, trimmed))
    } catch (err) {
      setError(describeError(err, lang))
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setResult(null)
    setError("")
    setQuestion("")
  }

  return (
    <section className="aiAsk">
      <h3 className="section__title">{t("ai.ask.title")}</h3>
      <p className="aiAsk__hint">{t("ai.ask.hint")}</p>

      <form className="aiAsk__form" onSubmit={submit}>
        <input
          className="aiAsk__input"
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={t("ai.ask.placeholder", { name })}
          aria-label={t("ai.ask.aria")}
          maxLength={200}
        />
        <button className="aiAsk__submit" type="submit" disabled={loading || !question.trim()}>
          {loading ? t("ai.ask.loading") : t("ai.ask.submit")}
        </button>
        {result || error ? (
          <button className="aiAsk__clear" type="button" onClick={reset}>
            {t("ai.ask.clear")}
          </button>
        ) : null}
      </form>

      {result === null && !loading && !error ? (
        <ul className="aiAsk__suggestions">
          {SUGGESTIONS.map((key) => (
            <li key={key}>
              <button
                type="button"
                className="aiAsk__suggestion"
                onClick={() => setQuestion(t(key))}
              >
                {t(key)}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {loading ? <Loader /> : null}

      {!loading && error ? (
        <StateMessage title={t("ai.ask.error.title")} detail={error} tone="error" />
      ) : null}

      {!loading && !error && result ? (
        <div className="aiAsk__answer">
          <p className="aiAsk__question">{result.question}</p>
          <p className="aiAsk__text">{result.answer}</p>
          {result.note ? <p className="aiAsk__note">{result.note}</p> : null}
          <p className="aiAsk__disclaimer">{result.disclaimer}</p>
        </div>
      ) : null}
    </section>
  )
}

export default AiAskBox
