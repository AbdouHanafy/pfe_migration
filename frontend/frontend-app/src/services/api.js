export const createApi = (baseUrl, token) => {
  const apiBase = (baseUrl || '').replace(/\/$/, '')

  const fetchJson = async (path, options = {}) => {
    const headers = { ...(options.headers || {}) }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
    const res = await fetch(`${apiBase}${path}`, { ...options, headers })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`${res.status} ${res.statusText}: ${text}`)
    }
    return res.json()
  }

  return { fetchJson }
}
