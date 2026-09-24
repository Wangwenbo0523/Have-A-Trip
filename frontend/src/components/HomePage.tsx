import React from "react"
import { Link } from "react-router-dom"

import { fetchAttractions, fetchRecommendations } from "../api/client"
import { APP_TAGLINE } from "../config"
import { useApi } from "../hooks/useApi"
import type { CategoryWithCount } from "../types"
import AttractionList from "./AttractionList"
import CategoryCard from "./CategoryCard"
import RecommendationGrid from "./RecommendationGrid"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"

interface HomePageProps {
  categories: CategoryWithCount[]
}

const HomePage = ({ categories }: HomePageProps) => {
  const recommendations = useApi(() => fetchRecommendations(6), [])
  const latest = useApi(() => fetchAttractions({ size: 6, sort: "newest" }), [])

  return (
    <main className="page">
      <section className="hero">
        <h2 className="hero__title">{APP_TAGLINE}</h2>
        <p className="hero__lead">
          按分类、城市和标签翻看景点档案, 看点、票价、最佳季节与游览时长一目了然。
        </p>
        <Link className="hero__cta" to="/attractions">
          浏览全部景点
        </Link>
      </section>

      <section className="section" aria-labelledby="home-recommend">
        <h3 className="section__title" id="home-recommend">
          为你推荐
        </h3>
        {recommendations.loading ? <Loader /> : null}
        {!recommendations.loading && recommendations.error ? (
          <StateMessage
            title="推荐暂时拿不到"
            detail={recommendations.error}
            tone="error"
            onRetry={recommendations.reload}
          />
        ) : null}
        {!recommendations.loading && !recommendations.error && recommendations.data ? (
          recommendations.data.length > 0 ? (
            <RecommendationGrid items={recommendations.data} />
          ) : (
            <StateMessage title="暂时没有可推荐的景点" detail="多逛几个景点之后推荐会更准" />
          )
        ) : null}
      </section>

      <section className="section" aria-labelledby="home-categories">
        <h3 className="section__title" id="home-categories">
          按分类浏览
        </h3>
        {categories.length > 0 ? (
          <div className="categoryGrid">
            {categories.map((category) => (
              <CategoryCard key={category.slug} category={category} />
            ))}
          </div>
        ) : (
          <StateMessage
            title="分类还没加载出来"
            detail="确认后端已经启动, 并且执行过 db/schema.sql 与 db/seed/seed.sql"
          />
        )}
      </section>

      <section className="section" aria-labelledby="home-latest">
        <h3 className="section__title" id="home-latest">
          最新收录
        </h3>
        {latest.loading ? <Loader /> : null}
        {!latest.loading && latest.error ? (
          <StateMessage
            title="景点加载失败"
            detail={latest.error}
            tone="error"
            onRetry={latest.reload}
          />
        ) : null}
        {!latest.loading && !latest.error && latest.data ? (
          <AttractionList attractions={latest.data.items} />
        ) : null}
      </section>
    </main>
  )
}

export default HomePage
