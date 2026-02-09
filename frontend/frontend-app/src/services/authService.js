const apiBase = (baseUrl) => (baseUrl || '').replace(/\/$/, '')

const extractErrorMessage = async (res) => {
  try {
    const data = await res.json()
    if (data && data.detail) {
      if (typeof data.detail === 'string') return data.detail
      if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg
    }
  } catch {
    // ignore JSON parse errors
  }
  const text = await res.text()
  return text || 'Request failed'
}

export const login = async ({ baseUrl, matricule, password }) => {
  const res = await fetch(`${apiBase(baseUrl)}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ matricule, password })
  })
  if (!res.ok) {
    throw new Error(await extractErrorMessage(res))
  }
  return res.json()
}

export const register = async ({ baseUrl, matricule, password }) => {
  const res = await fetch(`${apiBase(baseUrl)}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ matricule, password })
  })
  if (!res.ok) {
    throw new Error(await extractErrorMessage(res))
  }
  return res.json()
}
