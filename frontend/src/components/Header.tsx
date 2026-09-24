import React from "react"
import { Link, NavLink } from "react-router-dom"

import { APP_NAME } from "../config"
import { useI18n } from "../i18n"
import type { CategoryWithCount } from "../types"
import LanguageSwitch from "./LanguageSwitch"
import "../styles/Header.css"

/** 导航里最多放几个分类, 再多就挤了 —— 剩下的去首页分类区找 */
const MAX_NAV_CATEGORIES = 6

const navClass = ({ isActive }: { isActive: boolean }) =>
  `header__link${isActive ? " is-active" : ""}`

const Header = ({ categories }: { categories: CategoryWithCount[] }) => {
  const { t } = useI18n()
  const topCategories = [...categories]
    .sort((a, b) => b.attraction_count - a.attraction_count)
    .slice(0, MAX_NAV_CATEGORIES)

  return (
    <header className="header">
      <div className="header__bar">
        {/* 语种切换固定在页头右上角, 每一页都能点到 */}
        <LanguageSwitch />

        <Link className="header__brand" to="/">
          <span className="header__name">{APP_NAME}</span>
          <span className="header__tagline">{t("app.tagline")}</span>
        </Link>

        <nav className="header__nav" aria-label={t("nav.aria")}>
          <NavLink className={navClass} to="/" end>
            {t("nav.home")}
          </NavLink>
          <NavLink className={navClass} to="/attractions">
            {t("nav.attractions")}
          </NavLink>
          <NavLink className={navClass} to="/planner">
            {t("nav.planner")}
          </NavLink>
          {/* 分类名来自数据库, 是内容不是文案: 库里没有英文名, 两种语种下都显示原名 */}
          {topCategories.map((category) => (
            <NavLink key={category.slug} className={navClass} to={`/category/${category.slug}`}>
              {category.name}
            </NavLink>
          ))}
          <NavLink className={navClass} to="/credits">
            {t("nav.credits")}
          </NavLink>
        </nav>
      </div>
    </header>
  )
}

export default Header
