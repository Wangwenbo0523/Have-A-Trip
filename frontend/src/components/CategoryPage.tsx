import React from "react"
import { useParams } from "react-router-dom"

import { useI18n } from "../i18n"
import type { CategoryWithCount } from "../types"
import AttractionBrowser from "./AttractionBrowser"

interface CategoryPageProps {
  /** 分类清单在 App 顶层取过一次, 这里直接用, 不再多发一次请求 */
  categories: CategoryWithCount[]
}

const CategoryPage = ({ categories }: CategoryPageProps) => {
  const { t } = useI18n()
  const { slug = "" } = useParams<{ slug: string }>()
  const category = categories.find((item) => item.slug === slug)

  return (
    <main className="page">
      <h2 className="page__title">{category ? category.name : slug}</h2>
      <p className="page__subtitle">
        {category
          ? t("category.page.subtitle", { count: category.attraction_count })
          : t("category.page.missing")}
      </p>
      <AttractionBrowser category={slug} />
    </main>
  )
}

export default CategoryPage
