import {
  AboutPage,
  DashboardPage,
  LoginPage,
  MigrationHistoryPage,
  MigrationProgressPage,
  NewMigrationPage,
  NotFoundPage,
  RegisterPage,
  SettingsPage,
  VmManagementPage,
} from '../pages'
import ProtectedRoute from '../components/ProtectedRoute'

export const routes = [
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <DashboardPage />
      </ProtectedRoute>
    )
  },
  {
    path: '/migrations/new',
    element: (
      <ProtectedRoute>
        <NewMigrationPage />
      </ProtectedRoute>
    )
  },
  {
    path: '/migrations/progress',
    element: (
      <ProtectedRoute>
        <MigrationProgressPage />
      </ProtectedRoute>
    )
  },
  {
    path: '/migrations/history',
    element: (
      <ProtectedRoute>
        <MigrationHistoryPage />
      </ProtectedRoute>
    )
  },
  {
    path: '/vms',
    element: (
      <ProtectedRoute>
        <VmManagementPage />
      </ProtectedRoute>
    )
  },
  {
    path: '/settings',
    element: (
      <ProtectedRoute>
        <SettingsPage />
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
