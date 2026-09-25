import { fetchAttractions } from "../api/client"
import type { Attraction } from "../types"

/**
 * 一次取多少条。对应 backend/app/config.py 的 max_page_size —— 服务端上限是 100,
 * 这里跟着写 100, 只影响请求次数, 不影响正确性(页数按响应的 size 算)。
 */
const PAGE_SIZE = 100

/**
 * 取到**全部**已发布景点。
 *
 * 对比页和动态区的景点选择器都要求"全库都在候选里"。只取第一页不行: 景点数一旦超过
 * 一页, 后面的就选不到, 而从分享链接进来的 ?a=<slug> 还会被判成"已下架",
 * 静悄悄把用户的比较对象换掉。
 *
 * 页数从响应的 size 算而不是写死 —— 服务端有权把 size 压小。
 */
export async function fetchAllAttractions(): Promise<Attraction[]> {
  const first = await fetchAttractions({ page: 1, size: PAGE_SIZE, sort: "name" })
  const pages = first.size > 0 ? Math.ceil(first.total / first.size) : 1
  if (pages <= 1) return first.items

  const rest = await Promise.all(
    Array.from({ length: pages - 1 }, (_, index) =>
      fetchAttractions({ page: index + 2, size: PAGE_SIZE, sort: "name" }),
    ),
  )
  return [...first.items, ...rest.flatMap((page) => page.items)]
}
