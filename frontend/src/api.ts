const BASE = '/api'

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  return res.json()
}

export const api = {
  health: () => fetchJSON<{status: string}>('/health'),
  library: (limit = 50, offset = 0) =>
    fetchJSON<{items: any[]}>(`/library?limit=${limit}&offset=${offset}`),
  libraryItem: (id: number) => fetchJSON<any>(`/library/${id}`),
  profiles: () => fetchJSON<any[]>('/profiles'),
  createProfile: (data: any) =>
    fetchJSON<any>('/profiles', { method: 'POST', body: JSON.stringify(data) }),
  updateProfile: (id: number, data: any) =>
    fetchJSON<any>(`/profiles/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteProfile: (id: number) =>
    fetchJSON<any>(`/profiles/${id}`, { method: 'DELETE' }),
  categories: () => fetchJSON<any[]>('/categories'),
  sync: () => fetchJSON<any>('/sync', { method: 'POST' }),
  syncStatus: () => fetchJSON<any>('/sync/status'),
  syncSingle: (id: number) => fetchJSON<any>(`/sync/${id}`, { method: 'POST' }),
  generate: (profileId = 1) =>
    fetchJSON<any>(`/generate?profile_id=${profileId}`, { method: 'POST' }),
  preview: (profileId: number) => fetchJSON<any>(`/generate/preview/${profileId}`),
  plexConnect: (url: string, token: string) =>
    fetchJSON<any>(`/plex/connect?url=${encodeURIComponent(url)}&token=${encodeURIComponent(token)}`, { method: 'POST' }),
  plexScan: () => fetchJSON<any>('/plex/scan', { method: 'POST' }),
}
