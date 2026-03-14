import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

interface LibraryItem {
  id: number
  title: string
  year: number | null
  thumb_url: string | null
  matched: number
  source?: string | null
}

export default function Library({ onSelect }: { onSelect: (id: number) => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['library'],
    queryFn: () => api.library(200, 0),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-gray-400 text-lg">Loading library...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-red-400 text-lg">
          Failed to load library. Is the backend running?
        </div>
      </div>
    )
  }

  const items: LibraryItem[] = Array.isArray(data) ? data : []

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-400">
        <p className="text-lg mb-2">No items in library</p>
        <p className="text-sm">Connect to Plex and sync your library in Settings.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-white">Library</h2>
        <span className="text-sm text-gray-400">{items.length} items</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
        {items.map(item => (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            className="group relative bg-gray-800 rounded-lg overflow-hidden hover:ring-2 hover:ring-blue-500 transition-all text-left"
          >
            <div className="aspect-[2/3] bg-gray-700 flex items-center justify-center">
              {item.thumb_url ? (
                <img
                  src={item.thumb_url}
                  alt={item.title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-gray-500 text-4xl">🎬</span>
              )}
            </div>
            <div className="p-2">
              <p className="text-sm text-white truncate">{item.title}</p>
              <div className="flex items-center justify-between mt-1">
                {item.year && (
                  <span className="text-xs text-gray-400">{item.year}</span>
                )}
                <span
                  className={`inline-block w-2.5 h-2.5 rounded-full ml-auto ${
                    item.matched ? 'bg-green-500' : 'bg-yellow-500'
                  }`}
                  title={
                    item.matched
                      ? `Matched (${item.source || 'vidangel'})`
                      : 'Unmatched'
                  }
                />
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
