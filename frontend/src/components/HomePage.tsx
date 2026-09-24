import React from "react"
import { Link } from "react-router-dom"

import { fetchAttractions, fetchRecommendations } from "../api/client"
import { useApi } from "../hooks/useApi"
import { useI18n } from "../i18n"
import type { CategoryWithCount } from "../types"
import AttractionList from "./AttractionList"
import CategoryCard from "./CategoryCard"
import RandomPicks from "./RandomPicks"
import RecommendationGrid from "./RecommendationGrid"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"

interface HomePageProps {
  categories: CategoryWithCount[]
}

const HomePage = ({ categories }: HomePageProps) => {
  const { t } = useI18n()
  const recommendations = useApi(() => fetchRecommendations(6), [])
  const latest = useApi(() => fetchAttractions({ size: 6, sort: "newest" }), [])

  return (
    <main className="page">
      {/* 打开首页就弹的三个随机地方; 一次会话只弹一次, 关掉后本次不再出现 */}
      <RandomPicks />

      <section className="hero">
        <h2 className="hero__title">{t("app.tagline")}</h2>
        <p className="hero__lead">{t("home.lead")}</p>
        <Link className="hero__cta" to="/attractions">
          {t("home.cta")}
        </Link>
      </section>

      <section className="section" aria-labelledby="home-recommend">
        <h3 className="section__title" id="home-recommend">
          {t("home.recommend")}
        </h3>
        {recommendations.loading ? <Loader /> : null}
        {!recommendations.loading && recommendations.error ? (
          <StateMessage
            title={t("home.error.recommend")}
            detail={recommendations.error}
            tone="error"
            onRetry={recommendations.reload}
          />
        ) : null}
        {!recommendations.loading && !recommendations.error && recommendations.data ? (
          recommendations.data.length > 0 ? (
            <RecommendationGrid items={recommendations.data} />
          ) : (
            <StateMessage
              title={t("home.recommendEmpty.title")}
              detail={t("home.recommendEmpty.detail")}
            />
          )
        ) : null}
      </section>

      <section className="section" aria-labelledby="home-categories">
        <h3 className="section__title" id="home-categories">
          {t("home.categories")}
        </h3>
        {categories.length > 0 ? (
          <div className="categoryGrid">
            {categories.map((category) => (
              <CategoryCard key={category.slug} category={category} />
            ))}
          </div>
        ) : (
          <StateMessage
            title={t("home.categoriesEmpty.title")}
            detail={t("home.categoriesEmpty.detail")}
          />
        )}
      </section>

      <section className="section" aria-labelledby="home-latest">
        <h3 className="section__title" id="home-latest">
          {t("home.latest")}
        </h3>
        {latest.loading ? <Loader /> : null}
        {!latest.loading && latest.error ? (
          <StateMessage
            title={t("home.error.latest")}
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
