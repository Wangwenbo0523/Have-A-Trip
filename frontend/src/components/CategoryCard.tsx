import React from "react"
import { Link } from "react-router-dom"

import type { CategoryWithCount } from "../types"

const CategoryCard = ({ category }: { category: CategoryWithCount }) => (
  <Link className="categoryCard" to={`/category/${category.slug}`}>
    <span className="categoryCard__name">{category.name}</span>
    <span className="categoryCard__count">{category.attraction_count} 个景点</span>
  </Link>
)

export default CategoryCard
