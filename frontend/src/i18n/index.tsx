import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import { type Lang, type MessageKey, messages } from "./messages"

/** 语种存在 localStorage 里。刷新、换页都保持上次的选择。 */
export const LANG_STORAGE_KEY = "have-a-trip:lang"

/** 写进 <html lang> 与按钮的 lang 属性, 让屏幕阅读器用对的发音。 */
export const HTML_LANG: Record<Lang, string> = { zh: "zh-CN", en: "en" }

export type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string

/**
 * 占位符替换: 把 {name} 换成实参。
 *
 * 缺变量时**原样留着**而不是替换成空串 —— 页面上出现一个 {count} 比少一个数字
 * 更容易被发现和修掉。
 */
export function format(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in vars ? String(vars[name]) : whole,
  )
}

/** 查表 + 回退到中文。英文表缺键时页面显示中文, 不会露出 key 本身。 */
export function translate(
  lang: Lang,
  key: MessageKey,
  vars?: Record<string, string | number>,
): string {
  const template = messages[lang]?.[key] ?? messages.zh[key] ?? key
  return format(template, vars)
}

/**
 * 初始语种: 存过的选择优先, 否则**中文**。
 *
 * 刻意不嗅探 navigator.language: 景点档案(名称、简介、方案)只有中文, 英文浏览器
 * 进来看到的是「英文外壳 + 中文内容」, 反而不如直接给中文界面。选择权交给按钮。
 */
export function detectLang(): Lang {
  try {
    const saved = window.localStorage.getItem(LANG_STORAGE_KEY)
    if (saved === "zh" || saved === "en") return saved
  } catch {
    // 无痕模式下 localStorage 会直接抛, 按默认值走
  }
  return "zh"
}

function saveLang(lang: Lang): void {
  try {
    window.localStorage.setItem(LANG_STORAGE_KEY, lang)
  } catch {
    // 存不下就算了: 记不住选择不影响本次会话
  }
}

interface I18nValue {
  lang: Lang
  setLang: (next: Lang) => void
  toggle: () => void
  t: Translate
}

/**
 * 默认值给中文而不是抛异常: 单个组件(以及它的测试)可以脱离 Provider 独立渲染,
 * 中文界面下行为与加 i18n 之前完全一致。
 */
const FALLBACK: I18nValue = {
  lang: "zh",
  setLang: () => {},
  toggle: () => {},
  t: (key, vars) => translate("zh", key, vars),
}

const I18nContext = createContext<I18nValue>(FALLBACK)

export function LanguageProvider({
  children,
  initial,
}: {
  children: React.ReactNode
  /** 只给测试用: 跳过 localStorage, 直接指定语种 */
  initial?: Lang
}) {
  const [lang, setLang] = useState<Lang>(() => initial ?? detectLang())

  useEffect(() => {
    document.documentElement.lang = HTML_LANG[lang]
    document.title = translate(lang, "app.title")
    saveLang(lang)
  }, [lang])

  // toggle 用函数式更新, 连续点击不会读到过期的 lang
  const toggle = useCallback(() => setLang((current) => (current === "zh" ? "en" : "zh")), [])

  const value = useMemo<I18nValue>(
    () => ({ lang, setLang, toggle, t: (key, vars) => translate(lang, key, vars) }),
    [lang, toggle],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  return useContext(I18nContext)
}

export type { Lang, MessageKey }
