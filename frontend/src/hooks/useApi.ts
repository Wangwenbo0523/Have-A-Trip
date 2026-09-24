import { useCallback, useEffect, useState } from "react"

import { describeError } from "../api/client"

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
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    loader()
      .then((value) => {
        if (!alive) return
        setData(value)
        setLoading(false)
      })
      .catch((err) => {
        if (!alive) return
        setData(null)
        setError(describeError(err))
        setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return { data, loading, error, reload }
}
