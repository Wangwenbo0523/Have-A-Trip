import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

/** 主题存在 localStorage 里, 与语种同一套做法(刷新、换页都保持上次的选择)。 */
export const THEME_STORAGE_KEY = "have-a-trip:theme"

export type Theme = "dark" | "light"

/**
 * 浏览器 UI(移动端地址栏、任务切换器)也跟着换色。
 * 浅色页面上顶一条深色状态栏很割裂, 所以跟着主题走而不是写死在 index.html。
 */
const THEME_COLOR: Record<Theme, string> = { dark: "#101012", light: "#ffffff" }

/**
 * 初始主题: 存过的选择优先, 否则**浅色**。
 *
 * 这套视觉是白画布优先的(Airbnb 的设计语言, 见仓库根 DESIGN.md): 卡片是白底压白底
 * 靠细线分块, 页头也是白的。默认给深色等于让所有人先看到一副非设计意图的样子。
 *
 * 刻意不嗅探 prefers-color-scheme, 与 detectLang 不嗅探 navigator.language 是同一个
 * 理由: 跟着系统走会让同一台机器上的两个人、或者同一台机器上的两个页面看到两副样子。
 * 选择权交给按钮。
 */
export function detectTheme(): Theme {
  try {
    const saved = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (saved === "dark" || saved === "light") return saved
  } catch {
    // 无痕模式下 localStorage 会直接抛, 按默认值走
  }
  return "light"
}

/**
 * 把主题写到 <html data-theme> 上。CSS 侧只需要这一处开关, 见 src/index.css。
 *
 * 写在 dataset 而不是 <body> 的类名上: 页面的根元素在 React 挂载之前就存在,
 * 而且 index.html 里那段「首屏定主题」的内联脚本也写同一个位置。
 */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", THEME_COLOR[theme])
}

interface ThemeValue {
  theme: Theme
  setTheme: (next: Theme) => void
  toggle: () => void
}

/** 脱离 Provider 时给浅色而不是抛异常: 组件(以及它的测试)可以独立渲染。 */
const FALLBACK: ThemeValue = { theme: "light", setTheme: () => {}, toggle: () => {} }

const ThemeContext = createContext<ThemeValue>(FALLBACK)

export function ThemeProvider({
  children,
  initial,
}: {
  children: React.ReactNode
  /** 只给测试用: 跳过 localStorage, 直接指定主题 */
  initial?: Theme
}) {
  const [theme, setTheme] = useState<Theme>(() => initial ?? detectTheme())

  useEffect(() => {
    applyTheme(theme)
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // 存不下就算了: 记不住选择不影响本次会话
    }
  }, [theme])

  // toggle 用函数式更新, 连续点击不会读到过期的 theme
  const toggle = useCallback(() => setTheme((current) => (current === "dark" ? "light" : "dark")), [])

  const value = useMemo<ThemeValue>(() => ({ theme, setTheme, toggle }), [theme, toggle])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeValue {
  return useContext(ThemeContext)
}