import React from "react"

import { fetchCategories } from "./api/client"
import { useApi } from "./hooks/useApi"
import AppRouter from "./routes/AppRouter"
import "./App.css"

function App() {
  // 分类是导航的一部分, 在顶层取一次就够。取不到时导航自动降级为
  // 「首页 / 全部景点 / 关于」, 页面各自的错误态会说明原因。
  const { data: categories } = useApi(fetchCategories, [])

  return <AppRouter categories={categories ?? []} />
}

export default App
