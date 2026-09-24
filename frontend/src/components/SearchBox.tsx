import React from "react"

import "../styles/search.css"

interface SearchBoxProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

const SearchBox = ({ value, onChange, placeholder = "搜索…" }: SearchBoxProps) => (
  <form className="searchBox" role="search" onSubmit={(event) => event.preventDefault()}>
    <label className="searchBox__label" htmlFor="attraction-search">
      搜索
    </label>
    <input
      id="attraction-search"
      className="search"
      type="search"
      placeholder={placeholder}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  </form>
)

export default SearchBox
