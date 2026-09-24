import React from "react"

import { useI18n } from "../i18n"
import { useTheme } from "../theme"
import "../styles/themeSwitch.css"

/**
 * 浅色 / 深色主题切换按钮。
 *
 * 与语种按钮同一套做法: 按钮上写的是**目标主题**的名字 —— 深色界面上显示「浅色」,
 * 点一下变浅色。写当前状态的话要点两遍才看得懂。
 *
 * 图标跟着目标主题走(深色下给太阳, 浅色下给月亮), 纯装饰, 已有可读标签就不重复念。
 */
const ThemeSwitch = () => {
  const { t } = useI18n()
  const { theme, toggle } = useTheme()
  const toLight = theme === "dark"
  const label = toLight ? t("nav.theme.toLight") : t("nav.theme.toDark")

  return (
    <button
      type="button"
      className="header__tool themeSwitch"
      onClick={toggle}
      title={label}
      aria-label={label}
    >
      <span className="themeSwitch__icon" aria-hidden="true">
        {toLight ? "☀️" : "🌙"}
      </span>
      {toLight ? t("nav.theme.light") : t("nav.theme.dark")}
    </button>
  )
}

export default ThemeSwitch
