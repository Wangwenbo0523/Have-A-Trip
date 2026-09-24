import React from "react"
import { Link } from "react-router-dom"

import type { Attraction } from "../types"
import AttractionGradeBadge from "./AttractionGradeBadge"
import "../styles/AttractionCard.css"

const ratingText = (average: number, count: number) =>
  count > 0 ? `${average.toFixed(1)} 分 · ${count} 人评` : "暂无评分"

/**
 * 票价。库里只有 ticket_price 没有币种字段, 所以只对境内写人民币符号 —— 境外景点
 * 按数据口径只会写 0(确定免费), 真出现金额时也不替它编一个币种。
 */
const priceText = (price: number | null, countryCode: string) => {
  if (price === null || price === undefined) return "票价待补"
  if (price === 0) return "免费"
  return countryCode === "CN" ? `¥${price}` : "需购票"
}

const locationText = (attraction: Attraction) =>
  [attraction.city, attraction.province].filter(Boolean).join(" · ") || "地点待补"

const AttractionCard = ({ attraction }: { attraction: Attraction }) => (
  <Link className="attractionCard" to={`/attraction/${attraction.slug}`}>
    <div className="attractionCard__media">
      {attraction.cover_image ? (
        <img
          className="attractionCard__image"
          src={attraction.cover_image}
          alt={attraction.name}
          loading="lazy"
        />
      ) : (
        // 没有配图时用首字占位, 不要留一个破图
        <span className="attractionCard__placeholder" aria-hidden="true">
          {attraction.name.slice(0, 1)}
        </span>
      )}
      <span className="attractionCard__category">{attraction.category.name}</span>
      <AttractionGradeBadge aLevel={attraction.a_level} heritage={attraction.heritage} />
    </div>

    <div className="attractionCard__body">
      <h3 className="attractionCard__name">{attraction.name}</h3>
      {attraction.name_en ? <p className="attractionCard__nameEn">{attraction.name_en}</p> : null}
      <p className="attractionCard__location">{locationText(attraction)}</p>
      <p className="attractionCard__summary">{attraction.summary || "暂无简介"}</p>

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

export default AttractionCard
