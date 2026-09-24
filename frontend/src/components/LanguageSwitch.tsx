import React from "react"

import { useI18n } from "../i18n"
import "../styles/languageSwitch.css"

/**
 * 语种切换按钮。
 *
 * 按钮上写的是**目标语言**的名字: 中文界面上显示 EN, 英文界面上显示 中文。
 * 这是通行做法, 比写当前语言(点一下变成什么要看两遍)更好懂。
 * lang 属性跟着按钮文字走, 屏幕阅读器才不会用错发音。
 */
const LanguageSwitch = () => {
  const { lang, toggle, t } = useI18n()
  const toEnglish = lang === "zh"
  const label = toEnglish ? t("nav.lang.toEn") : t("nav.lang.toZh")

  return (
    <button
      type="button"
      className="langSwitch"
      onClick={toggle}
      aria-label={label}
      title={label}
      lang={toEnglish ? "en" : "zh-CN"}
    >
      <span className="langSwitch__globe" aria-hidden="true">
        🌐
      </span>
      {toEnglish ? t("nav.lang.en") : t("nav.lang.zh")}
    </button>
  )
}

export default LanguageSwitch
