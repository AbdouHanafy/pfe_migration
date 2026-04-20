import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Input from '../components/Input'
import { useAuth } from '../hooks/useAuth'
import { login } from '../services/authService'
import { validateCredentials } from '../utils/validators'

const Login = () => {
  const [matricule, setMatricule] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { setToken } = useAuth()

  const apiBase = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8000'

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    const errors = validateCredentials({ matricule, password })
    if (errors.length) {
      setError(errors[0])
      return
    }

    try {
      const data = await login({
        baseUrl: apiBase,
        matricule: matricule.trim(),
        password: password.trim()
      })
      setToken(data.access_token)
      navigate('/')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="page login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="logo">MX</div>
          <div>
            <h2>OpenShift Migration Nexus</h2>
            <p>VM migration intelligence for OpenShift Virtualization</p>
          </div>
        </div>
        <form className="login-form" onSubmit={onSubmit}>
          <Input
            placeholder="Matricule"
            value={matricule}
            onChange={(e) => setMatricule(e.target.value)}
          />
          <Input
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button type="submit">Login</Button>
        </form>
        {error ? <p className="error">{error}</p> : null}
        <p className="login-link">
          No account? <Link to="/register">Create one</Link>
        </p>
      </div>
    </div>
  )
}

export default Login
