import React from "react"

import "../styles/browser.css"

interface StateMessageProps {
  title: string
  detail?: string | null
  tone?: "error" | "empty"
  onRetry?: () => void
}

/** 错误态与空态的统一样式。错误态必须说清「怎么修」, 不能只丢一句 failed。 */
const StateMessage = ({ title, detail, tone = "empty", onRetry }: StateMessageProps) => (
  <div className={`stateMessage stateMessage--${tone}`} role={tone === "error" ? "alert" : "status"}>
    <p className="stateMessage__title">{title}</p>
    {detail ? <p className="stateMessage__detail">{detail}</p> : null}
    {onRetry ? (
      <button type="button" className="stateMessage__retry" onClick={onRetry}>
        重试
      </button>
    ) : null}
  </div>
)

export default StateMessage
