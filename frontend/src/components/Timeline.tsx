/**
 * Timeline — horizontal bar showing where filtered content appears in a movie.
 *
 * Color legend:
 *   Yellow  = Language
 *   Red     = Violence
 *   Pink    = Nudity
 *   Purple  = Sex
 */

interface Tag {
  start_sec: number
  end_sec: number
  category_group: string
  type: string
  category_name?: string
}

interface TimelineProps {
  tags: Tag[]
  runtime: number // total seconds
}

const GROUP_COLORS: Record<string, string> = {
  Language: 'bg-yellow-500',
  Violence: 'bg-red-500',
  Nudity:   'bg-pink-500',
  Sex:      'bg-purple-500',
}

function formatTime(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = Math.floor(totalSeconds % 60)
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function Timeline({ tags, runtime }: TimelineProps) {
  if (runtime <= 0) return null

  return (
    <div className="w-full">
      {/* Color legend */}
      <div className="flex gap-4 mb-2 text-xs text-gray-400">
        {Object.entries(GROUP_COLORS).map(([group, color]) => (
          <span key={group} className="flex items-center gap-1">
            <span className={`inline-block w-3 h-3 rounded-sm ${color}`} />
            {group}
          </span>
        ))}
      </div>

      {/* Bar */}
      <div className="relative h-6 bg-gray-700 rounded overflow-hidden">
        {tags.map((tag, i) => {
          const leftPct = (tag.start_sec / runtime) * 100
          const rawWidth = ((tag.end_sec - tag.start_sec) / runtime) * 100
          const widthPct = Math.max(rawWidth, 0.3)
          const color = GROUP_COLORS[tag.category_group] ?? 'bg-gray-500'

          const tooltip = [
            tag.category_group,
            tag.category_name ? `(${tag.category_name})` : '',
            `${formatTime(tag.start_sec)} - ${formatTime(tag.end_sec)}`,
          ]
            .filter(Boolean)
            .join(' ')

          return (
            <div
              key={i}
              className={`absolute top-0 h-full ${color} opacity-80 hover:opacity-100 transition-opacity`}
              style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
              title={tooltip}
            />
          )
        })}
      </div>

      {/* Time labels */}
      <div className="flex justify-between mt-1 text-xs text-gray-500">
        <span>0:00</span>
        <span>{formatTime(runtime)}</span>
      </div>
    </div>
  )
}
