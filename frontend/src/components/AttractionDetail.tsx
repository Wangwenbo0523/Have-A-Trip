import React, { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"

import { fetchAttraction, fetchSimilar, getDeviceId, reportEvent } from "../api/client"
import { useApi } from "../hooks/useApi"
import { useI18n } from "../i18n"
import { localizedName, namesFor } from "../lib/display"
import { HERITAGE_TEXT } from "../lib/grade"
import AiAskBox from "./AiAskBox"
import AttractionList from "./AttractionList"
import AttractionPlan from "./AttractionPlan"
import ExternalVideoSearch from "./ExternalVideoSearch"
import StateMessage from "./StateMessage"
import Loader from "./utils/Loader"
import "../styles/detail.css"

const AttractionDetail = () => {
  const { slug = "" } = useParams<{ slug: string }>()
  const { t, lang } = useI18n()
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

  /**
   * 评分 / 票价 / 时长三种写法放在组件里而不是模块级: 它们都要用当前语种的文案,
   * 而模块级常量拿不到语种(同 AttractionCard)。
   */
  const ratingText = (average: number, count: number) =>
    count > 0 ? t("card.rating", { avg: average.toFixed(1), count }) : t("card.rating.none")

  /**
   * 票价。库里只有 ticket_price 没有币种字段, 所以只对境内写人民币符号 —— 境外景点
   * 按数据口径只会写 0(确定免费), 真出现金额时也不替它编一个币种。
   */
  const priceText = (price: number | null, countryCode: string) => {
    if (price === null || price === undefined) return t("detail.tbd")
    if (price === 0) return t("card.price.free")
    return countryCode === "CN" ? `¥${price}` : t("card.price.ticketed")
  }

  const hoursText = (hours: number | null) =>
    hours === null || hours === undefined ? t("detail.tbd") : t("detail.hours", { hours })

  if (loading) return <main className="page"><Loader /></main>

  if (error) {
    return (
      <main className="page">
        <StateMessage
          title={t("detail.error.title")}
          detail={error}
          tone="error"
          onRetry={reload}
        />
        <p className="detail__back">
          <Link to="/attractions">{t("detail.back")}</Link>
        </p>
      </main>
    )
  }

  if (!data) return null

  // 中文界面: 中文名当标题、英文名当副标题; 英文界面: 有 name_en 就角色对调
  const { title, subtitle } = namesFor(lang, data)

  return (
    <main className="page">
      <p className="detail__back">
        <Link to={`/category/${data.category.slug}`}>← {data.category.name}</Link>
      </p>

      <header className="detail__head">
        <h2 className="detail__title">{title}</h2>
        {subtitle ? <p className="detail__titleEn">{subtitle}</p> : null}
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
          <img src={data.cover_image} alt={title} />
        </figure>
      ) : null}

      <div className="detail__actions">
        <button type="button" className="detail__action" onClick={onFavorite} disabled={favorited}>
          {favorited ? t("detail.favorited") : t("detail.favorite")}
        </button>
        <div className="detail__rate" role="group" aria-label={t("detail.rate.groupAria")}>
          <span>{t("detail.rate.label")}</span>
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              className="detail__star"
              aria-label={t("detail.rate.starAria", { star })}
              onClick={() => onRate(star)}
            >
              ★
            </button>
          ))}
        </div>
      </div>

      <dl className="detail__facts">
        <div>
          <dt>{t("detail.fact.rating")}</dt>
          <dd>{ratingText(data.rating_avg, data.rating_count)}</dd>
        </div>
        <div>
          <dt>{t("detail.fact.price")}</dt>
          <dd>{priceText(data.ticket_price, data.country_code)}</dd>
        </div>
        <div>
          <dt>{t("detail.fact.hours")}</dt>
          <dd>{hoursText(data.suggested_hours)}</dd>
        </div>
        <div>
          <dt>{t("detail.fact.season")}</dt>
          <dd>{data.best_season || t("detail.tbd")}</dd>
        </div>
        {data.a_level ? (
          <div>
            <dt>{t("detail.fact.level")}</dt>
            <dd>{t("grade.aLevel", { level: data.a_level })}</dd>
          </div>
        ) : null}
        {data.heritage ? (
          <div>
            <dt>{t("detail.fact.heritage")}</dt>
            <dd>{t(HERITAGE_TEXT[data.heritage].full)}</dd>
          </div>
        ) : null}
        <div>
          <dt>{t("detail.fact.address")}</dt>
          <dd>{data.address || t("detail.tbd")}</dd>
        </div>
        <div>
          <dt>{t("detail.fact.category")}</dt>
          <dd>
            <Link to={`/category/${data.category.slug}`}>{data.category.name}</Link>
          </dd>
        </div>
      </dl>

      {/* 追问紧跟在事实表后面: 刚看完票价/时长/季节, 正是想问点什么的时候 */}
      <AiAskBox slug={data.slug} name={title} />

      {data.description ? (
        <section className="detail__section">
          <h3 className="section__title">{t("detail.description")}</h3>
          <p className="detail__text">{data.description}</p>
        </section>
      ) : (
        <StateMessage
          title={t("detail.descriptionEmpty.title")}
          detail={t("detail.descriptionEmpty.detail")}
        />
      )}

      {data.plans.length > 0 ? (
        <section className="detail__section">
          <h3 className="section__title">{t("detail.plans")}</h3>
          <div className="planList">
            {[...data.plans]
              .sort((a, b) => a.days - b.days)
              .map((plan) => (
                <AttractionPlan key={plan.slug} plan={plan} />
              ))}
          </div>
          <p className="plan__disclaimer">{t("detail.plans.disclaimer")}</p>
        </section>
      ) : null}

      {data.images.length > 0 ? (
        <section className="detail__section">
          <h3 className="section__title">{t("detail.gallery")}</h3>
          <ul className="detail__gallery">
            {data.images.map((image) => (
              <li key={image.url}>
                <img src={image.url} alt={image.caption || title} loading="lazy" />
                <p className="detail__credit">
                  {image.credit} · {image.license}
                </p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* 站外搜索的关键词跟着界面显示的标题走, 见 src/lib/display.ts */}
      <ExternalVideoSearch keyword={localizedName(lang, data)} />

      {/* source / license 每个景点必填, 直接展示 —— 这是将来闭源时的数据层保险 */}
      <p className="detail__source">
        {t("detail.source", { source: data.source, license: data.license })}
        {data.source_url ? (
          <>
            {" "}
            ·{" "}
            <a href={data.source_url} target="_blank" rel="noreferrer noopener">
              {t("detail.source.original")}
            </a>
          </>
        ) : null}
      </p>

      <section className="detail__section" aria-labelledby="detail-similar">
        <h3 className="section__title" id="detail-similar">
          {t("detail.similar")}
        </h3>
        {similar.loading ? <Loader /> : null}
        {!similar.loading && similar.data && similar.data.length > 0 ? (
          <AttractionList attractions={similar.data} />
        ) : null}
        {!similar.loading && similar.data && similar.data.length === 0 ? (
          <StateMessage
            title={t("detail.similarEmpty.title")}
            detail={t("detail.similarEmpty.detail")}
          />
        ) : null}
      </section>
    </main>
  )
}

export default AttractionDetail
