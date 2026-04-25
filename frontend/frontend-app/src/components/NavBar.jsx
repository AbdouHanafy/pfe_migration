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
      <Link className="nav-brand" to="/">Migration Tool</Link>
      <div className="nav-links">
        {token ? <NavLink to="/" end>Dashboard</NavLink> : null}
        {token ? <NavLink to="/migrations/new">New Migration</NavLink> : null}
        {token ? <NavLink to="/migrations/progress">Progress</NavLink> : null}
        {token ? <NavLink to="/migrations/history">History</NavLink> : null}
        {token ? <NavLink to="/vms">VMs</NavLink> : null}
        {token ? <NavLink to="/settings">Settings</NavLink> : null}
        <NavLink to="/about">About</NavLink>
        {!token ? <NavLink to="/login">Login</NavLink> : null}
        {!token ? <NavLink to="/register">Register</NavLink> : null}
      </div>
      {token ? <Button variant="ghost" onClick={onLogout}>Logout</Button> : null}
    </nav>
  )
}

export default NavBar
