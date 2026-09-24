import React from "react"

import { fetchSources } from "../api/client"
import { APP_REPO_URL, BASE_REPO_NAME, BASE_REPO_URL } from "../config"
import { useApi } from "../hooks/useApi"
import { useI18n, type MessageKey } from "../i18n"
import type { ModificationStatus } from "../types"
import StateMessage from "./StateMessage"

import "../styles/credits.css"

/**
 * 修改状态 -> **文案键**。
 *
 * unregistered 不是「第四种正常状态」, 而是告警: 库里有 share-alike 来源, 但没人登记过
 * 改没改过。ODbL 与 CC BY-SA 都要求标注, 所以它必须显眼地露出来。
 */
const MODIFICATION_KEYS: Record<ModificationStatus, MessageKey> = {
  modified: "credits.modification.modified",
  unmodified: "credits.modification.unmodified",
  "not-applicable": "credits.modification.notApplicable",
  unregistered: "credits.modification.unregistered",
}

interface CodeAsset {
  nameKey: MessageKey
  /** 名称里带变量的(只有前端基底那条)在这里给值 */
  nameVars?: Record<string, string>
  license: string
  noteKey: MessageKey
  link?: string
}

/**
 * 代码层与静态素材。这一块**不进数据库** —— 它是仓库里的文件, 不是景点档案,
 * 所以只能手写。口径见 docs/LICENSE-AUDIT.md 第一、五节, 改这里要同步那边。
 */
const CODE_ASSETS: CodeAsset[] = [
  {
    nameKey: "credits.asset.self.name",
    license: "MIT",
    noteKey: "credits.asset.self.note",
    link: APP_REPO_URL,
  },
  {
    nameKey: "credits.asset.base.name",
    nameVars: { name: BASE_REPO_NAME },
    license: "MIT",
    noteKey: "credits.asset.base.note",
    link: BASE_REPO_URL,
  },
  {
    nameKey: "credits.asset.recbole.name",
    license: "MIT",
    noteKey: "credits.asset.recbole.note",
    link: "https://github.com/RUCAIBox/RecBole",
  },
  {
    nameKey: "credits.asset.favicon.name",
    license: "MIT",
    noteKey: "credits.asset.favicon.note",
    link: `${APP_REPO_URL}/blob/main/scripts/make_favicon.py`,
  },
]

const Credits = () => {
  const { t } = useI18n()
  const { data, loading, error, reload } = useApi(() => fetchSources(), [])

  const sourceSection = () => {
    if (loading) return <StateMessage title={t("credits.sources.loading")} />
    // 错误态在上面统一给过一次, 这里不再重复一个带按钮的报错
    if (!data) return null
    if (data.sources.length === 0) {
      return (
        <StateMessage
          title={t("credits.sources.empty.title")}
          detail={t("credits.sources.empty.detail")}
        />
      )
    }
    return (
      <>
        <div className="credits__scroll">
          <table className="credits__table">
            <caption className="credits__caption">
              {t("credits.sources.caption", { total: data.attraction_total })}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("credits.table.source")}</th>
                <th scope="col">{t("credits.table.license")}</th>
                <th scope="col">{t("credits.table.attractions")}</th>
                <th scope="col">{t("credits.table.provinces")}</th>
                <th scope="col">{t("credits.table.modification")}</th>
              </tr>
            </thead>
            <tbody>
              {data.sources.map((record) => (
                <tr key={`${record.source}::${record.license}`}>
                  <td>{record.source}</td>
                  <td>{record.license}</td>
                  <td>{record.attraction_count}</td>
                  <td>{record.province_count}</td>
                  <td>
                    <span
                      className={
                        record.modification === "unregistered"
                          ? "credits__flag credits__flag--warn"
                          : "credits__flag"
                      }
                    >
                      {t(MODIFICATION_KEYS[record.modification])}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="credits__note">{t("credits.note")}</p>
      </>
    )
  }

  const imageSection = () => {
    if (loading) return <StateMessage title={t("credits.images.loading")} />
    if (!data) return null
    if (data.images.length === 0) {
      return (
        <StateMessage
          title={t("credits.images.empty.title")}
          detail={t("credits.images.empty.detail")}
        />
      )
    }
    return (
      <div className="credits__scroll">
        <table className="credits__table">
          <caption className="credits__caption">
            {t("credits.images.caption", { total: data.image_total })}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t("credits.table.credit")}</th>
              <th scope="col">{t("credits.table.license")}</th>
              <th scope="col">{t("credits.table.count")}</th>
            </tr>
          </thead>
          <tbody>
            {data.images.map((image) => (
              <tr key={`${image.credit}::${image.license}`}>
                <td>{image.credit}</td>
                <td>{image.license}</td>
                <td>{image.image_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <main className="page">
      <h2 className="page__title">{t("credits.title")}</h2>
      <p className="page__subtitle">{t("credits.subtitle")}</p>

      {error ? (
        <StateMessage
          tone="error"
          title={t("credits.error.title")}
          detail={error}
          onRetry={reload}
        />
      ) : null}

      {data?.needs_attention ? (
        <StateMessage
          tone="error"
          title={t("credits.attention.title")}
          detail={t("credits.attention.detail")}
        />
      ) : null}

      <section className="section">
        <h3 className="section__title">{t("credits.sources.title")}</h3>
        {sourceSection()}
      </section>

      <section className="section">
        <h3 className="section__title">{t("credits.images.title")}</h3>
        {imageSection()}
      </section>

      <section className="section">
        <h3 className="section__title">{t("credits.code.title")}</h3>
        <div className="credits__scroll">
          <table className="credits__table">
            <thead>
              <tr>
                <th scope="col">{t("credits.table.name")}</th>
                <th scope="col">{t("credits.table.license")}</th>
                <th scope="col">{t("credits.table.note")}</th>
              </tr>
            </thead>
            <tbody>
              {CODE_ASSETS.map((asset) => (
                <tr key={asset.nameKey}>
                  <td>
                    {asset.link ? (
                      <a
                        className="credits__link"
                        href={asset.link}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        {t(asset.nameKey, asset.nameVars)}
                      </a>
                    ) : (
                      t(asset.nameKey, asset.nameVars)
                    )}
                  </td>
                  <td>{asset.license}</td>
                  <td>{t(asset.noteKey)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <h3 className="section__title">{t("credits.notDo.title")}</h3>
        <ul className="credits__list">
          <li>{t("credits.notDo.1")}</li>
          <li>{t("credits.notDo.2")}</li>
          <li>{t("credits.notDo.3")}</li>
          <li>{t("credits.notDo.4")}</li>
        </ul>
      </section>
    </main>
  )
}

export default Credits
