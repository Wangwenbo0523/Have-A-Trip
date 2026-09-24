/**
 * 与后端契约一一对应的类型。
 *
 * 契约来源: backend/app/schemas.py —— 改这里之前先改后端, 反之亦然。
 * 字段口径见 db/README.md。
 */

export interface Category {
  slug: string
  name: string
}

export interface CategoryWithCount extends Category {
  attraction_count: number
}

export interface Tag {
  slug: string
  name: string
}

export interface TagWithCount extends Tag {
  attraction_count: number
}

export interface AttractionImage {
  url: string
  caption: string | null
  credit: string
  license: string
}

/** 列表 / 卡片用的字段。后端刻意不含 description, 列表页不需要那段长文本。 */
export interface Attraction {
  id: number
  slug: string
  name: string
  name_en: string | null
  summary: string | null
  category: Category
  city: string | null
  province: string | null
  tags: Tag[]
  cover_image: string | null
  rating_avg: number
  rating_count: number
  ticket_price: number | null
  suggested_hours: number | null
}

export interface AttractionDetail extends Attraction {
  description: string | null
  country_code: string
  address: string | null
  /** 仅用于同城聚合等静态计算; 前端不渲染地图, 也不做定位 */
  lat: number | null
  lon: number | null
  best_season: string | null
  images: AttractionImage[]
  source: string
  license: string
  source_url: string | null
  updated_at: string
}

export interface Page<T> {
  items: T[]
  page: number
  size: number
  total: number
}

export type EventType = "view" | "favorite" | "rate" | "share"

export interface EventPayload {
  device_id: string
  attraction_id: number
  event_type: EventType
  /** 只有 event_type === "rate" 能带, 后端与数据库两侧都校验 */
  rating?: number
  dwell_ms?: number
}

export interface Recommendation {
  attraction: Attraction
  rank: number
  score: number | null
  /** 产出这条推荐的算法: recbole / content-based / popular-fallback */
  algo: string
  reason: string
}

export interface PageQuery {
  page?: number
  size?: number
  category?: string
  city?: string
  tag?: string
  q?: string
  sort?: "rating" | "newest" | "name"
}

/** 数据来源的修改状态。unregistered 是告警态, 不是正常的第四种状态。 */
export type ModificationStatus = "modified" | "unmodified" | "not-applicable" | "unregistered"

/** 一条 (source, license) 聚合。声明页从接口拿, 不在前端写死。 */
export interface SourceRecord {
  source: string
  license: string
  attraction_count: number
  province_count: number
  /** 许可是否带相同方式共享义务(ODbL / CC BY-SA)。为真时页面必须显示修改状态 */
  share_alike: boolean
  modification: ModificationStatus
}

/** 一条 (credit, license) 聚合。图片的署名与许可是数据库字段, 不是文档里的口头约定。 */
export interface ImageCredit {
  credit: string
  license: string
  image_count: number
}

export interface SourcesResponse {
  sources: SourceRecord[]
  images: ImageCredit[]
  attraction_total: number
  image_total: number
  /** 库里有 share-alike 来源却没登记修改状态 */
  needs_attention: boolean
}
