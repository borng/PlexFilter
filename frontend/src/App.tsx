import { useState } from 'react'
import Nav from './components/Nav'
import Library from './pages/Library'
import TitleDetail from './pages/TitleDetail'
import Profiles from './pages/Profiles'
import Settings from './pages/Settings'

type Page = 'library' | 'profiles' | 'settings'

export default function App() {
  const [page, setPage] = useState<Page>('library')
  const [selectedItem, setSelectedItem] = useState<number | null>(null)

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-6">
          <h1 className="text-3xl font-bold">PlexFilter</h1>
          <p className="text-gray-400 mt-1">Content filtering for Plex</p>
        </header>

        <Nav page={page} setPage={(p) => { setPage(p); setSelectedItem(null) }} />

        {page === 'library' && selectedItem !== null && (
          <TitleDetail id={selectedItem} onBack={() => setSelectedItem(null)} />
        )}
        {page === 'library' && selectedItem === null && (
          <Library onSelect={(id) => setSelectedItem(id)} />
        )}
        {page === 'profiles' && <Profiles />}
        {page === 'settings' && <Settings />}
      </div>
    </div>
  )
}
