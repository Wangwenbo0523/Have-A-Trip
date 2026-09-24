import React from "react"
import { useParams } from "react-router-dom"

import type { CategoryWithCount } from "../types"
import AttractionBrowser from "./AttractionBrowser"

interface CategoryPageProps {
  /** 分类清单在 App 顶层取过一次, 这里直接用, 不再多发一次请求 */
  categories: CategoryWithCount[]
}

const CategoryPage = ({ categories }: CategoryPageProps) => {
  const { slug = "" } = useParams<{ slug: string }>()
  const category = categories.find((item) => item.slug === slug)

  return (
    <main className="page">
      <h2 className="page__title">{category ? category.name : slug}</h2>
      <p className="page__subtitle">
        {category ? `共 ${category.attraction_count} 个景点` : "分类信息还没加载出来"}
      </p>
      <AttractionBrowser category={slug} />
    </main>
  )
}

export default CategoryPage
