import React from "react"
import { Link } from "react-router-dom"

import { APP_NAME, BASE_REPO_NAME, BASE_REPO_URL, APP_REPO_URL } from "../config"
import { useI18n } from "../i18n"

const Footer = () => {
  const { t } = useI18n()

  return (
    <footer className="footer">
      <div className="footer__inner">
        <p className="footer__brand">
          {APP_NAME} · {t("app.tagline")}
        </p>
        <nav className="footer__nav" aria-label={t("footer.navAria")}>
          <Link to="/credits">{t("footer.dataSources")}</Link>
          <a href={APP_REPO_URL} target="_blank" rel="noreferrer noopener">
            {t("footer.repo")}
          </a>
          <a href={BASE_REPO_URL} target="_blank" rel="noreferrer noopener">
            {t("footer.base", { name: BASE_REPO_NAME })}
          </a>
        </nav>
        <p className="footer__note">{t("footer.note")}</p>
      </div>
    </footer>
  )
}

export default Footer
