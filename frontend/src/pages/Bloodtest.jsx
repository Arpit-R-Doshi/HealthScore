import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Routes, Route, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, Syringe, AlertCircle, CheckCircle2, X,
  UploadCloud, Clock, History, ChevronDown, ChevronUp,
  FileCheck, User, Calendar, Stethoscope, AlertTriangle, Activity
} from 'lucide-react';

const PRIORITY_COLOR = {
  'Routine': 'var(--success)',
  'Urgent': 'var(--warning)',
  'STAT (Immediate)': 'var(--danger)',
};
const PRIORITY_BG = {
  'Routine': 'rgba(16,185,129,0.1)',
  'Urgent': 'rgba(245,158,11,0.15)',
  'STAT (Immediate)': 'rgba(239,68,68,0.1)',
};

export default function Bloodtest({ user }) {
  const navigate = useNavigate();

  const [alertConfig, setAlertConfig] = useState({ isOpen: false, title: '', message: '', type: 'success' });
  const showAlert = (title, message, type = 'success') => setAlertConfig({ isOpen: true, title, message, type });
  const closeAlert = () => setAlertConfig({ ...alertConfig, isOpen: false });

  const CustomAlert = () => (
    <AnimatePresence>
      {alertConfig.isOpen && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.4)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(5px)' }}>
          <motion.div initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9, y: 20 }}
            style={{ background: 'var(--bg-surface)', padding: '30px', borderRadius: '24px', width: '90%', maxWidth: '400px', border: '1px solid var(--border)', boxShadow: '0 20px 40px rgba(0,0,0,0.2)', textAlign: 'center', position: 'relative' }}>
            <button onClick={closeAlert} style={{ position: 'absolute', top: '15px', right: '15px', background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={20} /></button>
            <div style={{ display: 'inline-flex', marginBottom: '15px', background: alertConfig.type === 'error' ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)', padding: '15px', borderRadius: '50%' }}>
              {alertConfig.type === 'error' ? <AlertCircle color="var(--danger)" size={40} /> : <CheckCircle2 color="var(--success)" size={40} />}
            </div>
            <h3 style={{ margin: '0 0 10px 0', color: 'var(--text-main)', fontSize: '22px' }}>{alertConfig.title}</h3>
            <p style={{ color: 'var(--text-muted)', margin: '0 0 25px 0', lineHeight: '1.5' }}>{alertConfig.message}</p>
            <button onClick={closeAlert} style={{ width: '100%', padding: '14px', background: alertConfig.type === 'error' ? 'var(--danger)' : 'var(--success)', color: 'white', border: 'none', borderRadius: '12px', fontWeight: 'bold', fontSize: '16px', cursor: 'pointer' }}>Acknowledge</button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  // ============================================================
  // VIEW 1: PATIENT ORDERS
  // ============================================================
  const PatientOrdersView = () => {
    const [patientId, setPatientId] = useState('');
    const [patientData, setPatientData] = useState(null);
    const [scanState, setScanState] = useState({});
    const [loading, setLoading] = useState(false);

    const fetchPatient = async () => {
      if (!patientId.trim()) return showAlert('Error', 'Please enter a Patient ID.', 'error');
      setLoading(true);
      try {
        const res = await axios.get(`http://localhost:5001/api/patient/${patientId.trim()}?role=Bloodtest`);
        setPatientData(res.data);
        setScanState({});
      } catch {
        showAlert('Not Found', 'Patient ID does not exist.', 'error');
        setPatientData(null);
      }
      setLoading(false);
    };

    const toggleExpand = (scanId) =>
      setScanState(prev => ({ ...prev, [scanId]: { ...prev[scanId], expanded: !prev[scanId]?.expanded } }));

    const setFile = (scanId, file) =>
      setScanState(prev => ({ ...prev, [scanId]: { ...prev[scanId], file } }));

    const completeScan = async (scan) => {
      const state = scanState[scan.id] || {};
      setScanState(prev => ({ ...prev, [scan.id]: { ...prev[scan.id], uploading: true } }));
      try {
        let ipfsHash = '', fileName = '';
        if (state.file) {
          const fd = new FormData();
          fd.append('file', state.file);
          const uploadRes = await axios.post('http://localhost:5001/api/upload', fd);
          ipfsHash = uploadRes.data.ipfsHash;
          fileName = state.file.name;
        }
        await axios.post('http://localhost:5001/api/bloodtest/complete-scan', {
          patientId: patientId.trim(), scanId: scan.id, ipfsHash,
          fileName: fileName || `${scan.scanType} Report`, scanType: scan.scanType,
        });
        showAlert('Scan Completed', `${scan.scanType} marked as done${ipfsHash ? ' and report uploaded.' : '.'}`, 'success');
        const res = await axios.get(`http://localhost:5001/api/patient/${patientId.trim()}?role=Bloodtest`);
        setPatientData(res.data);
        setScanState({});
      } catch (e) {
        showAlert('Error', e.response?.data?.error || 'Failed to complete scan.', 'error');
        setScanState(prev => ({ ...prev, [scan.id]: { ...prev[scan.id], uploading: false } }));
      }
    };

    const pendingScans = (patientData?.scanRequests || []).filter(s => s.status !== 'Completed');
    const completedScans = (patientData?.scanRequests || []).filter(s => s.status === 'Completed');

    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} style={{ padding: '40px', maxWidth: '900px', margin: '0 auto' }}>
        <header style={{ marginBottom: '30px' }}>
          <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '28px', fontWeight: '800' }}>{user.name} Portal</h2>
          <p style={{ color: 'var(--text-muted)', margin: '5px 0 0 0' }}>Diagnostic Lab & Scan Fulfillment</p>
        </header>

        {/* ── REDESIGNED LOOKUP CARD ── */}
        <div style={{ background: 'linear-gradient(135deg, var(--primary) 0%, #6366f1 100%)', borderRadius: '24px', padding: '30px', marginBottom: '30px', position: 'relative', overflow: 'hidden', boxShadow: '0 8px 30px rgba(79,70,229,0.3)' }}>
          {/* Background icon */}
          <Activity size={120} style={{ position: 'absolute', right: '-20px', bottom: '-25px', opacity: 0.08, color: 'white' }} />

          <h3 style={{ color: 'white', margin: '0 0 6px 0', fontSize: '18px', fontWeight: '800', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Search size={20} /> Patient Lookup
          </h3>
          <p style={{ color: 'rgba(255,255,255,0.7)', margin: '0 0 20px 0', fontSize: '14px' }}>Enter a patient ID to view their pending scan and lab orders.</p>

          <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <User size={17} style={{ position: 'absolute', left: '15px', top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,0.5)' }} />
              <input
                style={{ width: '100%', padding: '14px 16px 14px 44px', borderRadius: '14px', border: '2px solid rgba(255,255,255,0.25)', background: 'rgba(255,255,255,0.15)', color: 'white', fontSize: '15px', outline: 'none', fontFamily: 'inherit', backdropFilter: 'blur(8px)', boxSizing: 'border-box' }}
                placeholder="e.g. PT-1000"
                value={patientId}
                onChange={e => setPatientId(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && fetchPatient()}
              />
            </div>
            <button
              onClick={fetchPatient}
              disabled={loading}
              style={{ padding: '0 28px', background: 'white', color: 'var(--primary)', border: 'none', borderRadius: '14px', fontWeight: '800', fontSize: '15px', cursor: loading ? 'wait' : 'pointer', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '8px', transition: '0.2s', boxShadow: '0 4px 15px rgba(0,0,0,0.15)' }}>
              <Search size={17} /> {loading ? 'Searching...' : 'Look Up'}
            </button>
          </div>
        </div>

        {patientData && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
            {/* Patient Banner */}
            <div style={{ ...s.card, padding: '20px 25px', display: 'flex', alignItems: 'center', gap: '16px', background: 'var(--primary-light)', border: 'none' }}>
              <div style={{ width: '50px', height: '50px', borderRadius: '50%', background: 'var(--primary)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '800', fontSize: '20px', flexShrink: 0 }}>
                {patientData.name?.charAt(0)}
              </div>
              <div>
                <div style={{ fontWeight: '800', color: 'var(--text-main)', fontSize: '18px' }}>{patientData.name}</div>
                <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>Age: {patientData.age} &nbsp;·&nbsp; Patient ID: {patientId}</div>
              </div>
            </div>

            {/* PENDING SCANS */}
            <div style={s.card}>
              <h3 style={{ margin: '0 0 20px 0', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Syringe color="var(--warning)" size={20} /> Pending Orders
                <span style={{ background: 'rgba(245,158,11,0.15)', color: 'var(--warning)', borderRadius: '20px', padding: '3px 12px', fontSize: '13px', fontWeight: '700' }}>{pendingScans.length}</span>
              </h3>

              {pendingScans.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {pendingScans.map((scan) => {
                    const st = scanState[scan.id] || {};
                    return (
                      <div key={scan.id} style={{ border: '1px solid var(--border)', borderRadius: '16px', overflow: 'hidden', borderLeft: `4px solid ${PRIORITY_COLOR[scan.priority] || 'var(--primary)'}` }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', background: 'var(--input-bg)' }}>
                          <div>
                            <div style={{ color: 'var(--text-main)', fontWeight: '700', fontSize: '16px' }}>{scan.scanType}</div>
                            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>Ordered by: {scan.doctorName} &nbsp;·&nbsp; {scan.date}</div>
                            {scan.notes && <div style={{ fontSize: '12px', color: 'var(--text-main)', marginTop: '8px', background: 'var(--bg-surface)', padding: '8px 12px', borderRadius: '8px', border: '1px solid var(--border)' }}>Note: {scan.notes}</div>}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                            <span style={{ fontSize: '12px', fontWeight: 'bold', color: PRIORITY_COLOR[scan.priority] }}>{scan.priority}</span>
                            <button onClick={() => toggleExpand(scan.id)}
                              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '8px 14px', cursor: 'pointer', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '600', fontSize: '13px' }}>
                              {st.expanded ? <><ChevronUp size={16} /> Close</> : <><ChevronDown size={16} /> Complete</>}
                            </button>
                          </div>
                        </div>
                        <AnimatePresence>
                          {st.expanded && (
                            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: 'hidden' }}>
                              <div style={{ padding: '20px', borderTop: '1px solid var(--border)', background: 'var(--bg-surface)', display: 'flex', flexDirection: 'column', gap: '15px' }}>
                                <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)', fontWeight: '600' }}>Upload report (optional) then mark as complete:</p>
                                <label style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '14px 16px', border: '2px dashed var(--border)', borderRadius: '12px', background: 'var(--input-bg)', cursor: 'pointer' }}>
                                  <UploadCloud size={22} color="var(--primary)" />
                                  <span style={{ fontSize: '14px', color: st.file ? 'var(--text-main)' : 'var(--text-muted)', fontWeight: '600' }}>
                                    {st.file ? st.file.name : 'Attach report file (PDF, image, etc.)'}
                                  </span>
                                  <input type="file" style={{ display: 'none' }} onChange={e => setFile(scan.id, e.target.files[0])} />
                                </label>
                                <div style={{ display: 'flex', gap: '10px' }}>
                                  <button disabled={st.uploading} onClick={() => completeScan(scan)}
                                    style={{ ...s.btn, background: st.uploading ? 'var(--text-muted)' : 'var(--success)', flex: 1, justifyContent: 'center' }}>
                                    <CheckCircle2 size={18} /> {st.uploading ? 'Processing...' : 'Mark as Done & Upload'}
                                  </button>
                                  <button onClick={() => toggleExpand(scan.id)}
                                    style={{ ...s.btn, background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>Cancel</button>
                                </div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', border: '1px dashed var(--border)', borderRadius: '12px' }}>No pending scan orders for this patient.</div>
              )}
            </div>

            {/* COMPLETED SCANS */}
            {completedScans.length > 0 && (
              <div style={s.card}>
                <h3 style={{ margin: '0 0 20px 0', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <CheckCircle2 color="var(--success)" size={20} /> Completed Orders
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {completedScans.map((scan) => (
                    <div key={scan.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 18px', background: 'var(--input-bg)', borderRadius: '12px', border: '1px solid var(--border)' }}>
                      <div>
                        <div style={{ fontWeight: '700', color: 'var(--text-main)' }}>{scan.scanType}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '3px' }}>Completed: {scan.completedDate || '—'}</div>
                      </div>
                      {scan.reportHash ? (
                        <a href={`https://gateway.pinata.cloud/ipfs/${scan.reportHash}`} target="_blank" rel="noreferrer"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 16px', background: 'var(--primary)', color: 'white', borderRadius: '8px', textDecoration: 'none', fontWeight: '600', fontSize: '13px' }}>
                          <FileCheck size={14} /> View Report
                        </a>
                      ) : (
                        <span style={{ background: 'rgba(16,185,129,0.1)', color: 'var(--success)', padding: '6px 14px', borderRadius: '8px', fontSize: '12px', fontWeight: 'bold' }}>✓ Done</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </motion.div>
    );
  };

  // ============================================================
  // VIEW 2: PATIENT HISTORY — accordion per scan
  // ============================================================
  const PatientHistoryView = () => {
    const [patients, setPatients] = useState([]);
    const [search, setSearch] = useState('');
    const [loading, setLoading] = useState(true);
    // expandedScans: { [patientId_scanId]: true/false }
    const [expandedScans, setExpandedScans] = useState({});

    useEffect(() => {
      const fetch = async () => {
        try {
          const res = await axios.get('http://localhost:5001/api/bloodtest/patients');
          setPatients(res.data);
        } catch { }
        setLoading(false);
      };
      fetch();
    }, []);

    const toggleScan = (key) =>
      setExpandedScans(prev => ({ ...prev, [key]: !prev[key] }));

    const filtered = patients.filter(p =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.id.toLowerCase().includes(search.toLowerCase())
    );

    const StatusBadge = ({ status }) => {
      const isComplete = status === 'Completed';
      return (
        <span style={{
          padding: '4px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '700',
          background: isComplete ? 'rgba(16,185,129,0.12)' : 'rgba(245,158,11,0.15)',
          color: isComplete ? 'var(--success)' : 'var(--warning)'
        }}>
          {isComplete ? '✓ Completed' : '⏳ Pending'}
        </span>
      );
    };

    return (
      <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} style={{ padding: '40px', maxWidth: '900px', margin: '0 auto' }}>
        <header style={{ marginBottom: '30px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '15px' }}>
          <div>
            <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '28px', fontWeight: '800' }}>Patient History</h2>
            <p style={{ color: 'var(--text-muted)', margin: '5px 0 0 0' }}>All patients with lab or scan orders — click any test to expand.</p>
          </div>
          <div style={{ position: 'relative', width: '280px' }}>
            <Search style={{ position: 'absolute', left: '14px', top: '13px', color: 'var(--text-muted)' }} size={18} />
            <input style={{ ...s.input, paddingLeft: '42px' }} placeholder="Search by name or ID..."
              value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </header>

        {loading ? (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>Loading...</p>
        ) : filtered.length === 0 ? (
          <div style={{ padding: '50px', textAlign: 'center', color: 'var(--text-muted)', border: '1px dashed var(--border)', borderRadius: '16px', background: 'var(--bg-surface)' }}>
            <History size={40} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <p style={{ margin: 0 }}>{search ? 'No patients match your search.' : 'No patients with scan orders yet.'}</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {filtered.map((p) => {
              const scans = p.scanRequests || [];
              const doneCount = scans.filter(s => s.status === 'Completed').length;
              const pendingCount = scans.length - doneCount;

              return (
                <div key={p.id} style={{ background: 'var(--bg-surface)', borderRadius: '20px', border: '1px solid var(--border)', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>

                  {/* ── Patient header row ── */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '20px 24px', borderBottom: '1px solid var(--border)' }}>
                    <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'var(--primary-light)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '800', fontSize: '20px', flexShrink: 0 }}>
                      {p.name.charAt(0)}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: '800', color: 'var(--text-main)', fontSize: '17px' }}>{p.name}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '3px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <User size={12} /> ID: {p.id} &nbsp;·&nbsp; Age: {p.age}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
                      {pendingCount > 0 && <span style={{ background: 'rgba(245,158,11,0.15)', color: 'var(--warning)', padding: '4px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: '700' }}>{pendingCount} Pending</span>}
                      {doneCount > 0 && <span style={{ background: 'rgba(16,185,129,0.1)', color: 'var(--success)', padding: '4px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: '700' }}>{doneCount} Done</span>}
                    </div>
                  </div>

                  {/* ── Scan rows (accordion) ── */}
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    {scans.map((scan, idx) => {
                      const key = `${p.id}_${scan.id}`;
                      const isExpanded = !!expandedScans[key];
                      const isLast = idx === scans.length - 1;

                      return (
                        <div key={scan.id} style={{ borderBottom: isLast ? 'none' : '1px solid var(--border)' }}>
                          {/* Scan row — always visible, clickable */}
                          <button
                            onClick={() => toggleScan(key)}
                            style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '16px', padding: '14px 24px', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left', transition: 'background 0.15s' }}
                            onMouseEnter={e => e.currentTarget.style.background = 'var(--input-bg)'}
                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>

                            {/* Priority indicator dot */}
                            <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: PRIORITY_COLOR[scan.priority] || 'var(--primary)', flexShrink: 0 }} />

                            {/* Scan type + quick info */}
                            <div style={{ flex: 1 }}>
                              <div style={{ fontWeight: '700', color: 'var(--text-main)', fontSize: '15px' }}>{scan.scanType}</div>
                              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                                {scan.date} &nbsp;·&nbsp; Ordered by {scan.doctorName}
                              </div>
                            </div>

                            <StatusBadge status={scan.status} />
                            {isExpanded ? <ChevronUp size={18} color="var(--text-muted)" /> : <ChevronDown size={18} color="var(--text-muted)" />}
                          </button>

                          {/* Expanded detail panel */}
                          <AnimatePresence>
                            {isExpanded && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                style={{ overflow: 'hidden' }}>
                                <div style={{ margin: '0 24px 16px 24px', background: 'var(--input-bg)', borderRadius: '14px', border: '1px solid var(--border)', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>

                                  {/* Detail grid */}
                                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                                    <DetailItem icon={<User size={14} />} label="Patient Name" value={p.name} />
                                    <DetailItem icon={<User size={14} />} label="Patient ID" value={p.id} />
                                    <DetailItem icon={<Stethoscope size={14} />} label="Ordered By" value={scan.doctorName} />
                                    <DetailItem icon={<Calendar size={14} />} label="Order Date" value={scan.date} />
                                    <DetailItem icon={<Syringe size={14} />} label="Test Type" value={scan.scanType} />
                                    <DetailItem
                                      icon={<AlertTriangle size={14} />}
                                      label="Priority"
                                      value={<span style={{ color: PRIORITY_COLOR[scan.priority], fontWeight: '700' }}>{scan.priority}</span>}
                                    />
                                    {scan.status === 'Completed' && (
                                      <DetailItem icon={<CheckCircle2 size={14} />} label="Completed On" value={scan.completedDate || '—'} />
                                    )}
                                  </div>

                                  {/* Clinical notes */}
                                  {scan.notes && (
                                    <div style={{ padding: '12px 14px', background: 'var(--bg-surface)', borderRadius: '10px', border: '1px solid var(--border)' }}>
                                      <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>Clinical Notes</div>
                                      <div style={{ fontSize: '14px', color: 'var(--text-main)', lineHeight: '1.5' }}>{scan.notes}</div>
                                    </div>
                                  )}

                                  {/* Report link if available */}
                                  {scan.reportHash && (
                                    <a href={`https://gateway.pinata.cloud/ipfs/${scan.reportHash}`} target="_blank" rel="noreferrer"
                                      style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 18px', background: 'var(--primary)', color: 'white', borderRadius: '10px', textDecoration: 'none', fontWeight: '700', fontSize: '14px', alignSelf: 'flex-start' }}>
                                      <FileCheck size={16} /> View Uploaded Report
                                    </a>
                                  )}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </motion.div>
    );
  };

  return (
    <>
      <CustomAlert />
      <Routes>
        <Route path="/" element={<PatientOrdersView />} />
        <Route path="/history" element={<PatientHistoryView />} />
      </Routes>
    </>
  );
}

// Small helper component for the detail grid
function DetailItem({ icon, label, value }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '5px' }}>
        {icon} {label}
      </div>
      <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-main)' }}>{value}</div>
    </div>
  );
}

const s = {
  card: { background: 'var(--bg-surface)', padding: '30px', borderRadius: '24px', boxShadow: 'var(--shadow-sm)', border: '1px solid var(--border)' },
  input: { width: '100%', padding: '14px 16px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--input-bg)', color: 'var(--text-main)', fontSize: '14px', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit' },
  btn: { padding: '12px 20px', border: 'none', borderRadius: '10px', background: 'var(--primary)', color: 'white', fontWeight: 'bold', cursor: 'pointer', transition: '0.2s', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px' },
};