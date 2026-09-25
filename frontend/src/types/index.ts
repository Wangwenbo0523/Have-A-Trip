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
/**
 * 景区质量等级(GB/T 17775), 只对中国大陆景区有值。
 * 世界遗产没有 A 级, 所以它不在这条刻度上 —— 见 GradeFilter。
 */
export type ALevel = "5A" | "4A" | "3A"

/** UNESCO 世界遗产类别。 */
export type Heritage = "cultural" | "natural" | "mixed"

/**
 * 列表页的等级筛选。5A/4A/3A 是中国景区的质量等级, heritage 表示「已列入 UNESCO
 * 世界遗产名录」—— 两套刻度, 各占一个取值, 不合并成一条线。
 */
export type GradeFilter = ALevel | "heritage"

/** 旅游方案里的一步。day_no 从 1 起, 同一天内按 sort 升序。 */
export interface PlanStep {
  day_no: number
  sort: number
  title: string
  detail: string
  duration_hours: number | null
  tip: string | null
}

/** 方案的花费档次。只给档次不给金额 —— 具体价格是易变信息。 */
export type PlanBudgetLevel = "free" | "low" | "mid" | "high"

/** 一个景点的游玩方案, 内容是本仓库自采的行程建议, 不是官方线路。 */
export interface Plan {
  slug: string
  title: string
  days: number
  budget_level: PlanBudgetLevel | null
  best_for: string | null
  summary: string
  steps: PlanStep[]
}

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
  /** 卡片按国别决定票价怎么写: 境内是人民币, 境外库里没有币种字段 */
  country_code: string
  /** 景区质量等级; null 表示未核实, 不是「无等级」 */
  a_level: ALevel | null
  /** 世界遗产类别; null 表示未核实 */
  heritage: Heritage | null
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
  plans: Plan[]
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

/**
 * 就近推荐用到了哪一层。四档: 同城 -> 同省 -> 国内 -> 全部。库里的 lat/lon 全是 NULL
 * (见 db/README.md 的数据口径), 算不出公里数, 所以「近」只能按行政层级近似。
 * world 只在库很小、或访客已知在境外时才会出现。
 */
export type NearbyScope = "city" | "region" | "nation" | "world"

/**
 * 首页「出去走走」的结果。契约来源: backend/app/schemas.py 的 NearbyResult。
 *
 * `scope` 取结果里最远的那一层 —— 三个里掺进了国内/境外的随机就不是纯就近, 页面上必须
 * 按它如实说明依据(nation 说的是「这批从国内抽的」, world 才是「从全部景点抽的」)。`located` 是「在你库里有收录的城市/省份上对上了」, 不是「认出了你的 IP」。
 */
export interface NearbyResult {
  items: Attraction[]
  located: boolean
  scope: NearbyScope
  /** 库内取值(不是归属地原文), 命中不到就是 null */
  city: string | null
  region: string | null
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
  /** 等级筛选; 不传就是全部 */
  grade?: GradeFilter
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

/**
 * 看板分布里的一档。
 *
 * key 是机器可读的取值(country_code / 5A / cultural / 分类 slug), label 是展示名
 * —— 分类的 label 是库里的分类名(内容, 不翻译), 其余取值的 label 与 key 相同。
 * key === "unknown" 表示档案里没填, 页面显示成「未核实」, 不显示成「无等级」。
 */
export interface StatSlice {
  key: string
  label: string
  count: number
}

/** 景点库总览。后端只统计已发布景点, 与 /sources 同一口径。 */
export interface StatsResponse {
  attraction_total: number
  image_total: number
  plan_total: number
  /** 覆盖的省级行政区数; 省份为空的景点不计入 */
  province_total: number
  /** 境内/境外按 country_code 分, 前端按 key === "CN" 判断 */
  by_country: StatSlice[]
  by_category: StatSlice[]
  by_a_level: StatSlice[]
  by_heritage: StatSlice[]
  /** 与 /sources 同一份聚合 */
  sources: SourceRecord[]
  needs_attention: boolean
}

// ---------------------------------------------------------------- AI 一句话检索
//
// 契约真身是 backend/app/schemas.py。模型只把这句话解析成筛选条件,
// items 永远来自库内档案 —— 所以这里没有「模型生成的景点」这种类型。

/** 解析出来的筛选条件, 与 /attractions 的查询参数一一对应。 */
export interface AIFilters {
  category: string | null
  tag: string | null
  grade: GradeFilter | null
  city: string | null
  q: string | null
  sort: "rating" | "newest" | "name"
}

/**
 * AI 入口是否可用。默认配置(后端 LLM_PROVIDER=none)下 available 为 false,
 * 页面据此决定要不要显示入口 —— 不给一个点了没反应的按钮。
 */
export interface AIStatus {
  available: boolean
  provider: string
  model: string | null
  /**
   * 语义检索是否可用。与 available 分开: 只配了向量模型、没配对话模型时,
   * 「用一句话找景点」不可用而语义检索可用 —— 合成一个状态位会把能用的入口一起藏起来。
   */
  embedding_available?: boolean
  embedding_model?: string | null
  /** 已向量化的已发布景点数 / 已发布景点总数 */
  embedded?: number
  published?: number
  disclaimer: string
}

/**
 * 一句话检索的结果。
 *
 * interpreted=false 或 degraded=true 表示这次没走成模型(未配置 / 超时 / 返回不合法),
 * 后端已退回关键词检索 —— 这是降级, 不是错误, 所以 note 与 degraded 都要显示给用户。
 */
export interface AISearchResult {
  query: string
  interpreted: boolean
  degraded: boolean
  model: string | null
  note: string
  filters: AIFilters
  items: Attraction[]
  page: number
  size: number
  total: number
  /**
   * 空结果放宽时被摘掉的条件(字段名)。非空表示这条结果不是原本那几个条件
   * 查出来的 —— 放宽过就得说, 所以 note 里也会带一句人话说明。
   */
  relaxed: string[]
  /** 结构化条件一条都没有时, 结果是向量近邻。与 relaxed 是两种兜底, 分开标。 */
  semantic_fallback: boolean
  /** 后端给的免责声明, 必须显示 */
  disclaimer: string
}
/**
 * 就某个景点追问一句的回答。
 *
 * grounded=false 表示这段答案是后端拼的档案摘录(降级时), 不是模型写的;
 * degraded=true 表示这次没走成模型。两者都不代表出错 —— 追问失败不该是报错页。
 */
export interface AIAskResult {
  slug: string
  question: string
  grounded: boolean
  degraded: boolean
  model: string | null
  answer: string
  note: string
  /** 模型自报用了哪些档案字段; dropped 是它报了但档案里没有的 */
  cited: string[]
  dropped: string[]
  disclaimer: string
}

/**
 * 推荐位润色的结果。reasons 是 slug -> 文案, 后端保证**每条推荐都一定有文案**
 * (润色不成功的那几条直接给回原来的理由), 所以页面照常渲染即可。
 *
 * polished=false 表示这次没走成模型, 此时 reasons 里就是后端的原理由。
 */
export interface AIRefinedNote {
  slug: string
  note: string
}

export interface AIRecommendNotes {
  polished: boolean
  degraded: boolean
  model: string | null
  note: string
  reasons: AIRefinedNote[]
  /** 被丢掉的条目: 模型报了不存在的 slug, 或改写内容查不到依据 */
  dropped: string[]
  disclaimer: string
}

// ---------------------------------------------------------------- 语义检索
//
// 与「一句话检索」的分工: 那条路是模型把句子解析成筛选条件, 这条路是把句子向量化
// 与景点描述比相似度 —— 不需要对话模型, 只配了向量模型也能用。

export interface SemanticHit {
  attraction: Attraction
  /** 余弦相似度 0..1; 关键词兜底时为 null */
  score: number | null
  /** semantic = 向量近邻; keyword = 向量不可用时的关键词兜底 */
  match: "semantic" | "keyword"
}

/**
 * 语义检索结果。
 *
 * degraded=true 表示这次没走成向量(未配置 / 库内没向量 / 维度不一致 / 服务不可用),
 * 后端**已经就地退回关键词检索**并照样返回条目 —— 所以 items 仍然可以用。
 */
export interface SemanticSearchResult {
  query: string
  degraded: boolean
  model: string | null
  note: string
  embedded: number
  published: number
  items: SemanticHit[]
  total: number
  disclaimer: string
}

// ---------------------------------------------------------------- 行程生成

export type ItineraryStatus =
  | "pending"
  | "generating"
  | "succeeded"
  | "failed"
  | "rejected"

/** 提交成功后的受理凭据。之后一律用 token 取, 不用 id —— id 可枚举。 */
export interface ItineraryAccepted {
  token: string
  status: ItineraryStatus
}

export interface ItineraryItem {
  day_index: number
  seq: number
  attraction_id: number
  /** 生成当时的景点名快照, 景点改名或下架后仍显示当时那一刻 */
  name: string
  note: string
  reason: string
}

export interface ItineraryUsage {
  prompt_tokens: number
  completion_tokens: number
}

export interface Itinerary {
  token: string
  status: ItineraryStatus
  days: number
  items: ItineraryItem[]
  error: string | null
  note: string | null
  model: string | null
  usage: ItineraryUsage | null
  generated_at: string | null
  created_at: string
  /** 轮询上限(秒)。超过它就该停, 不要一直转圈 */
  max_poll_seconds: number
  disclaimer: string
}

/** 被限额拦下时后端给的结构化原因(HTTP 429 的 detail)。 */
export interface ItineraryRejection {
  status: "rejected"
  reason: string
  retry_after: string
  limit?: number
}

// ---------------------------------------------------------------- 动态区

/**
 * 动态的作者。**只有署名** —— 没有账号体系, 服务端也不回 device_id:
 * 那个串是删除权限的凭据, 列出来等于把别人的删除权交给所有人。
 */
export interface PostAuthor {
  name: string
}

/**
 * 动态挂着的景点。slug 为 null 表示景点已下架或已删除: 名字照显, 但没有链接可点。
 */
export interface PostAttraction {
  slug: string | null
  name: string
  name_en: string | null
}

export interface Post {
  id: number
  author: PostAuthor
  body: string
  attraction: PostAttraction | null
  created_at: string
  /** 是不是这台设备发的。只有 true 才给删除按钮 —— 服务端删之前还会再查一次 */
  mine: boolean
}

export interface PostPage {
  items: Post[]
  page: number
  size: number
  total: number
  /** 当天发帖上限(配置值) */
  daily_limit: number
  /** 今天已经发了几条; 没带身份请求时为 null */
  used_today: number | null
  disclaimer: string
}

/** 发一条动态。attraction_slug 留空就是纯文字。 */
export interface PostPayload {
  body: string
  nickname?: string
  attraction_slug?: string
}
