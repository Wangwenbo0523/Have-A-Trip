import React from "react"
import { Link } from "react-router-dom"

import { APP_NAME, APP_TAGLINE, BASE_REPO_NAME, BASE_REPO_URL, APP_REPO_URL } from "../config"

const Footer = () => (
  <footer className="footer">
    <div className="footer__inner">
      <p className="footer__brand">
        {APP_NAME} · {APP_TAGLINE}
      </p>
      <nav className="footer__nav" aria-label="页脚导航">
        <Link to="/credits">数据来源与致谢</Link>
        <a href={APP_REPO_URL} target="_blank" rel="noreferrer noopener">
          源码仓库
        </a>
        <a href={BASE_REPO_URL} target="_blank" rel="noreferrer noopener">
          前端基底 {BASE_REPO_NAME}
        </a>
      </nav>
      <p className="footer__note">
        以 MIT 许可开源 · 只做景点介绍与推荐, 不含地图与定位功能
      </p>
    </div>
  </footer>
)

export default Footer
