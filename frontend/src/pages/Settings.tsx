import { useState } from 'react'
import { api } from '../api'

type Status = 'idle' | 'connecting' | 'scanning' | 'syncing' | 'done' | 'error'

export default function Settings() {
  const [plexUrl, setPlexUrl] = useState('http://localhost:32400')
  const [plexToken, setPlexToken] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [message, setMessage] = useState('')

  async function handleConnect() {
    if (!plexUrl || !plexToken) {
      setStatus('error')
      setMessage('Both URL and token are required.')
      return
    }

    try {
      setStatus('connecting')
      setMessage('Connecting to Plex...')
      await api.plexConnect(plexUrl, plexToken)

      setStatus('scanning')
      setMessage('Scanning Plex library...')
      await api.plexScan()

      setStatus('syncing')
      setMessage('Syncing filters and running local fallback where needed...')
      await api.sync()
      await waitForSyncCompletion()

      setStatus('done')
      setMessage('Connected and synced successfully.')
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof Error ? err.message : 'Connection failed.')
    }
  }

  const isWorking = status === 'connecting' || status === 'scanning' || status === 'syncing'

  async function waitForSyncCompletion() {
    // Poll every second while backend background task is running.
    // This keeps UX responsive during local frame analysis.
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const syncStatus = await api.syncStatus()
      if (!syncStatus.running) {
        const localCount = Number(syncStatus.local_fallback_count || 0)
        const summary = `${syncStatus.current || 0}/${syncStatus.total || 0} titles processed`
        if (localCount > 0) {
          setMessage(`${summary}. Local detection used for ${localCount} title(s).`)
        } else {
          setMessage(`${summary}.`)
        }
        return
      }

      const cur = Number(syncStatus.current || 0)
      const total = Number(syncStatus.total || 0)
      const extra = syncStatus.last_action ? ` (${syncStatus.last_action})` : ''
      setMessage(`Syncing ${cur}/${total}${extra}...`)
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
  }

  return (
    <div className="max-w-lg">
      <h2 className="text-xl font-semibold text-white mb-4">Settings</h2>

      <div className="bg-gray-800 rounded-lg p-6 space-y-4">
        <h3 className="text-lg font-medium text-white">Plex Connection</h3>

        <div>
          <label className="block text-sm text-gray-400 mb-1">Plex URL</label>
          <input
            type="text"
            value={plexUrl}
            onChange={e => setPlexUrl(e.target.value)}
            placeholder="http://localhost:32400"
            disabled={isWorking}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          />
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">Plex Token</label>
          <input
            type="password"
            value={plexToken}
            onChange={e => setPlexToken(e.target.value)}
            placeholder="Your Plex authentication token"
            disabled={isWorking}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          />
        </div>

        <button
          onClick={handleConnect}
          disabled={isWorking}
          className="w-full px-4 py-2 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isWorking ? 'Working...' : 'Connect & Sync'}
        </button>

        {message && (
          <div
            className={`text-sm px-3 py-2 rounded-md ${
              status === 'error'
                ? 'bg-red-900/50 text-red-300'
                : status === 'done'
                ? 'bg-green-900/50 text-green-300'
                : 'bg-blue-900/50 text-blue-300'
            }`}
          >
            {message}
          </div>
        )}
      </div>
    </div>
  )
}
