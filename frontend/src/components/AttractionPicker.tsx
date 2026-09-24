import React, { useEffect, useMemo, useRef, useState } from "react"

import { useI18n } from "../i18n"
import { localizedName, namesFor } from "../lib/display"
import type { Attraction } from "../types"

import "../styles/picker.css"

interface AttractionPickerProps {
  id: string
  label: string
  /** 当前选中的 slug; 空串表示还没选 */
  value: string
  options: Attraction[]
  onChange: (slug: string) => void
}

/** 中英文名都参与匹配: 中文界面想按英文名找、英文界面想按中文名找, 都说得通。 */
const searchTextOf = (item: Attraction) =>
  [item.name, item.name_en ?? ""].join(" ").toLowerCase()

/**
 * 可搜索的景点选择器。
 *
 * 为什么不用原生 `<select>`: 库里已经是 156 个景点, 原生下拉会把 156 行一次铺开 ——
 * 既搜不了也扫不动, 而这个数字只会继续涨。所以做成 combobox: 输入即筛, 上下键移动,
 * 回车落定, Esc 取消。
 *
 * **写回 URL 的永远是 slug, 而且只有从列表里选中才会写。** 手打半个名字不改值:
 * 否则一个不存在的 slug 会进 URL, 分享出去的链接就坏了(这个坑刚在候选只有 100 条时
 * 踩过一次, 见 docs/PLAN.md 的 v3.10)。
 *
 * 聚焦时输入框**清空**、直接进搜索态, 而不是把当前名字全选上。全选看着更聪明, 但
 * `select()` 会被点击带来的光标定位盖掉, 于是接着打的那几个字是**追加**在新名字后面
 * ("西湖" + "故宫"), 筛出个空结果。清空没有这个歧义; 当前选中的是谁, 表格抬头和列表
 * 里的高亮都写着。
 *
 * 用户实际会撞上的两个边: **选完再打字**与 **选完再点一下** —— 这两个动作都不会触发
 * focus 事件(focus 一直没离开输入框), 所以 onChange 里要自己置 editing、onClick 里要自己重开列表。
 * 漏了前者, 列表会铺全量而且刚敲的字被受控 value 吞掉; 漏了后者, Esc 之后列表再也叫不回来。
 */
const AttractionPicker = ({ id, label, value, options, onChange }: AttractionPickerProps) => {
  const { t, lang } = useI18n()
  // editing=false 时输入框显示当前选中的名字; true 时显示用户正在敲的内容
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)

  const selected = options.find((item) => item.slug === value) ?? null
  const selectedName = selected ? localizedName(lang, selected) : ""

  const matches = useMemo(() => {
    const needle = editing ? draft.trim().toLowerCase() : ""
    if (!needle) return options
    return options.filter((item) => searchTextOf(item).includes(needle))
  }, [options, editing, draft])

  const listId = `${id}-list`
  const optionId = (index: number) => `${id}-option-${index}`

  // 键盘移动高亮时把它滚进可视区。jsdom 没有 scrollIntoView, 所以要先探一下
  useEffect(() => {
    if (!open) return
    const node = rootRef.current?.querySelector<HTMLElement>(".picker__option.is-active")
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "nearest" })
    }
  }, [open, active])

  /** 进搜索态: 清掉输入、铺全量, 高亮落在当前选中的那一条上(回车可以原地重选)。 */
  const openList = () => {
    const index = matches.findIndex((item) => item.slug === value)
    setOpen(true)
    setEditing(true)
    setDraft("")
    setActive(index >= 0 ? index : 0)
  }

  const closeList = () => {
    setOpen(false)
    setEditing(false)
    setDraft("")
  }

  const commit = (slug: string) => {
    onChange(slug)
    closeList()
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault()
      if (!open) {
        openList()
        return
      }
      const delta = event.key === "ArrowDown" ? 1 : -1
      setActive((current) =>
        matches.length === 0 ? 0 : (current + delta + matches.length) % matches.length,
      )
      return
    }
    if (event.key === "Enter") {
      if (!open) return
      event.preventDefault()
      const picked = matches[active]
      if (picked) commit(picked.slug)
      return
    }
    if (event.key === "Escape") {
      closeList()
    }
  }

  return (
    <div className="picker" ref={rootRef}>
      <label className="picker__label" htmlFor={id}>
        {label}
      </label>
      <div className="picker__field">
        <input
          id={id}
          className="picker__input"
          type="text"
          role="combobox"
          autoComplete="off"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && matches[active] ? optionId(active) : undefined}
          placeholder={t("compare.select")}
          value={editing ? draft : selectedName}
          onChange={(event) => {
            const typed = event.target.value
            // 选完之后焦点还在输入框里, 这时打的字会接在新名字后面 —— 把那一段吃掉,
            // 只留用户真正敲进去的部分 (见上面「聚焦清空」那段说明)
            setDraft(editing || !selectedName ? typed : typed.replace(selectedName, ""))
            // 已经聚焦时再打字不会触发 focus, 这里必须自己进搜索态:
            // 否则筛选用的是空关键词(列表铺全量), 刚敲进去的字还会被受控 value 吞掉
            setEditing(true)
            setOpen(true)
            setActive(0)
          }}
          onFocus={openList}
          // 选完或按 Esc 之后列表收起, 但焦点还在输入框里, 再点一下不会触发 focus —— 手动把列表叫回来
          onClick={() => {
            if (!open) openList()
          }}
          onBlur={closeList}
          onKeyDown={onKeyDown}
        />
        {open ? (
          <ul className="picker__list" id={listId} role="listbox">
            {matches.length === 0 ? (
              <li className="picker__empty" role="presentation">
                {t("compare.pick.empty")}
              </li>
            ) : (
              matches.map((item, index) => {
                const { title, subtitle } = namesFor(lang, item)
                return (
                  <li
                    key={item.slug}
                    id={optionId(index)}
                    className={index === active ? "picker__option is-active" : "picker__option"}
                    role="option"
                    aria-selected={item.slug === value}
                    // 按下时就 preventDefault, 否则输入框先 blur、列表先收起来, click 落空
                    onMouseDown={(event) => event.preventDefault()}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => commit(item.slug)}
                  >
                    <span className="picker__optionName">{title}</span>
                    {subtitle ? <span className="picker__optionAlt">{subtitle}</span> : null}
                  </li>
                )
              })
            )}
          </ul>
        ) : null}
      </div>
    </div>
  )
}

export default AttractionPicker
