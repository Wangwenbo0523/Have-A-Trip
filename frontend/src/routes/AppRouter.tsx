import React from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"

import AttractionBrowser from "../components/AttractionBrowser"
import AttractionDetail from "../components/AttractionDetail"
import CategoryPage from "../components/CategoryPage"
import ComparePage from "../components/ComparePage"
import Credits from "../components/Credits"
import Footer from "../components/Footer"
import Header from "../components/Header"
import HomePage from "../components/HomePage"
import ItineraryPlanner from "../components/ItineraryPlanner"
import PostsPage from "../components/PostsPage"
import StatsPage from "../components/StatsPage"
import StateMessage from "../components/StateMessage"
import { useI18n } from "../i18n"
import type { CategoryWithCount } from "../types"

const AllAttractions = () => {
  const { t } = useI18n()
  return (
    <main className="page">
      <h2 className="page__title">{t("router.attractions.title")}</h2>
      <p className="page__subtitle">{t("router.attractions.subtitle")}</p>
      <AttractionBrowser />
    </main>
  )
}

const NotFound = () => {
  const { t } = useI18n()
  return (
    <main className="page">
      <StateMessage title={t("router.notFound.title")} detail={t("router.notFound.detail")} />
    </main>
  )
}

const Planner = () => {
  const { t } = useI18n()
  return (
    <main className="page">
      <h2 className="page__title">{t("router.planner.title")}</h2>
      <p className="page__subtitle">{t("router.planner.subtitle")}</p>
      <ItineraryPlanner />
    </main>
  )
}

const Feeds = () => {
  const { t } = useI18n()
  return (
    <main className="page">
      <h2 className="page__title">{t("router.posts.title")}</h2>
      <p className="page__subtitle">{t("router.posts.subtitle")}</p>
      <PostsPage />
    </main>
  )
}

interface AppRouterProps {
  categories: CategoryWithCount[]
}

const AppRouter = ({ categories }: AppRouterProps) => (
  <BrowserRouter>
    <div className="app">
      <Header categories={categories} />
      <Routes>
        <Route path="/" element={<HomePage categories={categories} />} />
        <Route path="/attractions" element={<AllAttractions />} />
        <Route path="/category/:slug" element={<CategoryPage categories={categories} />} />
        <Route path="/attraction/:slug" element={<AttractionDetail />} />
        <Route path="/planner" element={<Planner />} />
        <Route path="/posts" element={<Feeds />} />
        <Route path="/stats" element={<StatsPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/credits" element={<Credits />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Footer />
    </div>
  </BrowserRouter>
)

export default AppRouter
