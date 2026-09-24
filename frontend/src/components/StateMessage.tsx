import React from "react"

import { useI18n } from "../i18n"
import "../styles/browser.css"

interface StateMessageProps {
  title: string
  detail?: string | null
  tone?: "error" | "empty"
  onRetry?: () => void
}

/** 错误态与空态的统一样式。错误态必须说清「怎么修」, 不能只丢一句 failed。 */
const StateMessage = ({ title, detail, tone = "empty", onRetry }: StateMessageProps) => {
  const { t } = useI18n()

  return (
    <div
      className={`stateMessage stateMessage--${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      <p className="stateMessage__title">{title}</p>
      {detail ? <p className="stateMessage__detail">{detail}</p> : null}
      {onRetry ? (
        <button type="button" className="stateMessage__retry" onClick={onRetry}>
          {t("state.retry")}
        </button>
      ) : null}
    </div>
  )
}

export default StateMessage
