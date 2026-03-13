import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, Navigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  HeartPulse, LayoutDashboard, LogOut, Sun, Moon, FolderOpen,
  MessageSquare, Users, Search, Calendar, Package,
  ClipboardList, Syringe, Shield, History
} from 'lucide-react';

// --- PAGES ---
import Login from './pages/Login';
import Doctor from './pages/Doctor';
import Patient from './pages/Patient';
import Pharmacist from './pages/Pharmacist';
import Bloodtest from './pages/Bloodtest';
import Insurance from './pages/Insurance';
import Admin from './pages/Admin';

// --- ANIMATION VARIANTS ---
const pageVariants = { initial: { opacity: 0, x: -10 }, in: { opacity: 1, x: 0 }, out: { opacity: 0, x: 10 } };
const transition = { type: "tween", ease: "circOut", duration: 0.3 };

// --- 1. SIDEBAR COMPONENT ---
const SidebarItem = ({ icon, label, active, onClick }) => (
  <div onClick={onClick} style={{
    display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px',
    margin: '6px 0', borderRadius: '12px', cursor: 'pointer', transition: 'all 0.2s',
    backgroundColor: active ? 'var(--primary-light)' : 'transparent',
    color: active ? 'var(--primary)' : 'var(--text-muted)', fontWeight: active ? '600' : '500'
  }}>
    {icon} <span>{label}</span>
  </div>
);

// --- 2. MAIN LAYOUT WITH DYNAMIC NAVIGATION ---
const Layout = ({ user, children, onLogout, isDark, toggleTheme }) => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg-body)' }}>
      {/* SIDEBAR */}
      <div style={{ width: '260px', background: 'var(--bg-surface)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', padding: '24px 16px', zIndex: 20, flexShrink: 0, boxShadow: 'var(--shadow-sm)' }}>

        {/* BRANDING */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '11px', marginBottom: '36px', padding: '4px 8px' }}>
          <div style={{ background: 'linear-gradient(135deg, var(--primary) 0%, #3b82f6 100%)', padding: '10px', borderRadius: '14px', color: 'white', boxShadow: 'var(--shadow-primary)', flexShrink: 0 }}>
            <HeartPulse size={22} strokeWidth={2.5} />
          </div>
          <span style={{ fontSize: '20px', fontWeight: '900', color: 'var(--text-main)', letterSpacing: '-0.5px' }}>HealthScore</span>
        </div>

        {/* MENU LABEL */}
        <p style={{ fontSize: '10px', fontWeight: '800', color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: '8px', paddingLeft: '12px', letterSpacing: '1px' }}>Navigation</p>

        {/* DYNAMIC MENU ITEMS */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '2px' }}>

          {/* DOCTOR MENU */}
          {user.role === 'Doctor' && (
            <>
              <SidebarItem icon={<Search size={18} />} label="Patient Lookup" active={location.pathname === '/doctor'} onClick={() => navigate('/doctor')} />
              <SidebarItem icon={<Calendar size={18} />} label="Appointments" active={location.pathname === '/doctor/appointments'} onClick={() => navigate('/doctor/appointments')} />
              <SidebarItem icon={<History size={18} />} label="Patient History" active={location.pathname === '/doctor/patients'} onClick={() => navigate('/doctor/patients')} />
            </>
          )}

          {/* PATIENT MENU */}
          {user.role === 'Patient' && (
            <>
              <SidebarItem icon={<LayoutDashboard size={18} />} label="Dashboard" active={location.pathname === '/patient'} onClick={() => navigate('/patient')} />
              <SidebarItem icon={<Users size={18} />} label="Medical Team" active={location.pathname === '/patient/team'} onClick={() => navigate('/patient/team')} />
              <SidebarItem icon={<FolderOpen size={18} />} label="Medical Vault" active={location.pathname === '/patient/vault'} onClick={() => navigate('/patient/vault')} />
              <SidebarItem icon={<MessageSquare size={18} />} label="AI Assistant" active={location.pathname === '/patient/chat'} onClick={() => navigate('/patient/chat')} />
            </>
          )}

          {/* PHARMACIST MENU */}
          {user.role === 'Pharmacist' && (
            <>
              <SidebarItem icon={<Search size={18} />} label="Prescription Lookup" active={location.pathname === '/pharmacist'} onClick={() => navigate('/pharmacist')} />
              <SidebarItem icon={<Package size={18} />} label="Inventory Manager" active={location.pathname === '/pharmacist/inventory'} onClick={() => navigate('/pharmacist/inventory')} />
              <SidebarItem icon={<ClipboardList size={18} />} label="Dispense Logs" active={location.pathname === '/pharmacist/logs'} onClick={() => navigate('/pharmacist/logs')} />
            </>
          )}

          {/* BLOODTEST LAB MENU */}
          {user.role === 'Bloodtest' && (
            <>
              <SidebarItem icon={<Syringe size={18} />} label="Patient Orders" active={location.pathname === '/bloodtest'} onClick={() => navigate('/bloodtest')} />
              <SidebarItem icon={<History size={18} />} label="Patient History" active={location.pathname === '/bloodtest/history'} onClick={() => navigate('/bloodtest/history')} />
            </>
          )}

          {/* INSURANCE MENU */}
          {user.role === 'Insurance' && (
            <SidebarItem icon={<Shield size={18} />} label="Claims Portal" active={location.pathname === '/insurance'} onClick={() => navigate('/insurance')} />
          )}
        </div>

        {/* ── THEME PILL TOGGLE ── */}
        <div style={{ marginBottom: '16px' }}>
          <div
            onClick={toggleTheme}
            style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-body)', border: '1px solid var(--border)', borderRadius: '99px', padding: '4px', cursor: 'pointer', gap: '2px', position: 'relative', transition: 'all 0.3s' }}>
            {/* Sun side */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '8px', borderRadius: '99px', background: !isDark ? 'var(--bg-surface)' : 'transparent', boxShadow: !isDark ? 'var(--shadow-xs)' : 'none', transition: 'all 0.3s', gap: '6px', color: !isDark ? 'var(--warning)' : 'var(--text-faint)', fontWeight: '700', fontSize: '12px' }}>
              <Sun size={15} /> {!isDark && 'Light'}
            </div>
            {/* Moon side */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '8px', borderRadius: '99px', background: isDark ? 'var(--bg-surface)' : 'transparent', boxShadow: isDark ? 'var(--shadow-xs)' : 'none', transition: 'all 0.3s', gap: '6px', color: isDark ? 'var(--primary)' : 'var(--text-faint)', fontWeight: '700', fontSize: '12px' }}>
              <Moon size={15} /> {isDark && 'Dark'}
            </div>
          </div>
        </div>

        {/* USER PROFILE & LOGOUT */}
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', borderRadius: '14px', background: 'var(--bg-body)', border: '1px solid var(--border)' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'var(--primary-light)', border: '1px solid var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--primary)', fontWeight: '800', fontSize: '15px', flexShrink: 0 }}>
              {user.name.charAt(0)}
            </div>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.name}</div>
              <div style={{ fontSize: '11px', color: 'var(--primary)', fontWeight: '600' }}>{user.role}</div>
            </div>
            <button onClick={onLogout} title="Logout" style={{ background: 'var(--danger-light)', border: '1px solid var(--danger)', borderRadius: '8px', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--danger)', flexShrink: 0 }}>
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </div>

      {/* MAIN CONTENT WRAPPER */}
      <div style={{ flex: 1, overflowY: 'auto', position: 'relative' }}>
        {children}
      </div>
    </div>
  );
};

// --- 3. PROTECTED ROUTE WRAPPER ---
const ProtectedRoute = ({ user, role, children, onLogout, isDark, toggleTheme }) => {
  if (!user) return <Navigate to="/" replace />;
  if (user.role !== role) return <Navigate to={`/${user.role.toLowerCase()}`} replace />;

  return (
    <Layout user={user} onLogout={onLogout} isDark={isDark} toggleTheme={toggleTheme}>
      {children}
    </Layout>
  );
};

// Helper for Login Page
const LoginWrapper = ({ auth, setAuth }) => {
  if (auth) return <Navigate to={`/${auth.role.toLowerCase()}`} replace />;
  return <Login setAuth={setAuth} />;
};

// --- 4. MAIN ROUTER ---
export default function App() {
  const [user, setUser] = useState(JSON.parse(localStorage.getItem('user')));
  const [isDark, setIsDark] = useState(() => localStorage.getItem('theme') === 'dark');

  useEffect(() => {
    if (isDark) { document.documentElement.classList.add('dark'); localStorage.setItem('theme', 'dark'); }
    else { document.documentElement.classList.remove('dark'); localStorage.setItem('theme', 'light'); }
  }, [isDark]);

  const saveAuth = (u) => { setUser(u); localStorage.setItem('user', JSON.stringify(u)); };
  const logout = () => { setUser(null); localStorage.removeItem('user'); window.location.href = '/'; };
  const toggleTheme = () => setIsDark(!isDark);

  if (!user) {
    return (
      <Router>
        <Routes>
          <Route path="/" element={<Login setAuth={saveAuth} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    );
  }

  return (
    <Router>
      <AnimatePresence mode="wait">
        <Routes>
          {/* Admin Route - Independent of Layout */}
          <Route path="/admin/*" element={<Admin user={user} />} />
          
          {/* All other routes wrapped in Layout */}
          <Route path="*" element={
            <Layout user={user} onLogout={logout} isDark={isDark} toggleTheme={toggleTheme}>
              <Routes>
                <Route path="/doctor/*" element={<Doctor user={user} />} />
                <Route path="/patient/*" element={<Patient user={user} />} />
                <Route path="/pharmacist/*" element={<Pharmacist user={user} />} />
                <Route path="/bloodtest/*" element={<Bloodtest user={user} />} />
                <Route path="/insurance/*" element={<Insurance user={user} />} />
                <Route path="/" element={<Navigate to={`/${user.role.toLowerCase()}`} replace />} />
                <Route path="*" element={<Navigate to={`/${user.role.toLowerCase()}`} replace />} />
              </Routes>
            </Layout>
          } />
        </Routes>
      </AnimatePresence>
    </Router>
  );
}