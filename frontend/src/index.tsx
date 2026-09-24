import React from "react"
import ReactDOM from "react-dom/client"
import AOS from "aos"

// 顺序有讲究: tachyons 是上游基座的工具类库, 放在最前面,
// 让 index.css 里的全局样式能盖住它。
import "tachyons"
import "aos/dist/aos.css"
import "./index.css"

import App from "./App"

// 上游在 index.html 里用 <script src="https://cdn.rawgit.com/..."> 加载 AOS,
// 那个 CDN 2019 年就关停了, AOS.init 从来没跑起来过 —— 而 aos.css 会给
// [data-aos] 元素初始 opacity: 0, 结果带 data-aos 的元素永久不可见。
// 改为从 npm 包初始化。
AOS.init({ duration: 800, once: true })

const container = document.getElementById("root")
if (container) {
  ReactDOM.createRoot(container).render(<App />)
}
