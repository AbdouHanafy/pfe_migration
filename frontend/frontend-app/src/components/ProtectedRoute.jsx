import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import MigrationActivityPanel from './MigrationActivityPanel'

const ProtectedRoute = ({ children }) => {
  const { token } = useAuth()
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return (
    <>
      {children}
      <MigrationActivityPanel />
    </>
  )
}

export default ProtectedRoute
