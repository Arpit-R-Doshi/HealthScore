import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Routes, Route, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity, HeartPulse, FileText, Pill, FileCheck, Shield,
  User, UploadCloud, FolderOpen, Send, Bot,
  MapPin, Calendar, Stethoscope, Search, AlertCircle, CheckCircle2, X, Clock, Star,
  Syringe, ClipboardList, TrendingUp, Zap, ScanLine
} from 'lucide-react';

// Helpers
const formatDate = (dateStr) => {
  if (!dateStr) return '—';
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  return parts[0].length === 4 ? `${parts[2]}-${parts[1]}-${parts[0]}` : dateStr;
};

const TIME_SLOTS = [
  '09:00','09:30','10:00','10:30','11:00','11:30',
  '12:00','12:30','13:00','13:30','14:00','14:30',
  '15:00','15:30','16:00','16:30','17:00','17:30',
  '18:00','18:30','19:00','19:30','20:00','20:30','21:00',
];

export default function Patient({ user }) {
  const [liveUser, setLiveUser] = useState(user);
  const [healthData, setHealthData] = useState(null);
  const [medicalFiles, setMedicalFiles] = useState(user.medicalFiles || []);
  const [appointments, setAppointments] = useState(user.appointments || []);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [vaultCategory, setVaultCategory] = useState('Medical Summary');
  const [greeting, setGreeting] = useState('');
  const [alertConfig, setAlertConfig] = useState({ isOpen: false, title: '', message: '', type: 'success' });
  const [docSearch, setDocSearch] = useState('');
  const [bookingDocId, setBookingDocId] = useState(null);
  const [apptForm, setApptForm] = useState({ date: '', time: '' });

  const fallbackTeam = [
    { id: 'DR-001', name: 'Dr. Arpit Doshi', speciality: 'Cardiologist', hospital: 'Nanavati Super Speciality Hospital' },
    { id: 'DR-002', name: 'Dr. Priya Sharma', speciality: 'Endocrinologist', hospital: 'Lilavati Hospital' },
    { id: 'DR-003', name: 'Dr. Anil Desai', speciality: 'Orthopedic Surgeon', hospital: 'Kokilaben Hospital' },
    { id: 'DR-004', name: 'Dr. Vikram Patel', speciality: 'Neurologist', hospital: 'Breach Candy Hospital' },
  ];
  const medicalTeam = liveUser.medicalTeam?.length > 0 ? liveUser.medicalTeam : fallbackTeam;

  const safeWeight = liveUser?.weight || 0;
  const safeHeight = liveUser?.height || 1;
  const firstName = (liveUser?.name || 'Patient').split(' ')[0];
  const bmi = (safeWeight / Math.pow(safeHeight / 100, 2)).toFixed(1);
  let bmiStatus = 'Normal'; let bmiColor = 'var(--success)';
  if (bmi < 18.5) { bmiStatus = 'Underweight'; bmiColor = 'var(--warning)'; }
  else if (bmi >= 25 && bmi < 30) { bmiStatus = 'Overweight'; bmiColor = 'var(--warning)'; }
  else if (bmi >= 30) { bmiStatus = 'Obese'; bmiColor = 'var(--danger)'; }

  const defaultChat = [{ role: 'assistant', content: `Hi ${firstName}! I'm your personalized HealthScore AI. Ask me anything about your health.` }];
  const [messages, setMessages] = useState(() => {
    try { const s = sessionStorage.getItem(`chatHistory_${liveUser.id}`); return s ? JSON.parse(s) : defaultChat; } catch { return defaultChat; }
  });
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const endOfMessagesRef = useRef(null);

  const showAlert = (title, message, type = 'success') => setAlertConfig({ isOpen: true, title, message, type });
  const closeAlert = () => setAlertConfig(a => ({ ...a, isOpen: false }));
  const getTodayDate = () => { const tz = new Date().getTimezoneOffset() * 60000; return new Date(Date.now() - tz).toISOString().split('T')[0]; };

  useEffect(() => { endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { sessionStorage.setItem(`chatHistory_${liveUser.id}`, JSON.stringify(messages)); }, [messages, liveUser.id]);

  const fetchPatientData = async () => {
    try {
      const res = await axios.get(`http://localhost:5001/api/patient/${user.id}?role=Patient`);
      setLiveUser({ ...user, ...res.data });
      setAppointments(res.data.appointments || []);
      setMedicalFiles(res.data.medicalFiles || []);
    } catch { }
  };

  useEffect(() => { fetchPatientData(); }, []);
  useEffect(() => {
    const h = new Date().getHours();
    setGreeting(h < 12 ? 'Good Morning' : h < 18 ? 'Good Afternoon' : 'Good Evening');
    const fetchScore = async () => {
      try {
        const payload = { age: liveUser.age, height: liveUser.height, weight: liveUser.weight, gender: 'male', diseaseInput: liveUser.diseaseInput || liveUser.history };
        const res = await axios.post('http://localhost:5001/api/calculate-score', payload);
        setHealthData(res.data);
      } catch { }
    };
    if (liveUser.age) fetchScore();
  }, [liveUser]);

  const sendMessage = async () => {
    if (!chatInput.trim()) return;
    const currentInput = chatInput;
    const updated = [...messages, { role: 'user', content: currentInput }];
    setMessages(updated); setChatInput(''); setIsChatLoading(true);
    try {
      const history = updated.slice(-15).map(m => ({ role: m.role, content: m.content }));
      const res = await axios.post('http://localhost:5001/api/chat', { 
        patientData: { ...liveUser, health_score: healthData ? healthData.health_score : 'Calculating...' }, 
        messages: history 
      });
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.reply }]);
    } catch { setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Lost connection to server.' }]); }
    setIsChatLoading(false);
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append('file', selectedFile);
      const r = await axios.post('http://localhost:5001/api/upload', fd);
      await axios.post('http://localhost:5001/api/patient/add-file', { patientId: liveUser.id, ipfsHash: r.data.ipfsHash, fileName: selectedFile.name, category: vaultCategory });
      fetchPatientData(); setUploading(false); setSelectedFile(null);
      showAlert('Upload Successful', 'File securely stored on IPFS.');
    } catch { setUploading(false); showAlert('Upload Failed', 'Could not reach the IPFS network.', 'error'); }
  };

  const handleBook = async (doctor) => {
    if (!apptForm.date || !apptForm.time) return showAlert('Missing Info', 'Select a date and time slot.', 'error');
    try {
      const res = await axios.post('http://localhost:5001/api/book-appointment', { patientId: liveUser.id, doctorId: doctor.id, doctorName: doctor.name, date: apptForm.date, time: apptForm.time });
      fetchPatientData(); showAlert('Appointment Confirmed', res.data.message);
      setBookingDocId(null); setApptForm({ date: '', time: '' });
    } catch { showAlert('Booking Error', 'Failed to communicate with server.', 'error'); }
  };

  const toggleFavorite = async (doctorId) => {
    try {
      const res = await axios.post('http://localhost:5001/api/patient/toggle-favorite', { patientId: liveUser.id, doctorId });
      setLiveUser({ ...liveUser, favoriteDoctors: res.data.favoriteDoctors });
    } catch { showAlert('Error', 'Could not update favorites.', 'error'); }
  };

  const filteredTeam = medicalTeam
    .filter(d => d.name.toLowerCase().includes(docSearch.toLowerCase()) || d.speciality.toLowerCase().includes(docSearch.toLowerCase()) || d.hospital.toLowerCase().includes(docSearch.toLowerCase()))
    .sort((a, b) => (liveUser.favoriteDoctors?.includes(b.id) ? 1 : 0) - (liveUser.favoriteDoctors?.includes(a.id) ? 1 : 0));

  // ── Custom Alert Modal ──────────────────────────
  const CustomAlert = () => (
    <AnimatePresence>
      {alertConfig.isOpen && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(6px)' }}>
          <motion.div initial={{ scale: 0.9, y: 24 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.92, y: 12 }}
            style={{ background: 'var(--bg-surface)', padding: '36px', borderRadius: '28px', width: '90%', maxWidth: '400px', border: '1px solid var(--border)', boxShadow: 'var(--shadow-md)', textAlign: 'center', position: 'relative' }}>
            <button onClick={closeAlert} style={{ position: 'absolute', top: '14px', right: '14px', background: 'var(--bg-body)', border: '1px solid var(--border)', borderRadius: '8px', padding: '6px', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}><X size={16} /></button>
            <div style={{ display: 'inline-flex', marginBottom: '18px', background: alertConfig.type === 'error' ? 'var(--danger-light)' : 'var(--success-light)', padding: '16px', borderRadius: '50%' }}>
              {alertConfig.type === 'error' ? <AlertCircle color="var(--danger)" size={36} /> : <CheckCircle2 color="var(--success)" size={36} />}
            </div>
            <h3 style={{ margin: '0 0 10px', color: 'var(--text-main)', fontSize: '20px', fontWeight: '800' }}>{alertConfig.title}</h3>
            <p style={{ color: 'var(--text-muted)', margin: '0 0 28px', lineHeight: '1.6', fontSize: '14px' }}>{alertConfig.message}</p>
            <button onClick={closeAlert} style={{ width: '100%', padding: '14px', background: alertConfig.type === 'error' ? 'var(--danger)' : 'var(--success)', color: 'white', border: 'none', borderRadius: '12px', fontWeight: '800', fontSize: '15px', cursor: 'pointer' }}>Got it</button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  return (
    <>
      <CustomAlert />
      <Routes>

        {/* ══════════════════════════════════════════════
            ROUTE 1 — DASHBOARD
        ══════════════════════════════════════════════ */}
        <Route path="/" element={
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} style={s.page}>

            {/* Page header */}
            <div style={{ marginBottom: '28px' }}>
              <h2 style={s.pageTitle}>{greeting}, {firstName}</h2>
              <p style={s.pageSub}>Here's your personal health overview powered by AI & blockchain.</p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              {/* ── LEFT COLUMN ── */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                {/* Health Score hero */}
                <div style={{ background: 'linear-gradient(135deg, var(--primary) 0%, #6366f1 50%, #3b82f6 100%)', padding: '32px', borderRadius: '24px', color: 'white', position: 'relative', overflow: 'hidden', boxShadow: 'var(--shadow-primary)' }}>
                  <Activity size={130} style={{ position: 'absolute', right: '-20px', bottom: '-25px', opacity: 0.08 }} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px', opacity: 0.85 }}>
                    <Zap size={16} /> <span style={{ fontSize: '12px', fontWeight: '800', letterSpacing: '1.5px', textTransform: 'uppercase' }}>AI Health Score</span>
                  </div>
                  {healthData ? (
                    <>
                      <div style={{ fontSize: '82px', fontWeight: '900', lineHeight: '1', letterSpacing: '-3px' }}>{healthData.health_score}</div>
                      <div style={{ fontSize: '13px', opacity: 0.7, marginTop: '4px', fontWeight: '600' }}>out of 100</div>
                      <div style={{ display: 'flex', gap: '10px', marginTop: '20px', flexWrap: 'wrap' }}>
                        <span style={{ background: 'rgba(255,255,255,0.18)', padding: '7px 14px', borderRadius: '20px', fontSize: '12px', fontWeight: '700', backdropFilter: 'blur(4px)' }}>
                          Risk: {healthData.risk_score}
                        </span>
                        <span style={{ background: 'rgba(255,255,255,0.18)', padding: '7px 14px', borderRadius: '20px', fontSize: '12px', fontWeight: '700', backdropFilter: 'blur(4px)' }}>
                          Premium: ₹{healthData.premium}
                        </span>
                      </div>
                    </>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px' }}>
                      <div style={{ width: '48px', height: '48px', borderRadius: '50%', border: '3px solid rgba(255,255,255,0.3)', borderTopColor: 'white', animation: 'spin 1s linear infinite' }} />
                      <span style={{ opacity: 0.7, fontSize: '14px' }}>Analyzing your data…</span>
                    </div>
                  )}
                </div>

                {/* Profile stats */}
                <div style={s.card}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px' }}>
                    <User size={18} color="var(--primary)" />
                    <span style={{ fontWeight: '800', fontSize: '15px', color: 'var(--text-main)' }}>Personal Profile</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                    {[
                      { label: 'Age', val: `${liveUser.age} yrs` },
                      { label: 'Weight', val: `${liveUser.weight} kg` },
                      { label: 'Height', val: `${liveUser.height} cm` },
                      { label: 'Patient ID', val: liveUser.id },
                    ].map(({ label, val }) => (
                      <div key={label} style={{ background: 'var(--bg-body)', padding: '12px', borderRadius: '12px', border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: '10px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>{label}</div>
                        <div style={{ fontWeight: '800', fontSize: '17px', color: 'var(--text-main)' }}>{val}</div>
                      </div>
                    ))}
                  </div>
                  {/* BMI bar */}
                  <div style={{ padding: '14px', background: 'var(--bg-body)', borderRadius: '12px', border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-muted)' }}>BMI</span>
                      <span style={{ fontSize: '16px', fontWeight: '900', color: bmiColor }}>{bmi} <span style={{ fontSize: '12px' }}>· {bmiStatus}</span></span>
                    </div>
                    <div style={{ width: '100%', height: '6px', background: 'var(--border)', borderRadius: '99px', overflow: 'hidden' }}>
                      <motion.div initial={{ width: 0 }} animate={{ width: `${Math.min((bmi / 40) * 100, 100)}%` }} transition={{ duration: 1, ease: 'easeOut' }}
                        style={{ height: '100%', background: bmiColor, borderRadius: '99px' }} />
                    </div>
                  </div>
                </div>

                {/* Appointments widget */}
                <div style={s.card}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px' }}>
                    <Calendar size={18} color="var(--primary)" />
                    <span style={{ fontWeight: '800', fontSize: '15px', color: 'var(--text-main)' }}>Appointment Status</span>
                  </div>
                  {appointments.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {[...appointments].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 4).map((apt, i) => {
                        const S = { Completed: ['var(--success)', 'var(--success-light)'], Cancelled: ['var(--danger)', 'var(--danger-light)'], Rescheduled: ['var(--warning)', 'var(--warning-light)'] };
                        const [c, bg] = S[apt.status] || ['var(--primary)', 'var(--primary-light)'];
                        return (
                          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '13px 16px', background: 'var(--bg-body)', borderRadius: '12px', border: '1px solid var(--border)' }}>
                            <div>
                              <div style={{ fontWeight: '700', color: 'var(--text-main)', fontSize: '14px' }}>{apt.doctorName}</div>
                               <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>{formatDate(apt.date)} · {apt.time}</div>
                            </div>
                            <span style={{ background: bg, color: c, padding: '5px 12px', borderRadius: '99px', fontSize: '11px', fontWeight: '800' }}>{apt.status || 'Upcoming'}</span>
                          </div>
                        );
                      })}
                    </div>
                  ) : <p style={{ fontSize: '14px', color: 'var(--text-muted)', margin: 0, textAlign: 'center', padding: '20px', border: '1px dashed var(--border)', borderRadius: '12px' }}>No appointments on record.</p>}
                </div>
              </div>

              {/* ── RIGHT COLUMN ── */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                {/* Prescriptions */}
                <div style={{ ...s.card, borderTop: '4px solid var(--primary)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px' }}>
                    <Pill size={18} color="var(--primary)" />
                    <span style={{ fontWeight: '800', fontSize: '15px', color: 'var(--text-main)' }}>My Prescriptions</span>
                    {liveUser.prescriptions?.length > 0 && <span style={{ marginLeft: 'auto', background: 'var(--primary-light)', color: 'var(--primary)', padding: '3px 10px', borderRadius: '99px', fontSize: '11px', fontWeight: '800' }}>{liveUser.prescriptions.length}</span>}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {liveUser.prescriptions?.length > 0
                      ? liveUser.prescriptions.map((rx, i) => {
                        const isRevoked = rx.status === 'REVOKED';
                        const isDispensed = rx.status === 'DISPENSED' || rx.dispensedDate;
                        const statusColor = isRevoked ? 'var(--danger, #ef4444)' : isDispensed ? 'var(--success, #10b981)' : 'var(--primary)';
                        const statusBg = isRevoked ? 'rgba(239,68,68,0.12)' : isDispensed ? 'rgba(16,185,129,0.12)' : 'var(--primary-light)';
                        const statusLabel = isRevoked ? 'Revoked by Doctor' : isDispensed ? 'Dispensed' : 'Active';
                        return (
                          <div key={i} style={{ padding: '16px', background: 'var(--bg-body)', borderRadius: '14px', border: '1px solid var(--border)', borderLeft: `4px solid ${statusColor}`, opacity: isRevoked ? 0.7 : 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                              <div style={{ fontWeight: '800', color: 'var(--text-main)', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px', textDecoration: isRevoked ? 'line-through' : 'none' }}>
                                <Pill size={15} color={statusColor} /> {rx.medicine}
                              </div>
                              <span style={{ padding: '3px 10px', borderRadius: '99px', fontSize: '10px', fontWeight: '800', background: statusBg, color: statusColor }}>{statusLabel}</span>
                            </div>
                            <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                              {rx.frequency && <span><strong>Freq:</strong> {rx.frequency}</span>}
                              {rx.duration && <span><strong>Dur:</strong> {rx.duration}</span>}
                            </div>
                            {rx.remarks && <div style={{ fontSize: '12px', color: isRevoked ? 'var(--danger, #ef4444)' : 'var(--warning)', marginTop: '10px', background: isRevoked ? 'rgba(239,68,68,0.08)' : 'var(--warning-light)', padding: '8px 12px', borderRadius: '8px' }}>{isRevoked ? '⚠ This prescription has been revoked by your doctor.' : `Note: ${rx.remarks}`}</div>}
                          </div>
                        );
                      })
                      : <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', border: '1px dashed var(--border)', borderRadius: '12px', fontSize: '14px' }}>No prescriptions yet.</div>
                    }
                  </div>
                </div>

                {/* Lab / Scan requests */}
                <div style={{ ...s.card, borderTop: '4px solid var(--warning)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px' }}>
                    <Syringe size={18} color="var(--warning)" />
                    <span style={{ fontWeight: '800', fontSize: '15px', color: 'var(--text-main)' }}>Required Tests & Scans</span>
                    {liveUser.scanRequests?.filter(s => s.status !== 'Completed').length > 0 && (
                      <span style={{ marginLeft: 'auto', background: 'var(--warning-light)', color: 'var(--warning)', padding: '3px 10px', borderRadius: '99px', fontSize: '11px', fontWeight: '800' }}>
                        {liveUser.scanRequests.filter(s => s.status !== 'Completed').length} Pending
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {liveUser.scanRequests?.length > 0
                      ? liveUser.scanRequests.map((scan, i) => {
                        const isDone = scan.status === 'Completed';
                        return (
                          <div key={i} style={{ padding: '14px 16px', background: 'var(--bg-body)', borderRadius: '14px', border: '1px solid var(--border)', borderLeft: `4px solid ${isDone ? 'var(--success)' : scan.priority === 'STAT (Immediate)' ? 'var(--danger)' : 'var(--warning)'}`, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div>
                              <div style={{ fontWeight: '800', color: 'var(--text-main)', fontSize: '15px' }}>{scan.scanType}</div>
                              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>By {scan.doctorName} · {scan.date}</div>
                              {scan.notes && <div style={{ fontSize: '12px', color: 'var(--text-main)', marginTop: '8px', background: 'var(--bg-surface)', padding: '7px 10px', borderRadius: '8px', border: '1px solid var(--border)' }}>{scan.notes}</div>}
                            </div>
                            <span style={{ background: isDone ? 'var(--success-light)' : 'var(--warning-light)', color: isDone ? 'var(--success)' : 'var(--warning)', padding: '4px 10px', borderRadius: '99px', fontSize: '11px', fontWeight: '800', flexShrink: 0, marginLeft: '12px' }}>
                              {isDone ? '✓ Done' : scan.priority}
                            </span>
                          </div>
                        );
                      })
                      : <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', border: '1px dashed var(--border)', borderRadius: '12px', fontSize: '14px' }}>All clear — no tests required. ✓</div>
                    }
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        } />

        {/* ══════════════════════════════════════════════
            ROUTE 2 — MEDICAL TEAM
        ══════════════════════════════════════════════ */}
        <Route path="/team" element={
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} style={s.page}>
            <div style={{ ...s.pageHeader, marginBottom: '24px' }}>
              <div>
                <h2 style={s.pageTitle}>Your Medical Team</h2>
                <p style={s.pageSub}>Book appointments with your care providers.</p>
              </div>
              <div style={{ position: 'relative' }}>
                <Search size={16} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input style={{ ...s.input, paddingLeft: '40px', width: '260px' }} placeholder="Search doctor, speciality…" value={docSearch} onChange={e => setDocSearch(e.target.value)} />
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {filteredTeam.length > 0 ? filteredTeam.map((doc, i) => {
                const isFav = liveUser.favoriteDoctors?.includes(doc.id);
                const isBooking = bookingDocId === doc.id;
                return (
                  <div key={i} style={{ ...s.card, padding: '22px 26px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <div style={{ width: '52px', height: '52px', borderRadius: '16px', background: 'var(--primary-light)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          <Stethoscope size={24} />
                        </div>
                        <div>
                          <div style={{ fontWeight: '800', fontSize: '16px', color: 'var(--text-main)' }}>{doc.name}</div>
                          <div style={{ fontSize: '13px', color: 'var(--primary)', fontWeight: '700', marginTop: '2px' }}>{doc.speciality}</div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-muted)', fontSize: '12px', marginTop: '4px' }}><MapPin size={12} /> {doc.hospital}</div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <button onClick={() => toggleFavorite(doc.id)} style={{ background: isFav ? 'var(--warning-light)' : 'var(--bg-body)', border: `1px solid ${isFav ? 'var(--warning)' : 'var(--border)'}`, borderRadius: '10px', padding: '9px', cursor: 'pointer', color: isFav ? 'var(--warning)' : 'var(--text-muted)', display: 'flex' }}>
                          <Star fill={isFav ? 'var(--warning)' : 'none'} size={18} />
                        </button>
                        {!isBooking && (
                          <button onClick={() => setBookingDocId(doc.id)} style={{ display: 'flex', alignItems: 'center', gap: '7px', padding: '10px 18px', background: 'var(--primary)', color: 'white', border: 'none', borderRadius: '12px', fontWeight: '700', cursor: 'pointer', fontSize: '13px' }}>
                            <Calendar size={15} /> Book
                          </button>
                        )}
                      </div>
                    </div>

                    <AnimatePresence>
                      {isBooking && (
                        <motion.div initial={{ height: 0, opacity: 0, marginTop: 0 }} animate={{ height: 'auto', opacity: 1, marginTop: 18 }} exit={{ height: 0, opacity: 0, marginTop: 0 }} style={{ overflow: 'hidden' }}>
                          <div style={{ background: 'var(--bg-body)', padding: '20px', borderRadius: '14px', border: '1px solid var(--border)' }}>
                            <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-main)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}><Clock size={14} color="var(--primary)" /> Book Appointment with {doc.name}</div>

                            {/* Date Picker */}
                            <div style={{ marginBottom: '16px' }}>
                              <label style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '8px' }}>Select Date</label>
                              <input
                                type="date"
                                value={apptForm.date}
                                min={getTodayDate()}
                                onChange={e => setApptForm({ ...apptForm, date: e.target.value, time: '' })}
                                style={{ width: '100%', padding: '11px 14px', borderRadius: '12px', border: apptForm.date ? '1.5px solid var(--primary)' : '1px solid var(--border)', background: 'var(--bg-surface)', color: 'var(--text-main)', fontSize: '14px', outline: 'none', boxSizing: 'border-box', colorScheme: 'dark' }}
                              />
                            </div>

                            {/* Time Slot Grid */}
                            {apptForm.date && (() => {
                              const today = getTodayDate();
                              const isToday = apptForm.date === today;
                              const now = new Date();
                              // current time as "HH:MM" — add 30 min buffer
                              const bufferMs = now.getTime() + 30 * 60000;
                              const bufDate = new Date(bufferMs);
                              const nowHHMM = `${String(bufDate.getHours()).padStart(2,'0')}:${String(bufDate.getMinutes()).padStart(2,'0')}`;
                              const availableSlots = TIME_SLOTS.filter(s => !isToday || s >= nowHHMM);
                              const pastCount = TIME_SLOTS.length - availableSlots.length;

                              return (
                                <div style={{ marginBottom: '16px' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                                    <label style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Select Time Slot</label>
                                    {isToday && pastCount > 0 && (
                                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                        {pastCount} past slot{pastCount > 1 ? 's' : ''} hidden
                                      </span>
                                    )}
                                  </div>
                                  {availableSlots.length === 0 ? (
                                    <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px', border: '1px dashed var(--border)', borderRadius: '10px' }}>
                                      No slots available for today. Please select a future date.
                                    </div>
                                  ) : (
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '7px' }}>
                                      {availableSlots.map(slot => {
                                        const selected = apptForm.time === slot;
                                        return (
                                          <button
                                            key={slot}
                                            onClick={() => setApptForm({ ...apptForm, time: slot })}
                                            style={{
                                              padding: '9px 4px',
                                              border: selected ? '1.5px solid var(--primary)' : '1px solid var(--border)',
                                              borderRadius: '9px',
                                              background: selected ? 'var(--primary)' : 'var(--bg-surface)',
                                              color: selected ? 'white' : 'var(--text-main)',
                                              fontWeight: selected ? '800' : '500',
                                              fontSize: '12px',
                                              cursor: 'pointer',
                                              transition: '0.15s',
                                              fontFamily: 'inherit'
                                            }}
                                          >{slot}</button>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                              );
                            })()}

                            <div style={{ display: 'flex', gap: '10px' }}>
                              <button onClick={() => handleBook(doc)} disabled={!apptForm.date || !apptForm.time} style={{ flex: 1, padding: '12px', background: (!apptForm.date || !apptForm.time) ? 'var(--text-muted)' : 'var(--primary)', color: 'white', border: 'none', borderRadius: '10px', fontWeight: '700', cursor: (!apptForm.date || !apptForm.time) ? 'default' : 'pointer', fontSize: '14px' }}>Confirm Booking</button>
                              <button onClick={() => { setBookingDocId(null); setApptForm({ date: '', time: '' }); }} style={{ flex: 1, padding: '12px', background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '10px', fontWeight: '700', cursor: 'pointer' }}>Cancel</button>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              }) : <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px', background: 'var(--bg-surface)', border: '1px dashed var(--border)', borderRadius: '16px' }}>No doctors match your search.</p>}
            </div>
          </motion.div>
        } />

        {/* ══════════════════════════════════════════════
            ROUTE 3 — MEDICAL VAULT
        ══════════════════════════════════════════════ */}
        <Route path="/vault" element={
          <VaultView
            liveUser={liveUser}
            uploading={uploading}
            selectedFile={selectedFile}
            setSelectedFile={setSelectedFile}
            handleFileUpload={handleFileUpload}
            vaultCategory={vaultCategory}
            setVaultCategory={setVaultCategory}
            s={s}
          />
        } />

        {/* ══════════════════════════════════════════════
            ROUTE 4 — AI CHATBOT
        ══════════════════════════════════════════════ */}
        <Route path="/chat" element={
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} style={{ padding: '28px 36px', maxWidth: '900px', margin: '0 auto', height: 'calc(100vh - 80px)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '20px' }}>
              <div style={{ background: 'linear-gradient(135deg, var(--primary), #3b82f6)', padding: '12px', borderRadius: '16px', color: 'white', boxShadow: 'var(--shadow-primary)' }}><Bot size={26} /></div>
              <div>
                <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '22px', fontWeight: '900' }}>AI Health Assistant</h2>
                <p style={{ color: 'var(--text-muted)', margin: 0, fontSize: '12px', fontWeight: '600' }}>Powered by Groq · Llama 3.3 70B · Health-only mode</p>
              </div>
            </div>

            <div style={{ flex: 1, background: 'var(--bg-surface)', borderRadius: '24px', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ flex: 1, overflowY: 'auto', padding: '28px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
                {messages.map((msg, idx) => (
                  <div key={idx} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '75%' }}>
                    <div style={{ background: msg.role === 'user' ? 'linear-gradient(135deg, var(--primary), #3b82f6)' : 'var(--bg-body)', color: msg.role === 'user' ? 'white' : 'var(--text-main)', padding: '14px 18px', borderRadius: '20px', borderBottomRightRadius: msg.role === 'user' ? '4px' : '20px', borderBottomLeftRadius: msg.role === 'assistant' ? '4px' : '20px', fontSize: '14px', lineHeight: '1.6', border: msg.role === 'assistant' ? '1px solid var(--border)' : 'none', boxShadow: msg.role === 'user' ? 'var(--shadow-primary)' : 'var(--shadow-xs)' }}>
                      {msg.content}
                    </div>
                  </div>
                ))}
                {isChatLoading && (
                  <div style={{ alignSelf: 'flex-start', background: 'var(--bg-body)', padding: '14px 18px', borderRadius: '20px', borderBottomLeftRadius: '4px', color: 'var(--text-muted)', border: '1px solid var(--border)', fontSize: '14px', display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: 'var(--text-muted)', animation: 'pulse 1s infinite' }} />
                    <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: 'var(--text-muted)', animation: 'pulse 1s 0.2s infinite' }} />
                    <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: 'var(--text-muted)', animation: 'pulse 1s 0.4s infinite' }} />
                  </div>
                )}
                <div ref={endOfMessagesRef} />
              </div>

              <div style={{ padding: '18px 22px', borderTop: '1px solid var(--border)', background: 'var(--bg-body)', display: 'flex', gap: '12px' }}>
                <input
                  style={{ flex: 1, padding: '14px 18px', borderRadius: '14px', border: '1px solid var(--border)', background: 'var(--bg-surface)', color: 'var(--text-main)', fontSize: '14px', outline: 'none', fontFamily: 'inherit' }}
                  placeholder="Ask about symptoms, medications, nutrition…"
                  value={chatInput} onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendMessage()}
                />
                <button onClick={sendMessage} disabled={isChatLoading || !chatInput.trim()}
                  style={{ padding: '0 20px', background: chatInput.trim() ? 'linear-gradient(135deg, var(--primary), #3b82f6)' : 'var(--border)', color: 'white', border: 'none', borderRadius: '14px', cursor: chatInput.trim() ? 'pointer' : 'default', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: chatInput.trim() ? 'var(--shadow-primary)' : 'none', transition: '0.2s' }}>
                  <Send size={18} />
                </button>
              </div>
            </div>
          </motion.div>
        } />
      </Routes>
    </>
  );
}

// ════════════════════════════════════════════════
// VAULT VIEW COMPONENT — categorised file sections
// ════════════════════════════════════════════════
const VAULT_SECTIONS = [
  { key: 'Test Report', label: 'Test Reports', Icon: Syringe, color: 'var(--primary)', bg: 'var(--primary-light)', desc: 'Blood tests, urine analysis, lab results' },
  { key: 'Scan', label: 'Scans & Imaging', Icon: ScanLine, color: 'var(--warning)', bg: 'var(--warning-light)', desc: 'X-rays, MRIs, CT scans, ultrasounds' },
  { key: 'Medical Summary', label: 'Medical Summary Reports', Icon: ClipboardList, color: 'var(--success)', bg: 'var(--success-light)', desc: 'Discharge notes, prescriptions, general docs' },
];

function VaultView({ liveUser, uploading, selectedFile, setSelectedFile, handleFileUpload, vaultCategory, setVaultCategory, s }) {
  const files = liveUser.medicalFiles || [];

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} style={s.page}>
      <div style={{ marginBottom: '28px' }}>
        <h2 style={s.pageTitle}>Medical Vault</h2>
        <p style={s.pageSub}>Your IPFS-secured health record repository.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '24px', alignItems: 'start' }}>
        {/* Upload panel */}
        <div style={{ ...s.card, padding: '24px' }}>
          <h3 style={{ margin: '0 0 18px', color: 'var(--text-main)', fontSize: '16px', fontWeight: '800' }}>Upload Document</h3>

          <label style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '8px' }}>Document Type</label>
          <select value={vaultCategory} onChange={e => setVaultCategory(e.target.value)}
            style={{ ...s.input, marginBottom: '16px', cursor: 'pointer' }}>
            <option value="Test Report">Test Report</option>
            <option value="Scan">Scan / Imaging</option>
            <option value="Medical Summary">Medical Summary</option>
          </select>

          <label htmlFor="file-upload" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '28px 16px', border: '2px dashed var(--primary)', borderRadius: '14px', background: 'var(--primary-light)', cursor: uploading ? 'wait' : 'pointer', opacity: uploading ? 0.7 : 1, marginBottom: '14px' }}>
            <UploadCloud size={30} color="var(--primary)" style={{ marginBottom: '10px' }} />
            <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--primary)', textAlign: 'center' }}>{selectedFile ? selectedFile.name : 'Click to select file'}</span>
            <input id="file-upload" type="file" style={{ display: 'none' }} onChange={e => setSelectedFile(e.target.files[0])} disabled={uploading} />
          </label>

          <button disabled={uploading || !selectedFile} onClick={handleFileUpload}
            style={{ width: '100%', padding: '13px', background: (!selectedFile || uploading) ? 'var(--text-muted)' : 'var(--primary)', color: 'white', border: 'none', borderRadius: '12px', cursor: (!selectedFile || uploading) ? 'not-allowed' : 'pointer', fontWeight: '800', fontSize: '14px' }}>
            {uploading ? 'Encrypting & Uploading…' : 'Secure Upload'}
          </button>
        </div>

        {/* File sections */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {VAULT_SECTIONS.map(({ key, label, Icon, color, bg, desc }) => {
            const sectionFiles = files.filter(f => (f.category || 'Medical Summary') === key);
            return (
              <div key={key} style={{ background: 'var(--bg-surface)', borderRadius: '22px', border: '1px solid var(--border)', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px', padding: '18px 24px', background: bg, borderBottom: sectionFiles.length > 0 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'var(--bg-surface)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: 'var(--shadow-xs)' }}>
                    <Icon size={20} color={color} />
                  </div>
                  <div>
                    <div style={{ fontWeight: '800', color: 'var(--text-main)', fontSize: '15px' }}>{label}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{desc}</div>
                  </div>
                  <span style={{ marginLeft: 'auto', background: 'var(--bg-surface)', color, padding: '4px 12px', borderRadius: '99px', fontSize: '12px', fontWeight: '800', flexShrink: 0, boxShadow: 'var(--shadow-xs)' }}>
                    {sectionFiles.length} {sectionFiles.length === 1 ? 'file' : 'files'}
                  </span>
                </div>
                {sectionFiles.length > 0 ? (
                  <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {sectionFiles.map((file, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: 'var(--bg-body)', borderRadius: '12px', border: '1px solid var(--border)' }}>
                        <div>
                          <div style={{ fontWeight: '700', color: 'var(--text-main)', fontSize: '14px' }}>{file.name}</div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>{file.date}</div>
                        </div>
                        <a href={`https://gateway.pinata.cloud/ipfs/${file.hash}`} target="_blank" rel="noreferrer"
                          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', background: 'var(--primary)', color: 'white', borderRadius: '10px', textDecoration: 'none', fontWeight: '700', fontSize: '13px', whiteSpace: 'nowrap' }}>
                          <FileCheck size={14} /> View
                        </a>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ padding: '22px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>No {label.toLowerCase()} uploaded yet.</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}

const s = {
  page: { padding: '36px 40px', maxWidth: '1200px', margin: '0 auto' },
  pageHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '16px' },
  pageTitle: { margin: 0, fontSize: '26px', fontWeight: '900', color: 'var(--text-main)', letterSpacing: '-0.5px' },
  pageSub: { margin: '5px 0 0', color: 'var(--text-muted)', fontSize: '14px' },
  card: { background: 'var(--bg-surface)', padding: '26px', borderRadius: '22px', boxShadow: 'var(--shadow-sm)', border: '1px solid var(--border)' },
  input: { width: '100%', padding: '12px 14px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--input-bg)', color: 'var(--text-main)', fontSize: '14px', fontFamily: 'inherit', boxSizing: 'border-box', outline: 'none' },
  dateInput: { flex: 1, padding: '12px 14px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--bg-surface)', color: 'var(--text-main)', fontSize: '14px', outline: 'none', colorScheme: 'dark', fontFamily: 'inherit' },
};