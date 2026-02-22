import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import Timeline from '../components/Timeline'

// ── Types matching backend schema ──────────────────────────────────────

interface Tag {
  id: number
  vidangel_id: number
  tag_set_id: number
  category_id: number
  category_name: string
  category_group: string
  description: string | null
  type: string        // "audio" | "visual" | "audiovisual"
  start_sec: number
  end_sec: number
}

interface LibraryDetail {
  id: number
  plex_key: string
  title: string
  year: number | null
  tmdb_id: string | null
  imdb_id: string | null
  media_type: string
  thumb_url: string | null
  last_scanned: string | null
  // match fields (may be null when unmatched)
  vidangel_work_id: number | null
  tag_set_id: number | null
  tag_count: number | null
  match_method?: string | null
  last_synced: string | null
  matched: number   // 0 or 1
  tags: Tag[]
}

// ── Helpers ─────────────────────────────────────────────────────────────

function formatTimestamp(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

const TYPE_BADGE_COLORS: Record<string, string> = {
  audio:       'bg-blue-600',
  visual:      'bg-green-600',
  audiovisual: 'bg-indigo-600',
}

// ── Component ───────────────────────────────────────────────────────────

export default function TitleDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const { data: item, isLoading, error } = useQuery<LibraryDetail>({
    queryKey: ['library', id],
    queryFn: () => api.libraryItem(id),
  })

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-gray-400 text-lg">Loading...</div>
      </div>
    )
  }

  // Error state
  if (error || !item) {
    return (
      <div className="space-y-4">
        <button
          onClick={onBack}
          className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
        >
          &larr; Back to library
        </button>
        <div className="text-red-400">Failed to load title details.</div>
      </div>
    )
  }

  // Estimate runtime from last tag end_sec (backend doesn't store runtime directly).
  // Fall back to 7200 (2h) if no tags so the timeline still renders a bar.
  const lastTagEnd = item.tags.length > 0
    ? Math.max(...item.tags.map(t => t.end_sec))
    : 0
  const estimatedRuntime = lastTagEnd > 0 ? Math.ceil(lastTagEnd) : 0

  // Group tags by category_group
  const grouped: Record<string, Tag[]> = {}
  for (const tag of item.tags) {
    const group = tag.category_group
    if (!grouped[group]) grouped[group] = []
    grouped[group].push(tag)
  }

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={onBack}
        className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
      >
        &larr; Back to library
      </button>

      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">
          {item.title}
          {item.year && <span className="text-gray-400 font-normal ml-2">({item.year})</span>}
        </h2>
        <span className="inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-300 uppercase">
          {item.media_type}
        </span>
      </div>

      {/* Match info */}
      {item.matched ? (
        <div className="text-sm text-gray-400 space-y-1">
          <p>
            <span className="text-green-400 font-medium">Matched</span>
            {item.match_method && <> via <span className="text-gray-300">{item.match_method}</span></>}
          </p>
          <p>{item.tag_count ?? item.tags.length} tags found</p>
        </div>
      ) : (
        <div className="bg-yellow-900/40 border border-yellow-700 text-yellow-300 rounded-lg px-4 py-3 text-sm">
          Not matched with VidAngel — no filter data available for this title.
        </div>
      )}

      {/* Timeline */}
      {item.tags.length > 0 && estimatedRuntime > 0 && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">Content Timeline</h3>
          <Timeline tags={item.tags} runtime={estimatedRuntime} />
        </div>
      )}

      {/* Tags grouped by category_group */}
      {Object.keys(grouped).length > 0 && (
        <div className="space-y-6">
          {Object.entries(grouped).map(([group, tags]) => (
            <div key={group} className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-gray-300 mb-3">
                {group}
                <span className="ml-2 text-xs text-gray-500 font-normal">({tags.length})</span>
              </h3>
              <ul className="space-y-2">
                {tags.map(tag => (
                  <li
                    key={tag.id}
                    className="flex items-start gap-3 text-sm bg-gray-750 rounded px-3 py-2"
                    style={{ backgroundColor: 'rgba(255,255,255,0.03)' }}
                  >
                    {/* Timestamp */}
                    <span className="text-gray-500 tabular-nums whitespace-nowrap min-w-[5rem]">
                      {formatTimestamp(tag.start_sec)} &ndash; {formatTimestamp(tag.end_sec)}
                    </span>

                    {/* Category + description */}
                    <span className="flex-1 text-gray-300">
                      <span className="font-medium text-gray-200">{tag.category_name}</span>
                      {tag.description && (
                        <span className="text-gray-400 ml-1">— {tag.description}</span>
                      )}
                    </span>

                    {/* Type badge */}
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium text-white whitespace-nowrap ${
                        TYPE_BADGE_COLORS[tag.type] ?? 'bg-gray-600'
                      }`}
                    >
                      {tag.type}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
