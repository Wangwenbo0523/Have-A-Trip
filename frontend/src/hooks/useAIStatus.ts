import { useEffect, useState } from "react"

import { fetchAIStatus } from "../api/client"
import type { AIStatus } from "../types"

/** 拿不到状态时用它: 宁可不显示入口, 也不给一个点了没反应的按钮。 */
const UNAVAILABLE: AIStatus = {
  available: false,
  provider: "unknown",
  model: null,
  disclaimer: "",
}

/**
 * AI 入口是否可用。默认配置(后端 LLM_PROVIDER=none)下 available 为 false,
 * 页面据此决定要不要显示 AI 入口。
 *
 * 一次挂载查一次就够: 可用性是部署配置决定的, 不会在使用过程中变。
 */
export function useAIStatus(): AIStatus | null {
  const [status, setStatus] = useState<AIStatus | null>(null)

  useEffect(() => {
    let alive = true
    fetchAIStatus()
      .then((data) => {
        if (alive) setStatus(data)
      })
      .catch(() => {
        if (alive) setStatus(UNAVAILABLE)
      })
    return () => {
      alive = false
    }
  }, [])

  return status
}