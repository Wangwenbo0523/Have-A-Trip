import React from "react"

import type { Attraction } from "../types"
import AttractionCard from "./AttractionCard"

interface AttractionListProps {
  attractions: Attraction[]
}

const AttractionList = ({ attractions }: AttractionListProps) => (
  <ul className="attractionGrid">
    {attractions.map((attraction) => (
      <li key={attraction.slug}>
        <AttractionCard attraction={attraction} />
      </li>
    ))}
  </ul>
)

export default AttractionList
