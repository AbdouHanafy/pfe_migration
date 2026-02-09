import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Button from './Button'

const NavBar = () => {
  const { token, setToken } = useAuth()
  const navigate = useNavigate()

  const onLogout = () => {
    setToken('')
    navigate('/login')
  }

  return (
    <nav className="nav">
      <Link className="nav-brand" to="/">VM Control</Link>
      <div className="nav-links">
        <NavLink to="/" end>Home</NavLink>
        <NavLink to="/about">About</NavLink>
        {!token ? <NavLink to="/login">Login</NavLink> : null}
        {!token ? <NavLink to="/register">Register</NavLink> : null}
      </div>
      {token ? <Button variant="ghost" onClick={onLogout}>Logout</Button> : null}
    </nav>
  )
}

export default NavBar
