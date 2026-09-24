import React from "react"
import { Link, NavLink } from "react-router-dom"

import { APP_NAME, APP_TAGLINE } from "../config"
import type { CategoryWithCount } from "../types"
import "../styles/Header.css"

/** 导航里最多放几个分类, 再多就挤了 —— 剩下的去首页分类区找 */
const MAX_NAV_CATEGORIES = 6

const navClass = ({ isActive }: { isActive: boolean }) =>
  `header__link${isActive ? " is-active" : ""}`

const Header = ({ categories }: { categories: CategoryWithCount[] }) => {
  const topCategories = [...categories]
    .sort((a, b) => b.attraction_count - a.attraction_count)
    .slice(0, MAX_NAV_CATEGORIES)

  return (
    <header className="header">
      <div className="header__bar">
        <Link className="header__brand" to="/">
          <span className="header__name">{APP_NAME}</span>
          <span className="header__tagline">{APP_TAGLINE}</span>
        </Link>

        <nav className="header__nav" aria-label="主导航">
          <NavLink className={navClass} to="/" end>
            首页
          </NavLink>
          <NavLink className={navClass} to="/attractions">
            全部景点
          </NavLink>
          {topCategories.map((category) => (
            <NavLink key={category.slug} className={navClass} to={`/category/${category.slug}`}>
              {category.name}
            </NavLink>
          ))}
          <NavLink className={navClass} to="/credits">
            关于
          </NavLink>
        </nav>
      </div>
    </header>
  )
}

export default Header
