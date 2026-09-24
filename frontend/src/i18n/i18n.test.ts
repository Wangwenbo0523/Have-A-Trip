import { describe, expect, it } from "vitest"

import { LANG_STORAGE_KEY, detectLang, format, translate, type MessageKey } from "./index"
import { messages } from "./messages"

/** 文案里出现的占位符名字, 排序后只比集合不比顺序。 */
const placeholders = (text: string) =>
  [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort()

describe("文案表", () => {
  it("中英两张表的键完全一致", () => {
    expect(Object.keys(messages.en).sort()).toEqual(Object.keys(messages.zh).sort())
  })

  it("没有空文案, 且英文表的占位符与中文表一一对应", () => {
    for (const key of Object.keys(messages.zh) as MessageKey[]) {
      expect(messages.zh[key].trim(), key).not.toBe("")
      expect(messages.en[key].trim(), key).not.toBe("")
      // 英文表少了 {count} 这类占位符, 页面上就会少一个数字
      expect(placeholders(messages.en[key]), key).toEqual(placeholders(messages.zh[key]))
    }
  })
})

describe("format", () => {
  it("按名字替换占位符", () => {
    expect(format("第 {page} / {total} 页", { page: 2, total: 9 })).toBe("第 2 / 9 页")
  })

  it("缺变量时原样留着占位符, 不变成空串", () => {
    expect(format("共 {count} 个")).toBe("共 {count} 个")
    expect(format("共 {count} 个", { other: 1 })).toBe("共 {count} 个")
  })
})

describe("translate", () => {
  it("按语种查表", () => {
    expect(translate("zh", "nav.home")).toBe("首页")
    expect(translate("en", "nav.home")).toBe("Home")
  })

  it("英文表缺键时回退中文, 不会把 key 渲染到页面上", () => {
    const en = messages.en as Record<string, string>
    const saved = en["nav.home"]
    delete en["nav.home"]
    try {
      expect(translate("en", "nav.home")).toBe(messages.zh["nav.home"])
    } finally {
      en["nav.home"] = saved
    }
  })

  it("两张表都没有的键才原样返回, 便于发现漏配", () => {
    expect(translate("zh", "nope.nope" as MessageKey)).toBe("nope.nope")
  })
})

describe("detectLang", () => {
  it("存过的选择优先, 否则默认中文", () => {
    window.localStorage.clear()
    expect(detectLang()).toBe("zh")

    window.localStorage.setItem(LANG_STORAGE_KEY, "en")
    expect(detectLang()).toBe("en")

    // 非法值(旧版本残留 / 手改过 localStorage)当没存过
    window.localStorage.setItem(LANG_STORAGE_KEY, "fr")
    expect(detectLang()).toBe("zh")

    window.localStorage.clear()
  })
})
