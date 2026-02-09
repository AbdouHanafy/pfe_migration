import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Input from '../components/Input'
import { register } from '../services/authService'
import { validateCredentials } from '../utils/validators'

const Register = () => {
  const [matricule, setMatricule] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const navigate = useNavigate()

  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    const errors = validateCredentials({ matricule, password })
    if (errors.length) {
      setError(errors[0])
      return
    }

    try {
      await register({
        baseUrl: apiBase,
        matricule: matricule.trim(),
        password: password.trim()
      })
      setSuccess('Account created. You can now log in.')
      setTimeout(() => navigate('/login'), 600)
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
            <h2>Create Account</h2>
            <p>Register with matricule and password.</p>
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
          <Button type="submit">Register</Button>
        </form>
        {error ? <p className="error">{error}</p> : null}
        {success ? <p className="success">{success}</p> : null}
      </div>
    </div>
  )
}

export default Register
