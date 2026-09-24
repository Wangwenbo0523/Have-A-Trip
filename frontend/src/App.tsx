import React from "react"

import { fetchCategories } from "./api/client"
import { useApi } from "./hooks/useApi"
import { LanguageProvider } from "./i18n"
import { ThemeProvider } from "./theme"
import AppRouter from "./routes/AppRouter"
import "./App.css"

/**
 * 取分类这一步放在 Provider **里面**。
 *
 * 分类是导航的一部分, 在顶层取一次就够。取不到时导航自动降级为
 * 「首页 / 全部景点 / 关于」, 页面各自的错误态会说明原因。
 * 放在 Provider 里是为了让 useApi 报错时能跟着当前语种走。
 */
function AppShell() {
  const { data: categories } = useApi(fetchCategories, [])

  return <AppRouter categories={categories ?? []} />
}

/** 主题与语种状态包在最外层: 页头(含两个切换按钮)、页脚与所有页面共用同一份。 */
function App() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <AppShell />
      </LanguageProvider>
    </ThemeProvider>
  )
}

export default App
