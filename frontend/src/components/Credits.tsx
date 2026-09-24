import React from "react"

import { fetchSources } from "../api/client"
import { APP_REPO_URL, BASE_REPO_NAME, BASE_REPO_URL } from "../config"
import { useApi } from "../hooks/useApi"
import type { ModificationStatus } from "../types"
import StateMessage from "./StateMessage"

import "../styles/credits.css"

/**
 * 修改状态 -> 页面上的一句话。
 *
 * unregistered 不是「第四种正常状态」, 而是告警: 库里有 share-alike 来源, 但没人登记过
 * 改没改过。ODbL 与 CC BY-SA 都要求标注, 所以它必须显眼地露出来。
 */
const MODIFICATION_LABEL: Record<ModificationStatus, string> = {
  modified: "已修改",
  unmodified: "未修改",
  "not-applicable": "无需标注",
  unregistered: "未登记",
}

interface CodeAsset {
  name: string
  license: string
  note: string
  link?: string
}

/**
 * 代码层与静态素材。这一块**不进数据库** —— 它是仓库里的文件, 不是景点档案,
 * 所以只能手写。口径见 docs/LICENSE-AUDIT.md 第一、五节, 改这里要同步那边。
 */
const CODE_ASSETS: CodeAsset[] = [
  {
    name: "Have-A-Trip 本体",
    license: "MIT",
    note: "根 LICENSE 的署名为 Copyright (c) 2026 Wangwenbo0523",
    link: APP_REPO_URL,
  },
  {
    name: `前端基底 ${BASE_REPO_NAME}`,
    license: "MIT",
    note: "已大幅修改: 删掉地图与定位、整体换成景点模型。上游 LICENSE 原样保留",
    link: BASE_REPO_URL,
  },
  {
    name: "RecBole",
    license: "MIT",
    note: "推荐引擎, 当 pip 依赖使用, 未改动源码",
    link: "https://github.com/RUCAIBox/RecBole",
  },
  {
    name: "站点图标 public/favicon.ico",
    license: "MIT",
    note: "自绘: 由 scripts/make_favicon.py 程序化生成, 与仓库同许可, 不含第三方素材",
    link: `${APP_REPO_URL}/blob/main/scripts/make_favicon.py`,
  },
]

const Credits = () => {
  const { data, loading, error, reload } = useApi(() => fetchSources(), [])

  const sourceSection = () => {
    if (loading) return <StateMessage title="正在加载来源清单" />
    // 错误态在上面统一给过一次, 这里不再重复一个带按钮的报错
    if (!data) return null
    if (data.sources.length === 0) {
      return (
        <StateMessage
          title="暂无已发布的景点数据"
          detail="库里还没有 status='published' 的景点。"
        />
      )
    }
    return (
      <>
        <div className="credits__scroll">
          <table className="credits__table">
            <caption className="credits__caption">
              共 {data.attraction_total} 条已发布景点
            </caption>
            <thead>
              <tr>
                <th scope="col">来源</th>
                <th scope="col">许可</th>
                <th scope="col">景点数</th>
                <th scope="col">覆盖省级行政区</th>
                <th scope="col">修改状态</th>
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
                      {MODIFICATION_LABEL[record.modification]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="credits__note">
          许可带相同方式共享义务(ODbL / CC BY-SA)时必须有「已修改 / 未修改」的标注。
          「未登记」的意思是还没登记, 不等于无需标注。
        </p>
      </>
    )
  }

  const imageSection = () => {
    if (loading) return <StateMessage title="正在加载图片署名" />
    if (!data) return null
    if (data.images.length === 0) {
      return (
        <StateMessage
          title="目前一张配图都没有"
          detail="库里的图每条都必须带 credit 与 license(两列都是 NOT NULL), 查不到出处的图不进仓库。现在一张都没有, 说明配图还没落库。"
        />
      )
    }
    return (
      <div className="credits__scroll">
        <table className="credits__table">
          <caption className="credits__caption">共 {data.image_total} 张图</caption>
          <thead>
            <tr>
              <th scope="col">署名</th>
              <th scope="col">许可</th>
              <th scope="col">张数</th>
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
      <h2 className="page__title">数据来源与许可</h2>
      <p className="page__subtitle">景点数据与图片署名由数据库聚合生成, 不是手写的清单</p>

      {error ? (
        <StateMessage tone="error" title="来源清单加载失败" detail={error} onRetry={reload} />
      ) : null}

      {data?.needs_attention ? (
        <StateMessage
          tone="error"
          title="有 share-alike 来源没有登记修改状态"
          detail="ODbL 与 CC BY-SA 要求标注「是否修改过」。请先在 backend/app/api/sources.py 的 SOURCE_MODIFICATIONS 里登记, 再对外发布。"
        />
      ) : null}

      <section className="section">
        <h3 className="section__title">景点数据来源</h3>
        {sourceSection()}
      </section>

      <section className="section">
        <h3 className="section__title">图片署名</h3>
        {imageSection()}
      </section>

      <section className="section">
        <h3 className="section__title">代码与静态素材</h3>
        <div className="credits__scroll">
          <table className="credits__table">
            <thead>
              <tr>
                <th scope="col">名称</th>
                <th scope="col">许可</th>
                <th scope="col">说明</th>
              </tr>
            </thead>
            <tbody>
              {CODE_ASSETS.map((asset) => (
                <tr key={asset.name}>
                  <td>
                    {asset.link ? (
                      <a
                        className="credits__link"
                        href={asset.link}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        {asset.name}
                      </a>
                    ) : (
                      asset.name
                    )}
                  </td>
                  <td>{asset.license}</td>
                  <td>{asset.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <h3 className="section__title">这个应用不做什么</h3>
        <ul className="credits__list">
          <li>不含地图与定位: 没有地图 SDK, 不采集轨迹, 也不上报位置。</li>
          <li>评分只来自用户主动打分: 种子数据里的评分恒为 0, 不伪造数字。</li>
          <li>推荐结果由离线任务整批写入, 接口只读结果表, 不实时跟踪任何个人。</li>
        </ul>
      </section>
    </main>
  )
}

export default Credits