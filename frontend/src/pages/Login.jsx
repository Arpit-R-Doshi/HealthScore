import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  User, Lock, ArrowRight, Activity, Dna, Heart,
  Stethoscope, HeartPulse, Sun, Moon, Eye, EyeOff,
  UserPlus, LogIn, Shield, Syringe
} from 'lucide-react';
import BlockchainBackground from '../components/BlockchainBackground';

// ── Animated digital human SVG ──────────────────────────────
const DigitalHuman = () => (
  <svg width="280" height="460" viewBox="0 0 200 400" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ zIndex: 10, opacity: 0.9 }}>
    <defs>
      <linearGradient id="bodyGrad" x1="100" y1="0" x2="100" y2="400" gradientUnits="userSpaceOnUse">
        <stop stopColor="#a5b4fc" stopOpacity="0.15" />
        <stop offset="1" stopColor="#4f46e5" stopOpacity="0.7" />
      </linearGradient>
      <filter id="glow">
        <feGaussianBlur stdDeviation="3" result="coloredBlur" />
        <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
    </defs>
    <motion.path
      initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ duration: 2, ease: "easeInOut" }}
      d="M100 40 C 120 40, 130 60, 130 75 C 130 90, 150 100, 160 110 L 165 200 L 155 200 L 150 130 L 130 130 L 130 220 L 140 380 L 110 380 L 105 250 L 95 250 L 90 380 L 60 380 L 70 220 L 70 130 L 50 130 L 45 200 L 35 200 L 40 110 C 50 100, 70 90, 70 75 C 70 60, 80 40, 100 40"
      stroke="url(#bodyGrad)" strokeWidth="2" fill="url(#bodyGrad)" filter="url(#glow)"
    />
    <motion.line x1="0" y1="0" x2="200" y2="0" stroke="#818cf8" strokeWidth="1.5" filter="url(#glow)"
      animate={{ y: [40, 380, 40], opacity: [0, 1, 0] }} transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
    />
    {[{ cx: 100, cy: 55 }, { cx: 100, cy: 100 }, { cx: 130, cy: 110 }, { cx: 70, cy: 110 }, { cx: 100, cy: 160 }, { cx: 85, cy: 220 }, { cx: 115, cy: 220 }].map((pt, i) => (
      <motion.circle key={i} cx={pt.cx} cy={pt.cy} r="3" fill="#fff"
        animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 2, delay: i * 0.2, repeat: Infinity }} />
    ))}
  </svg>
);

const TABS = [
  { key: 'Patient', icon: User, color: '#4f46e5' },
  { key: 'Doctor', icon: Stethoscope, color: '#0ea5e9' },
  { key: 'Enterprise', icon: Shield, color: '#10b981' },
];

export default function Login({ setAuth }) {
  const [activeTab, setActiveTab] = useState('Patient');
  const [isLogin, setIsLogin] = useState(true);
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ name: '', username: '', password: '', age: '', height: '', weight: '', diseaseInput: '' });
  const [isDark, setIsDark] = useState(() => localStorage.getItem('theme') === 'dark');
  const navigate = useNavigate();

  useEffect(() => {
    if (isDark) { document.documentElement.classList.add('dark'); localStorage.setItem('theme', 'dark'); }
    else { document.documentElement.classList.remove('dark'); localStorage.setItem('theme', 'light'); }
  }, [isDark]);

  const handleAuth = async () => {
    setError(''); setLoading(true);
    try {
      const endpoint = isLogin ? '/api/login' : '/api/register';
      const payload = isLogin ? { username: form.username, password: form.password, role: activeTab } : { ...form };
      const res = await axios.post(`http://localhost:5001${endpoint}`, payload);
      if (isLogin) {
        setAuth(res.data.user);
        navigate(`/${res.data.user.role.toLowerCase()}`, { replace: true });
      } else {
        setError(res.data.message);
        setIsLogin(true);
      }
    } catch (err) { setError(err.response?.data?.message || 'Connection error. Please try again.'); }
    setLoading(false);
  };

  const inputF = f => e => { setForm({ ...form, [f]: e.target.value }); setError(''); };

  return (
    <div style={{ height: '100vh', width: '100vw', display: 'flex', overflow: 'hidden', background: 'var(--bg-body)' }}>

      {/* ── LEFT: Hero panel (always dark-ish) ───────────── */}
      <div style={{ flex: '1.15', position: 'relative', background: 'radial-gradient(ellipse at 80% 20%, #312e81 0%, #1e1b4b 60%, #0f0e2a 100%)', overflow: 'hidden', padding: '50px 60px', display: 'flex', flexDirection: 'column' }}>
        <BlockchainBackground />

        {/* Brand */}
        <div style={{ position: 'relative', zIndex: 10, display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '8px', border: '1px solid rgba(255,255,255,0.25)', borderRadius: '10px', background: 'rgba(255,255,255,0.08)' }}>
            <HeartPulse size={18} color="white" />
          </div>
          <span style={{ color: 'white', fontSize: '13px', fontWeight: '700', letterSpacing: '2.5px', opacity: 0.85 }}>HEALTHSCORE</span>
        </div>

        {/* Rotating DNA + Human */}
        <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <motion.div animate={{ rotate: 360 }} transition={{ duration: 120, repeat: Infinity, ease: 'linear' }}
            style={{ position: 'absolute', right: '-180px', top: '-50px', opacity: 0.06 }}>
            <Dna size={700} color="white" />
          </motion.div>
          <div style={{ position: 'relative', zIndex: 10 }}><DigitalHuman /></div>

          {/* Floating stat cards */}
          {[
            { top: '12%', right: '18%', icon: <Activity size={16} color="white" />, bg: '#ef4444', title: 'Vitals', val: 'Stable' },
            { bottom: '28%', left: '10%', icon: <Syringe size={16} color="white" />, bg: '#4f46e5', title: 'AI Score', val: '94/100' },
          ].map((c, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 + i * 0.2 }}
              style={{ position: 'absolute', top: c.top, bottom: c.bottom, right: c.right, left: c.left, background: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(12px)', border: '1px solid rgba(255,255,255,0.18)', padding: '12px 18px', borderRadius: '16px', display: 'flex', alignItems: 'center', gap: '12px', zIndex: 12, boxShadow: '0 10px 30px rgba(0,0,0,0.3)' }}>
              <div style={{ background: c.bg, padding: '8px', borderRadius: '10px', display: 'flex' }}>{c.icon}</div>
              <div>
                <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.55)', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.8px' }}>{c.title}</div>
                <div style={{ fontSize: '14px', color: '#fff', fontWeight: '800' }}>{c.val}</div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Hero text */}
        <div style={{ position: 'relative', zIndex: 10, marginBottom: '20px' }}>
          <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}
            style={{ fontSize: '52px', fontWeight: '900', color: 'white', lineHeight: '1.08', margin: '0 0 16px 0', letterSpacing: '-1.5px' }}>
            Decentralized<br />
            <span style={{ background: 'linear-gradient(90deg, #818cf8, #c7d2fe)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Patient Care.
            </span>
          </motion.h1>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
            style={{ color: '#6b7da0', fontSize: '15px', lineHeight: '1.7', maxWidth: '400px', margin: 0 }}>
            Secure your medical identity on the blockchain. AI-driven risk analysis with full privacy and control.
          </motion.p>
        </div>
      </div>

      {/* ── RIGHT: Form panel ─────────────────────────────── */}
      <div style={{ flex: '1', background: 'var(--bg-surface)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 32px', position: 'relative', overflow: 'hidden' }}>

        {/* Background blobs */}
        <motion.div animate={{ y: [0, 18, 0] }} transition={{ duration: 6, repeat: Infinity }}
          style={{ position: 'absolute', top: '10%', right: '10%', width: '160px', height: '160px', borderRadius: '50%', background: 'radial-gradient(circle, var(--primary-glow) 0%, transparent 70%)', pointerEvents: 'none', zIndex: 0 }} />
        <motion.div animate={{ y: [0, -14, 0] }} transition={{ duration: 8, repeat: Infinity }}
          style={{ position: 'absolute', bottom: '12%', left: '8%', width: '120px', height: '120px', borderRadius: '50%', background: 'radial-gradient(circle, var(--success-light) 0%, transparent 70%)', pointerEvents: 'none', zIndex: 0 }} />

        {/* Dark mode toggle (top-right of panel) */}
        <button onClick={() => setIsDark(d => !d)}
          style={{ position: 'absolute', top: '24px', right: '24px', width: '44px', height: '44px', borderRadius: '50%', background: 'var(--bg-elevated)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', zIndex: 20, boxShadow: 'var(--shadow-xs)' }}>
          <AnimatePresence mode="wait">
            <motion.div key={isDark ? 'sun' : 'moon'} initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.2 }}>
              {isDark ? <Sun size={18} color="var(--warning)" /> : <Moon size={18} color="var(--text-muted)" />}
            </motion.div>
          </AnimatePresence>
        </button>

        {/* Main form container */}
        <div style={{ width: '100%', maxWidth: '400px', position: 'relative', zIndex: 10 }}>

          {/* Logo */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '36px' }}>
            <div style={{ background: 'linear-gradient(135deg, var(--primary) 0%, #3b82f6 100%)', padding: '14px', borderRadius: '20px', color: 'white', boxShadow: 'var(--shadow-primary)', marginBottom: '16px' }}>
              <HeartPulse size={30} strokeWidth={2.5} />
            </div>
            <h1 style={{ fontSize: '32px', fontWeight: '900', color: 'var(--text-main)', margin: '0 0 6px 0', letterSpacing: '-1px' }}>HealthScore</h1>
            <p style={{ color: 'var(--text-muted)', margin: 0, fontSize: '14px', fontWeight: '500' }}>
              {isLogin ? 'Welcome back. Select your portal.' : 'Create your health identity.'}
            </p>
          </div>

          {/* Tab selector */}
          <div style={{ background: 'var(--bg-body)', border: '1px solid var(--border)', padding: '5px', borderRadius: '16px', display: 'flex', marginBottom: '24px', gap: '4px' }}>
            {TABS.map(({ key, icon: Icon }) => (
              <button key={key} onClick={() => { setActiveTab(key); setIsLogin(true); setError(''); }}
                style={{
                  flex: 1, padding: '11px 8px', borderRadius: '12px', border: 'none', fontSize: '13px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', transition: 'all 0.25s ease',
                  background: activeTab === key ? 'var(--primary)' : 'transparent',
                  color: activeTab === key ? 'white' : 'var(--text-muted)',
                  boxShadow: activeTab === key ? 'var(--shadow-primary)' : 'none'
                }}>
                <Icon size={14} /> {key}
              </button>
            ))}
          </div>

          {/* Glass card */}
          <div style={{ background: 'var(--bg-glass)', backdropFilter: 'blur(20px)', border: '1px solid var(--border)', padding: '32px', borderRadius: '24px', boxShadow: 'var(--shadow-md)' }}>

            {/* Registration extra fields */}
            <AnimatePresence>
              {!isLogin && activeTab === 'Patient' && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: 'hidden' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '11px', marginBottom: '11px' }}>
                    <InputField placeholder="Full Name" colSpan style={{ gridColumn: 'span 2' }} onChange={inputF('name')} />
                    <InputField placeholder="Age" type="number" onChange={inputF('age')} onKeyDown={e => e.key === 'Enter' && handleAuth()} />
                    <InputField placeholder="Height (cm)" type="number" onChange={inputF('height')} onKeyDown={e => e.key === 'Enter' && handleAuth()} />
                    <InputField placeholder="Weight (kg)" type="number" colSpan onChange={inputF('weight')} onKeyDown={e => e.key === 'Enter' && handleAuth()} />
                    <InputField placeholder="Medical History (e.g. Diabetes)" colSpan onChange={inputF('diseaseInput')} onKeyDown={e => e.key === 'Enter' && handleAuth()} />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Login fields */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ position: 'relative' }}>
                <User size={17} style={{ position: 'absolute', top: '50%', left: '16px', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
                <input
                  placeholder="Username"
                  onChange={inputF('username')}
                  onKeyDown={e => e.key === 'Enter' && handleAuth()}
                  style={s.iconInput}
                />
              </div>

              <div style={{ position: 'relative' }}>
                <Lock size={17} style={{ position: 'absolute', top: '50%', left: '16px', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
                <input
                  type={showPass ? 'text' : 'password'}
                  placeholder="Password"
                  onChange={inputF('password')}
                  onKeyDown={e => e.key === 'Enter' && handleAuth()}
                  style={{ ...s.iconInput, paddingRight: '48px' }}
                />
                <button onClick={() => setShowPass(v => !v)}
                  style={{ position: 'absolute', top: '50%', right: '14px', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: '4px' }}>
                  {showPass ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>

              {/* Error */}
              <AnimatePresence>
                {error && (
                  <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    style={{ background: 'var(--danger-light)', border: '1px solid var(--danger)', borderRadius: '10px', padding: '10px 14px', color: 'var(--danger)', fontSize: '13px', fontWeight: '600' }}>
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Submit button */}
              <motion.button
                onClick={handleAuth}
                disabled={loading}
                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                style={{ width: '100%', padding: '16px', borderRadius: '14px', border: 'none', background: loading ? 'var(--text-muted)' : 'linear-gradient(135deg, var(--primary) 0%, #3b82f6 100%)', color: 'white', fontWeight: '800', fontSize: '15px', cursor: loading ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', boxShadow: loading ? 'none' : 'var(--shadow-primary)', marginTop: '4px' }}>
                {isLogin ? <><LogIn size={18} /> {loading ? 'Signing in…' : 'Access Dashboard'}</> : <><UserPlus size={18} /> {loading ? 'Creating…' : 'Create Account'}</>}
              </motion.button>
            </div>
          </div>

          {/* Toggle login/register */}
          {activeTab === 'Patient' && (
            <p onClick={() => { setIsLogin(l => !l); setError(''); }}
              style={{ textAlign: 'center', fontSize: '13px', color: 'var(--text-muted)', marginTop: '24px', cursor: 'pointer', fontWeight: '600' }}>
              {isLogin ? <>New to HealthScore? <span style={{ color: 'var(--primary)' }}>Create your ID →</span></> : <>Already have an account? <span style={{ color: 'var(--primary)' }}>Sign In →</span></>}
            </p>
          )}

          {activeTab === 'Enterprise' && (
            <p style={{ textAlign: 'center', fontSize: '12px', color: 'var(--text-faint)', marginTop: '20px', fontWeight: '500' }}>
              Demo: pharma1 / lab1 / ins1 &nbsp;·&nbsp; pass: password123
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// Reusable input helper
function InputField({ placeholder, type = 'text', onChange, onKeyDown, colSpan }) {
  return (
    <input
      type={type}
      placeholder={placeholder}
      onChange={onChange}
      onKeyDown={onKeyDown}
      style={{ width: '100%', padding: '13px 15px', borderRadius: '11px', border: '1px solid var(--border)', background: 'var(--input-bg)', color: 'var(--text-main)', fontSize: '14px', boxSizing: 'border-box', gridColumn: colSpan ? 'span 2' : undefined }}
    />
  );
}

const s = {
  iconInput: { width: '100%', padding: '14px 16px 14px 45px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--input-bg)', color: 'var(--text-main)', fontSize: '14px', boxSizing: 'border-box' },
};