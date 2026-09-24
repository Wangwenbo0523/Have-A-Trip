import { useCallback, useEffect, useState } from "react"

import { describeError } from "../api/client"
import { useI18n } from "../i18n"

export interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * 极简数据获取: 加载态 / 错误态 / 重试。
 *
 * loader 每次渲染都是新函数, 所以不把它放进 effect 的依赖里 —— 调用方必须把
 * 真正影响请求的参数完整列进 deps, 否则不会重新请求。
 */
export function useApi<T>(loader: () => Promise<T>, deps: unknown[]): ApiState<T> {
  const { lang } = useI18n()
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  // 存原始错误而不是当时算好的字符串: 切语种后错误提示要跟着变, 不必重新请求
  const [failure, setFailure] = useState<unknown>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setFailure(null)
    loader()
      .then((value) => {
        if (!alive) return
        setData(value)
        setLoading(false)
      })
      .catch((err) => {
        if (!alive) return
        setData(null)
        setFailure(err)
        setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return {
    data,
    loading,
    error: failure === null ? null : describeError(failure, lang),
    reload,
  }
}
