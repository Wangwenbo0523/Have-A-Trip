import React from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"

import AttractionBrowser from "../components/AttractionBrowser"
import AttractionDetail from "../components/AttractionDetail"
import CategoryPage from "../components/CategoryPage"
import Credits from "../components/Credits"
import Footer from "../components/Footer"
import Header from "../components/Header"
import HomePage from "../components/HomePage"
import StateMessage from "../components/StateMessage"
import type { CategoryWithCount } from "../types"

const AllAttractions = () => (
  <main className="page">
    <h2 className="page__title">全部景点</h2>
    <p className="page__subtitle">支持关键字搜索、排序与分页</p>
    <AttractionBrowser />
  </main>
)

const NotFound = () => (
  <main className="page">
    <StateMessage title="页面不存在" detail="检查一下链接, 或者回首页看看" />
  </main>
)

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
        <Route path="/credits" element={<Credits />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Footer />
    </div>
  </BrowserRouter>
)

export default AppRouter
