import { AboutPage, HomePage, LoginPage, NotFoundPage, RegisterPage } from '../pages'
import ProtectedRoute from '../components/ProtectedRoute'

export const routes = [
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <HomePage />
      </ProtectedRoute>
    )
  },
  {
    path: '/about',
    element: <AboutPage />
  },
  {
    path: '/login',
    element: <LoginPage />
  },
  {
    path: '/register',
    element: <RegisterPage />
  },
  {
    path: '*',
    element: <NotFoundPage />
  }
]
