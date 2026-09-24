import React from "react"
import { Link } from "react-router-dom"

import { useI18n } from "../i18n"
import { namesFor } from "../lib/display"
import type { Attraction } from "../types"
import AttractionGradeBadge from "./AttractionGradeBadge"
import "../styles/AttractionCard.css"

const AttractionCard = ({ attraction }: { attraction: Attraction }) => {
  const { t, lang } = useI18n()
  const { title, subtitle } = namesFor(lang, attraction)

  const ratingText = (average: number, count: number) =>
    count > 0 ? t("card.rating", { avg: average.toFixed(1), count }) : t("card.rating.none")

  /**
   * 票价。库里只有 ticket_price 没有币种字段, 所以只对境内写人民币符号 —— 境外景点
   * 按数据口径只会写 0(确定免费), 真出现金额时也不替它编一个币种。
   */
  const priceText = (price: number | null, countryCode: string) => {
    if (price === null || price === undefined) return t("card.price.tbd")
    if (price === 0) return t("card.price.free")
    return countryCode === "CN" ? `¥${price}` : t("card.price.ticketed")
  }

  const locationText =
    [attraction.city, attraction.province].filter(Boolean).join(" · ") || t("card.location.tbd")

  return (
    <Link className="attractionCard" to={`/attraction/${attraction.slug}`}>
      <div className="attractionCard__media">
        {attraction.cover_image ? (
          <img
            className="attractionCard__image"
            src={attraction.cover_image}
            alt={title}
            loading="lazy"
          />
        ) : (
          // 没有配图时用首字占位, 不要留一个破图
          <span className="attractionCard__placeholder" aria-hidden="true">
            {title.slice(0, 1)}
          </span>
        )}
        {/* 分类名是库里的内容, 没有英文版本 */}
        <span className="attractionCard__category">{attraction.category.name}</span>
        <AttractionGradeBadge aLevel={attraction.a_level} heritage={attraction.heritage} />
      </div>

      <div className="attractionCard__body">
        <h3 className="attractionCard__name">{title}</h3>
        {subtitle ? <p className="attractionCard__nameEn">{subtitle}</p> : null}
        <p className="attractionCard__location">{locationText}</p>
        <p className="attractionCard__summary">{attraction.summary || t("card.summary.none")}</p>

        {attraction.tags.length > 0 ? (
          <ul className="attractionCard__tags">
            {attraction.tags.slice(0, 4).map((tag) => (
              <li key={tag.slug}>{tag.name}</li>
            ))}
          </ul>
        ) : null}

        <p className="attractionCard__foot">
          <span>{ratingText(attraction.rating_avg, attraction.rating_count)}</span>
          <span>{priceText(attraction.ticket_price, attraction.country_code)}</span>
        </p>
      </div>
    </Link>
  )
}

export default AttractionCard
