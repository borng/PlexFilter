type Page = 'library' | 'profiles' | 'settings'

export default function Nav({ page, setPage }: { page: Page; setPage: (p: Page) => void }) {
  const tabs: { key: Page; label: string }[] = [
    { key: 'library', label: 'Library' },
    { key: 'profiles', label: 'Profiles' },
    { key: 'settings', label: 'Settings' },
  ]
  return (
    <nav className="flex gap-1 bg-gray-800 p-2 rounded-lg mb-6">
      {tabs.map(t => (
        <button
          key={t.key}
          onClick={() => setPage(t.key)}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            page === t.key ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          {t.label}
        </button>
      ))}
    </nav>
  )
}
