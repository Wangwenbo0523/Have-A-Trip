import React from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import Region from "../components/Region"
import RegionList from "../components/RegionList"
import Header from "../components/Header"
import Footer from "../components/Footer"
import Detail from "../components/CountryDetails/Detail"
import Credits from "../components/Credits"

interface AppRouterProps {
  onSearchChange: (event: React.ChangeEvent<HTMLInputElement>) => void
  regionList: string[]
  countryList: string[]
  flagList: string[]
  countries: any[]
  searchField: string
}

function AppRouter({
  onSearchChange,
  regionList,
  countries,
  searchField,
}: AppRouterProps) {
  const regions = [
    "/africa",
    "/americas",
    "/antarctic",
    "/antarctic-ocean",
    "/asia",
    "/europe",
    "/oceania",
    "/polar",
  ]

  const routes = regions.map((region, index) => {
    const regionName = region.replace("/", "")
      .replace(/-/g, " ")
      .replace(/\b\w/g, l => l.toUpperCase())

    return (
      <Route
        key={index}
        path={region}
        element={
          <Region
            onSearchChange={onSearchChange}
            search={searchField}
            region={regionName}
            countries={countries}
          />
        }
      />
    )
  })

  return (
    <BrowserRouter>
      <div>
        <Header />
        <Routes>
          <Route
            path="/"
            element={<RegionList countries={countries} regions={regionList} />}
          />
          {routes}
          <Route path="/detail/:id" element={<Detail />} />
          <Route path="/credits" element={<Credits />} />
        </Routes>
        <Footer />
      </div>
    </BrowserRouter>
  )
}

export default AppRouter