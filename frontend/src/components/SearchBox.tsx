import React from "react"

import { useI18n } from "../i18n"
import "../styles/search.css"

interface SearchBoxProps {
  value: string
  onChange: (value: string) => void
  /** 不传就用通用文案「搜索…」, 列表页会传更具体的「搜索景点名称或简介…」 */
  placeholder?: string
}

const SearchBox = ({ value, onChange, placeholder }: SearchBoxProps) => {
  const { t } = useI18n()

  return (
    <form className="searchBox" role="search" onSubmit={(event) => event.preventDefault()}>
      <label className="searchBox__label" htmlFor="attraction-search">
        {t("search.label")}
      </label>
      <input
        id="attraction-search"
        className="search"
        type="search"
        placeholder={placeholder ?? t("search.placeholder")}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </form>
  )
}

export default SearchBox
