// frontend/src/App.tsx
import { Navigate, Outlet, Route, Routes } from 'react-router'
import { AdminBar, TopBar } from './components/Navigation'
import { RequireAdmin, RequireAuth } from './components/Guards'
import { Accueil } from './pages/Accueil'
import { Connexion, Inscription } from './pages/AuthPages'
import { Compte, Documentation, Introuvable } from './pages/ClientPages'
import { AdminCles } from './pages/admin/Cles'
import { AdminComptes } from './pages/admin/Comptes'
import { AdminDocuments } from './pages/admin/Documents'
import { AdminJournal } from './pages/admin/Journal'

function ClientLayout() {
  return (
    <RequireAuth>
      <TopBar links={[{ to: '/', label: 'nav.accueil', end: true }, { to: '/documentation', label: 'nav.documentation' }]} />
      <Outlet />
    </RequireAuth>
  )
}

function AdminLayout() {
  return (
    <RequireAuth>
      <RequireAdmin>
        <AdminBar links={[
          { to: '/administration/documents', label: 'admin.documents' },
          { to: '/administration/comptes', label: 'admin.comptes' },
          { to: '/administration/cles', label: 'admin.cles' },
          { to: '/administration/journal', label: 'admin.journal' },
        ]} />
        <Outlet />
      </RequireAdmin>
    </RequireAuth>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/connexion" element={<Connexion />} />
      <Route path="/inscription" element={<Inscription />} />
      <Route element={<ClientLayout />}>
        <Route index element={<Accueil />} />
        <Route path="documentation" element={<Documentation />} />
        <Route path="compte" element={<Compte />} />
      </Route>
      <Route path="administration" element={<AdminLayout />}>
        <Route index element={<Navigate to="documents" replace />} />
        <Route path="documents" element={<AdminDocuments />} />
        <Route path="comptes" element={<AdminComptes />} />
        <Route path="cles" element={<AdminCles />} />
        <Route path="journal" element={<AdminJournal />} />
      </Route>
      <Route element={<ClientLayout />}>
        <Route path="*" element={<Introuvable />} />
      </Route>
    </Routes>
  )
}
