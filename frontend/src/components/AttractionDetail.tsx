import React, { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"

import { fetchAttraction, fetchSimilar, getDeviceId, reportEvent } from "../api/client"
import { useApi } from "../hooks/useApi"
import { HERITAGE_LABELS, aLevelText } from "../lib/grade"
import AttractionList from "./AttractionList"
import AttractionPlan from "./AttractionPlan"
import ExternalVideoSearch from "./ExternalVideoSearch"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"
import "../styles/detail.css"

const ratingText = (average: number, count: number) =>
  count > 0 ? `${average.toFixed(1)} 分 · ${count} 人评` : "暂无评分"

/**
 * 票价。库里只有 ticket_price 没有币种字段, 所以只对境内写人民币符号 —— 境外景点
 * 按数据口径只会写 0(确定免费), 真出现金额时也不替它编一个币种。
 */
const priceText = (price: number | null, countryCode: string) => {
  if (price === null || price === undefined) return "待补"
  if (price === 0) return "免费"
  return countryCode === "CN" ? `¥${price}` : "需购票"
}

const hoursText = (hours: number | null) =>
  hours === null || hours === undefined ? "待补" : `约 ${hours} 小时`

const AttractionDetail = () => {
  const { slug = "" } = useParams<{ slug: string }>()
  const { data, loading, error, reload } = useApi(() => fetchAttraction(slug), [slug])
  const similar = useApi(() => fetchSimilar(slug, 6), [slug])
  const [favorited, setFavorited] = useState(false)

  const attractionId = data?.id ?? null

  // 进详情页算一次浏览行为。这是推荐系统的原料 —— 只记录行为, 不采集位置。
  useEffect(() => {
    if (attractionId === null) return
    reportEvent({
      device_id: getDeviceId(),
      attraction_id: attractionId,
      event_type: "view",
    }).catch(() => {
      // 埋点失败不影响阅读, 什么都不做
    })
  }, [attractionId])

  const onFavorite = () => {
    if (attractionId === null) return
    reportEvent({
      device_id: getDeviceId(),
      attraction_id: attractionId,
      event_type: "favorite",
    })
      .then(() => setFavorited(true))
      .catch(() => setFavorited(false))
  }

  const onRate = (rating: number) => {
    if (attractionId === null) return
    reportEvent({
      device_id: getDeviceId(),
      attraction_id: attractionId,
      event_type: "rate",
      rating,
    })
      .then(() => reload())
      .catch(() => {
        // 评分失败就保持原样, 不弹窗打断
      })
  }

  if (loading) return <main className="page"><Loader /></main>

  if (error) {
    return (
      <main className="page">
        <StateMessage
          title="打不开这个景点"
          detail={error}
          tone="error"
          onRetry={reload}
        />
        <p className="detail__back">
          <Link to="/attractions">← 回景点列表</Link>
        </p>
      </main>
    )
  }

  if (!data) return null

  return (
    <main className="page">
      <p className="detail__back">
        <Link to={`/category/${data.category.slug}`}>← {data.category.name}</Link>
      </p>

      <header className="detail__head">
        <h2 className="detail__title">{data.name}</h2>
        {data.name_en ? <p className="detail__titleEn">{data.name_en}</p> : null}
        <p className="detail__meta">
          {[data.city, data.province, data.country_code].filter(Boolean).join(" · ")}
        </p>
        {data.tags.length > 0 ? (
          <ul className="detail__tags">
            {data.tags.map((tag) => (
              <li key={tag.slug}>{tag.name}</li>
            ))}
          </ul>
        ) : null}
      </header>

      {data.cover_image ? (
        <figure className="detail__cover">
          <img src={data.cover_image} alt={data.name} />
        </figure>
      ) : null}

      <div className="detail__actions">
        <button type="button" className="detail__action" onClick={onFavorite} disabled={favorited}>
          {favorited ? "已收藏" : "收藏"}
        </button>
        <div className="detail__rate" role="group" aria-label="给这个景点打分">
          <span>打分:</span>
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              className="detail__star"
              aria-label={`${star} 分`}
              onClick={() => onRate(star)}
            >
              ★
            </button>
          ))}
        </div>
      </div>

      <dl className="detail__facts">
        <div>
          <dt>评分</dt>
          <dd>{ratingText(data.rating_avg, data.rating_count)}</dd>
        </div>
        <div>
          <dt>票价</dt>
          <dd>{priceText(data.ticket_price, data.country_code)}</dd>
        </div>
        <div>
          <dt>建议游览</dt>
          <dd>{hoursText(data.suggested_hours)}</dd>
        </div>
        <div>
          <dt>最佳季节</dt>
          <dd>{data.best_season || "待补"}</dd>
        </div>
        {data.a_level ? (
          <div>
            <dt>景区等级</dt>
            <dd>{aLevelText(data.a_level)}</dd>
          </div>
        ) : null}
        {data.heritage ? (
          <div>
            <dt>世界遗产</dt>
            <dd>{HERITAGE_LABELS[data.heritage].full}</dd>
          </div>
        ) : null}
        <div>
          <dt>地址</dt>
          <dd>{data.address || "待补"}</dd>
        </div>
        <div>
          <dt>分类</dt>
          <dd>
            <Link to={`/category/${data.category.slug}`}>{data.category.name}</Link>
          </dd>
        </div>
      </dl>

      {data.description ? (
        <section className="detail__section">
          <h3 className="section__title">景点介绍</h3>
          <p className="detail__text">{data.description}</p>
        </section>
      ) : (
        <StateMessage title="这个景点还没有详细介绍" detail="资料正在补录中" />
      )}

      {data.plans.length > 0 ? (
        <section className="detail__section">
          <h3 className="section__title">旅游方案</h3>
          <div className="planList">
            {[...data.plans]
              .sort((a, b) => a.days - b.days)
              .map((plan) => (
                <AttractionPlan key={plan.slug} plan={plan} />
              ))}
          </div>
          <p className="plan__disclaimer">
            方案按公开信息自采, 是行程建议而不是官方线路; 花费只给档次, 具体价格随季节浮动。
          </p>
        </section>
      ) : null}

      {data.images.length > 0 ? (
        <section className="detail__section">
          <h3 className="section__title">图集</h3>
          <ul className="detail__gallery">
            {data.images.map((image) => (
              <li key={image.url}>
                <img src={image.url} alt={image.caption || data.name} loading="lazy" />
                <p className="detail__credit">
                  {image.credit} · {image.license}
                </p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <ExternalVideoSearch keyword={data.name} />

      {/* source / license 每个景点必填, 直接展示 —— 这是将来闭源时的数据层保险 */}
      <p className="detail__source">
        数据来源: {data.source} · 许可: {data.license}
        {data.source_url ? (
          <>
            {" "}
            ·{" "}
            <a href={data.source_url} target="_blank" rel="noreferrer noopener">
              原始链接
            </a>
          </>
        ) : null}
      </p>

      <section className="detail__section" aria-labelledby="detail-similar">
        <h3 className="section__title" id="detail-similar">
          相似景点
        </h3>
        {similar.loading ? <Loader /> : null}
        {!similar.loading && similar.data && similar.data.length > 0 ? (
          <AttractionList attractions={similar.data} />
        ) : null}
        {!similar.loading && similar.data && similar.data.length === 0 ? (
          <StateMessage title="暂时没有相似的景点" detail="等收录的景点再多一些" />
        ) : null}
      </section>
    </main>
  )
}

export default AttractionDetail
