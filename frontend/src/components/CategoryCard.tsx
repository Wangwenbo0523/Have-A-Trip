import React from "react"
import { Link } from "react-router-dom"

import { useI18n } from "../i18n"
import type { CategoryWithCount } from "../types"

const CategoryCard = ({ category }: { category: CategoryWithCount }) => {
  const { t } = useI18n()

  return (
    <Link className="categoryCard" to={`/category/${category.slug}`}>
      {/* 分类名是库里的内容, 没有英文版本, 两种语种下都显示原名 */}
      <span className="categoryCard__name">{category.name}</span>
      <span className="categoryCard__count">
        {t("category.count", { count: category.attraction_count })}
      </span>
    </Link>
  )
}

export default CategoryCard
