import React, { useState } from 'react';
import axios from 'axios';
import { ShieldAlert, Database, Users, Package, FileText, Lock, Activity, ExternalLink, RefreshCw } from 'lucide-react';

const GRAFANA_BASE = 'http://localhost:3001';
const DASHBOARD_UID = 'healthscore';

// Solo panel URLs for embedding
const panels = [
  { id: 1, title: 'HTTP Request Rate',       h: '320px' },
  { id: 2, title: 'Request Latency (P95)',   h: '320px' },
  { id: 3, title: 'Prescription Activity',   h: '220px' },
  { id: 4, title: 'Appointment Activity',    h: '220px' },
  { id: 5, title: 'Active Users by Role',    h: '220px' },
  { id: 6, title: 'Fabric Tx by Org',        h: '320px' },
  { id: 7, title: 'Node.js Memory',          h: '320px' },
  { id: 8, title: 'Event Loop Lag',          h: '320px' },
  { id: 9, title: 'Fabric Peer Ledger Height', h: '180px' },
];

const panelUrl = (panelId) =>
  `${GRAFANA_BASE}/d-solo/${DASHBOARD_UID}/healthscore-monitoring?orgId=1&panelId=${panelId}&theme=dark&from=now-30m&to=now&refresh=5s`;

export default function Admin() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [adminKey, setAdminKey] = useState('');
  const [db, setDb] = useState(null);
  const [activeTab, setActiveTab] = useState('users');
  const [refreshKey, setRefreshKey] = useState(0);

  const handleUnlock = async () => {
    try {
      const res = await axios.post('http://localhost:5001/api/admin/access', { adminKey });
      setDb(res.data.database);
      setIsAuthenticated(true);
    } catch (err) {
      alert("ACCESS DENIED");
    }
  };

  // --- LOCK SCREEN ---
  if (!isAuthenticated) {
    return (
      <div style={{ height: '100vh', width: '100vw', background: '#0f172a', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#ef4444' }}>
        <ShieldAlert size={64} style={{ marginBottom: '20px' }} />
        <h1 style={{ fontFamily: 'monospace', letterSpacing: '2px', fontSize: '24px' }}>RESTRICTED AREA</h1>
        <p style={{ color: '#64748b', marginBottom: '30px' }}>Authorized Personnel Only</p>
        <div style={{ display: 'flex', gap: '10px' }}>
          <input 
            type="password" 
            placeholder="Enter Admin Key" 
            style={s.darkInput}
            onChange={(e) => setAdminKey(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleUnlock()}
          />
          <button onClick={handleUnlock} style={s.darkBtn}><Lock size={16}/></button>
        </div>
      </div>
    );
  }

  // --- DATA DASHBOARD ---
  const patients = db.users.filter(u => u.role === 'Patient');
  const staff = db.users.filter(u => u.role !== 'Patient');

  return (
    <div style={{ padding: '40px', background: '#f8fafc', minHeight: '100vh' }}>
      <header style={{ marginBottom: '40px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ color: '#1e293b', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Database color="#4f46e5" /> Master Database View
          </h1>
          <p style={{ color: '#64748b' }}>System-wide overview. Total Patients: <strong>{db.total_patients}</strong> | Total RX: <strong>{db.total_prescriptions}</strong></p>
        </div>
        <button onClick={() => window.location.href='/'} style={{...s.btn, background: '#ef4444'}}>Exit Admin Mode</button>
      </header>

      {/* TABS */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <TabButton label="User Database" icon={<Users size={18}/>} active={activeTab === 'users'} onClick={() => setActiveTab('users')} />
        <TabButton label="Global Inventory" icon={<Package size={18}/>} active={activeTab === 'inventory'} onClick={() => setActiveTab('inventory')} />
        <TabButton label="Monitoring" icon={<Activity size={18}/>} active={activeTab === 'monitoring'} onClick={() => setActiveTab('monitoring')} />
      </div>

      {activeTab === 'users' && (
        <div style={{ display: 'grid', gap: '30px' }}>
          {/* STAFF TABLE */}
          <div style={s.card}>
            <h3 style={s.sectionTitle}>Medical Staff (Doctors & Pharmacists)</h3>
            <table style={s.table}>
              <thead>
                <tr style={s.tr}><th style={s.th}>ID</th><th style={s.th}>Name</th><th style={s.th}>Role</th><th style={s.th}>Username</th><th style={s.th}>Pass (Plaintext)</th></tr>
              </thead>
              <tbody>
                {staff.map((u, i) => (
                  <tr key={i} style={s.tr}>
                    <td style={s.td}><strong>{u.id}</strong></td>
                    <td style={s.td}>{u.name}</td>
                    <td style={s.td}><span style={s.badge}>{u.role}</span></td>
                    <td style={s.td}>{u.username}</td>
                    <td style={{...s.td, fontFamily: 'monospace', color: '#ef4444'}}>{u.password}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* PATIENTS TABLE */}
          <div style={s.card}>
            <h3 style={s.sectionTitle}>Patient Records</h3>
            {patients.map((p, i) => (
              <div key={i} style={{ border: '1px solid #e2e8f0', borderRadius: '12px', padding: '20px', marginBottom: '15px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
                  <div>
                    <h4 style={{ margin: 0, color: '#1e293b' }}>{p.name} <span style={{ color: '#64748b', fontWeight: '400' }}>({p.id})</span></h4>
                    <small style={{ color: '#64748b' }}>Age: {p.age} | H: {p.height} | W: {p.weight}</small>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontWeight: 'bold', color: '#4f46e5' }}>History: {p.diseaseInput}</div>
                  </div>
                </div>
                
                <div style={{ background: '#f1f5f9', padding: '15px', borderRadius: '8px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#64748b', marginBottom: '5px', textTransform: 'uppercase' }}>Prescriptions ({p.prescriptions.length})</div>
                  {p.prescriptions.length > 0 ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px' }}>
                      {p.prescriptions.map((rx, j) => (
                        <div key={j} style={{ background: 'white', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '13px' }}>
                          <div style={{ fontWeight: 'bold', color: '#1e293b' }}>{rx.medicine}</div>
                          <div style={{ color: '#64748b' }}>{rx.frequency}</div>
                          <div style={{ color: '#ef4444', fontSize: '11px', marginTop: '4px' }}>{rx.id}</div>
                        </div>
                      ))}
                    </div>
                  ) : <span style={{fontSize: '13px', color: '#94a3b8'}}>No records found.</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'inventory' && (
        <div style={s.card}>
          <h3 style={s.sectionTitle}>Global Pharmacy Inventory</h3>
          <table style={s.table}>
            <thead>
              <tr style={s.tr}><th style={s.th}>ID</th><th style={s.th}>Medicine Name</th><th style={s.th}>Stock Level</th><th style={s.th}>Price</th><th style={s.th}>Expiry</th></tr>
            </thead>
            <tbody>
              {db.inventory.map((item, i) => (
                <tr key={i} style={s.tr}>
                  <td style={s.td}>{item.id}</td>
                  <td style={s.td}><strong>{item.name}</strong></td>
                  <td style={s.td}>
                    {item.stock < 20 ? <span style={{color: '#ef4444', fontWeight:'bold'}}>Low ({item.stock})</span> : <span style={{color: '#16a34a', fontWeight:'bold'}}>{item.stock}</span>}
                  </td>
                  <td style={s.td}>₹{item.price}</td>
                  <td style={s.td}>{item.expiry}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'monitoring' && (
        <div>
          {/* Header bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <div>
              <h3 style={{ margin: 0, color: '#1e293b', fontWeight: '800', fontSize: '20px' }}>System Monitoring</h3>
              <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '13px' }}>Live metrics from Prometheus & Grafana — auto-refreshes every 5s</p>
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button onClick={() => setRefreshKey(k => k + 1)} style={{ ...s.btn, background: '#4f46e5', padding: '9px 16px', fontSize: '13px' }}>
                <RefreshCw size={14} /> Refresh
              </button>
              <a href={`${GRAFANA_BASE}/d/${DASHBOARD_UID}`} target="_blank" rel="noreferrer" style={{ ...s.btn, background: '#059669', padding: '9px 16px', fontSize: '13px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <ExternalLink size={14} /> Full Dashboard
              </a>
            </div>
          </div>

          {/* Row 1: HTTP traffic */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            {panels.slice(0, 2).map(p => (
              <div key={p.id} style={{ ...s.card, padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '12px 18px', borderBottom: '1px solid #e2e8f0', fontSize: '13px', fontWeight: '700', color: '#334155' }}>{p.title}</div>
                <iframe key={refreshKey} src={panelUrl(p.id)} width="100%" height={p.h} frameBorder="0" style={{ display: 'block', background: '#1e1e2e' }} />
              </div>
            ))}
          </div>

          {/* Row 2: Business metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            {panels.slice(2, 5).map(p => (
              <div key={p.id} style={{ ...s.card, padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '12px 18px', borderBottom: '1px solid #e2e8f0', fontSize: '13px', fontWeight: '700', color: '#334155' }}>{p.title}</div>
                <iframe key={refreshKey} src={panelUrl(p.id)} width="100%" height={p.h} frameBorder="0" style={{ display: 'block', background: '#1e1e2e' }} />
              </div>
            ))}
          </div>

          {/* Row 3: Fabric + System */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            {panels.slice(5, 8).map(p => (
              <div key={p.id} style={{ ...s.card, padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '12px 18px', borderBottom: '1px solid #e2e8f0', fontSize: '13px', fontWeight: '700', color: '#334155' }}>{p.title}</div>
                <iframe key={refreshKey} src={panelUrl(p.id)} width="100%" height={p.h} frameBorder="0" style={{ display: 'block', background: '#1e1e2e' }} />
              </div>
            ))}
          </div>

          {/* Row 4: Ledger height */}
          <div style={{ ...s.card, padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '12px 18px', borderBottom: '1px solid #e2e8f0', fontSize: '13px', fontWeight: '700', color: '#334155' }}>Fabric Peer Ledger Height</div>
            <iframe key={refreshKey} src={panelUrl(9)} width="100%" height="180px" frameBorder="0" style={{ display: 'block', background: '#1e1e2e' }} />
          </div>
        </div>
      )}
    </div>
  );
}

// --- COMPONENTS & STYLES ---
const TabButton = ({ label, icon, active, onClick }) => (
  <button onClick={onClick} style={{
    display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 20px', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold',
    background: active ? '#4f46e5' : 'white', color: active ? 'white' : '#64748b', boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
  }}>
    {icon} {label}
  </button>
);

const s = {
  darkInput: { padding: '12px', background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: 'white', outline: 'none', width: '250px' },
  darkBtn: { padding: '12px', background: '#ef4444', border: 'none', borderRadius: '8px', color: 'white', cursor: 'pointer' },
  btn: { padding: '10px 20px', borderRadius: '8px', border: 'none', color: 'white', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' },
  card: { background: 'white', borderRadius: '16px', padding: '25px', boxShadow: '0 4px 6px rgba(0,0,0,0.05)', marginBottom: '20px' },
  sectionTitle: { margin: '0 0 20px 0', color: '#1e293b' },
  table: { width: '100%', borderCollapse: 'collapse' },
  tr: { borderBottom: '1px solid #f1f5f9' },
  th: { textAlign: 'left', padding: '12px', color: '#64748b', fontSize: '13px', textTransform: 'uppercase' },
  td: { padding: '12px', color: '#334155', fontSize: '14px' },
  badge: { background: '#e0e7ff', color: '#4338ca', padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: 'bold' }
};