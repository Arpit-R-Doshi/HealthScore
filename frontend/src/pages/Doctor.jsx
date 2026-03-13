import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, UserPlus, UploadCloud, FileCheck, FolderOpen, Edit, Save, X,
  Calendar, CheckCircle2, Clock, XCircle, FilePlus, AlertCircle,
  Syringe, ChevronDown, ChevronUp, History, User, Stethoscope,
  AlertTriangle, ArrowRight, Activity, Pill, Ban
} from 'lucide-react';

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

const PRIORITY_COLOR = { 'Routine': 'var(--success)', 'Urgent': 'var(--warning)', 'STAT (Immediate)': 'var(--danger)' };

export default function Doctor({ user }) {
  const navigate = useNavigate();
  const location = useLocation();

  const [alertConfig, setAlertConfig] = useState({ isOpen: false, title: '', message: '', type: 'success' });
  const showAlert = (title, message, type = 'success') => setAlertConfig({ isOpen: true, title, message, type });
  const closeAlert = () => setAlertConfig(a => ({ ...a, isOpen: false }));

  const CustomAlert = () => (
    <AnimatePresence>
      {alertConfig.isOpen && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(6px)' }}>
          <motion.div initial={{ scale: 0.9, y: 24 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.92, y: 12 }}
            style={{ background: 'var(--bg-surface)', padding: '36px', borderRadius: '28px', width: '90%', maxWidth: '400px', border: '1px solid var(--border)', boxShadow: 'var(--shadow-md)', textAlign: 'center', position: 'relative' }}>
            <button onClick={closeAlert} style={s.iconClose}><X size={18} /></button>
            <div style={{ display: 'inline-flex', marginBottom: '18px', background: alertConfig.type === 'error' ? 'var(--danger-light)' : 'var(--success-light)', padding: '16px', borderRadius: '50%' }}>
              {alertConfig.type === 'error' ? <AlertCircle color="var(--danger)" size={38} /> : <CheckCircle2 color="var(--success)" size={38} />}
            </div>
            <h3 style={{ margin: '0 0 10px', color: 'var(--text-main)', fontSize: '20px', fontWeight: '800' }}>{alertConfig.title}</h3>
            <p style={{ color: 'var(--text-muted)', margin: '0 0 28px', lineHeight: '1.6', fontSize: '14px' }}>{alertConfig.message}</p>
            <button onClick={closeAlert} style={{ ...s.btn, width: '100%', justifyContent: 'center', background: alertConfig.type === 'error' ? 'var(--danger)' : 'var(--success)', fontSize: '15px', padding: '14px' }}>Got it</button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  const getGreeting = () => {
    const h = new Date().getHours();
    return h < 12 ? 'Good Morning' : h < 18 ? 'Good Afternoon' : 'Good Evening';
  };

  // Strip any leading "Dr." or "Dr" prefix so we don't double up
  const doctorFirstName = user.name
    .replace(/^Dr\.?\s*/i, '')
    .split(' ')[0];

  // ════════════════════════════════════════════════
  // VIEW 1 — PATIENT LOOKUP
  // ════════════════════════════════════════════════
  const DashboardView = () => {
    const initialId = location.state?.patientId || '';
    const [patientId, setPatientId] = useState(initialId);
    const [patientData, setPatientData] = useState(null);
    const [rxForm, setRxForm] = useState({ medicine: '', frequency: '', duration: '', remarks: '' });
    const [file, setFile] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState({ weight: '', history: '' });
    const [scanForm, setScanForm] = useState({ scanType: 'Blood Test', priority: 'Routine', notes: '' });
    const [isScanOpen, setIsScanOpen] = useState(false);
    const [isScanSubmitting, setIsScanSubmitting] = useState(false);
    const [loading, setLoading] = useState(false);
    const [revoking, setRevoking] = useState(null);

    useEffect(() => { if (initialId) fetchPatient(initialId); }, []);

    const fetchPatient = async (id = patientId) => {
      if (!id) return;
      setLoading(true);
      try {
        const res = await axios.get(`http://localhost:5001/api/patient/${id}?role=Doctor`);
        setPatientData(res.data);
        setEditForm({ weight: res.data.weight, history: res.data.history });
        setIsScanOpen(false);
      } catch { showAlert('Not Found', 'No patient found with that ID.', 'error'); setPatientData(null); }
      setLoading(false);
    };

    const updatePatient = async () => {
      try {
        await axios.post('http://localhost:5001/api/patient/update', { id: patientId, weight: editForm.weight, history: editForm.history });
        showAlert('Updated', 'Patient record saved successfully.');
        setIsEditing(false); fetchPatient();
      } catch { showAlert('Error', 'Update failed.', 'error'); }
    };

    const issuePrescription = async () => {
      if (!rxForm.medicine) return showAlert('Missing', 'Enter the medicine name.', 'error');
      setIsUploading(true);
      try {
        let ipfsHash = '';
        if (file) { const fd = new FormData(); fd.append('file', file); const r = await axios.post('http://localhost:5001/api/upload', fd); ipfsHash = r.data.ipfsHash; }
        await axios.post('http://localhost:5001/api/prescription', { ...rxForm, patientId, ipfsHash });
        showAlert('Prescription Issued', 'Secured on the blockchain ledger.');
        setRxForm({ medicine: '', frequency: '', duration: '', remarks: '' }); setFile(null);
        fetchPatient();
      } catch { showAlert('Error', 'Could not issue prescription.', 'error'); }
      setIsUploading(false);
    };

    const revokePrescription = async (rxId) => {
      setRevoking(rxId);
      try {
        await axios.post('http://localhost:5001/api/prescription/revoke', { rxId, patientId, reason: 'Revoked by doctor' });
        showAlert('Revoked', `Prescription ${rxId} has been revoked on the blockchain.`);
        fetchPatient();
      } catch (e) { showAlert('Error', e.response?.data?.error || 'Revoke failed.', 'error'); }
      setRevoking(null);
    };

    const submitScan = async () => {
      setIsScanSubmitting(true);
      try {
        await axios.post('http://localhost:5001/api/doctor/request-scan', { ...scanForm, patientId, doctorId: user.id, doctorName: user.name });
        showAlert('Request Sent', 'Lab order added to the patient record.');
        setScanForm({ scanType: 'Blood Test', priority: 'Routine', notes: '' }); setIsScanOpen(false);
      } catch { showAlert('Error', 'Could not send lab request.', 'error'); }
      setIsScanSubmitting(false);
    };

    return (
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} style={s.page}>
        {/* ── Page header ── */}
        <div style={s.pageHeader}>
          <div>
            <h2 style={s.pageTitle}>{getGreeting()}, Dr. {doctorFirstName}</h2>
            <p style={s.pageSub}>Search a patient to view their record and issue prescriptions.</p>
          </div>
        </div>

        {/* ── Search hero ── */}
        <div style={{ background: 'linear-gradient(135deg, var(--primary) 0%, #3b82f6 100%)', borderRadius: '24px', padding: '28px 30px', marginBottom: '28px', position: 'relative', overflow: 'hidden', boxShadow: 'var(--shadow-primary)' }}>
          <Activity size={110} style={{ position: 'absolute', right: '-15px', bottom: '-20px', opacity: 0.07, color: 'white' }} />
          <h3 style={{ color: 'white', margin: '0 0 6px 0', fontWeight: '800', fontSize: '17px', display: 'flex', alignItems: 'center', gap: '8px' }}><Search size={18} /> Patient Lookup</h3>
          <p style={{ color: 'rgba(255,255,255,0.65)', margin: '0 0 18px 0', fontSize: '13px' }}>Enter or paste a patient ID and press Enter or click Search.</p>
          <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <User size={16} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,0.5)' }} />
              <input
                style={{ width: '100%', padding: '13px 16px 13px 44px', borderRadius: '14px', border: '2px solid rgba(255,255,255,0.25)', background: 'rgba(255,255,255,0.14)', color: 'white', fontSize: '15px', backdropFilter: 'blur(8px)', boxSizing: 'border-box', fontFamily: 'inherit' }}
                className="gradient-input"
                placeholder="e.g. PT-1000"
                value={patientId}
                onChange={e => setPatientId(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && fetchPatient()}
              />
            </div>
            <button onClick={() => fetchPatient()} disabled={loading}
              style={{ padding: '0 26px', background: 'white', color: 'var(--primary)', border: 'none', borderRadius: '14px', fontWeight: '800', fontSize: '14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '7px', whiteSpace: 'nowrap', boxShadow: '0 4px 15px rgba(0,0,0,0.15)' }}>
              <Search size={16} /> {loading ? 'Searching…' : 'Search'}
            </button>
          </div>
        </div>

        {patientData && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
            {/* LEFT column */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

              {/* Patient card */}
              <div style={s.card}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                  <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
                    <div style={{ width: '52px', height: '52px', borderRadius: '16px', background: 'var(--primary-light)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '900', fontSize: '22px' }}>{patientData.name?.charAt(0)}</div>
                    <div>
                      <div style={{ fontWeight: '800', fontSize: '18px', color: 'var(--text-main)' }}>{patientData.name}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>Age {patientData.age} · {patientData.weight} kg</div>
                    </div>
                  </div>
                  {!isEditing
                    ? <button onClick={() => setIsEditing(true)} style={{ ...s.iconBtn, color: 'var(--primary)', background: 'var(--primary-light)' }}><Edit size={16} /></button>
                    : <div style={{ display: 'flex', gap: '6px' }}>
                      <button onClick={updatePatient} style={{ ...s.iconBtn, color: 'var(--success)', background: 'var(--success-light)' }}><Save size={16} /></button>
                      <button onClick={() => setIsEditing(false)} style={{ ...s.iconBtn, color: 'var(--danger)', background: 'var(--danger-light)' }}><X size={16} /></button>
                    </div>
                  }
                </div>

                {isEditing ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div><label style={s.label}>Weight (kg)</label><input style={s.input} type="number" value={editForm.weight} onChange={e => setEditForm({ ...editForm, weight: e.target.value })} /></div>
                    <div><label style={s.label}>Medical History</label><input style={s.input} value={editForm.history} onChange={e => setEditForm({ ...editForm, history: e.target.value })} /></div>
                  </div>
                ) : (
                  <div style={{ padding: '16px', background: 'var(--bg-body)', borderRadius: '14px', border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}><span style={s.statLabel}>History</span></div>
                    <p style={{ margin: 0, color: 'var(--text-main)', fontSize: '14px', lineHeight: '1.6' }}>{patientData.history || 'No medical history recorded.'}</p>
                  </div>
                )}

                {/* Patient Vault */}
                <div style={{ marginTop: '20px', paddingTop: '20px', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                    <FolderOpen size={16} color="var(--primary)" />
                    <span style={{ fontWeight: '700', fontSize: '14px', color: 'var(--text-main)' }}>Medical Vault</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {patientData.medicalFiles?.length > 0
                      ? patientData.medicalFiles.map((f, i) => (
                        <a key={i} href={`https://gateway.pinata.cloud/ipfs/${f.hash}`} target="_blank" rel="noreferrer"
                          style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '11px 14px', background: 'var(--primary-light)', borderRadius: '12px', color: 'var(--primary)', textDecoration: 'none', fontSize: '13px', fontWeight: '600' }}>
                          <FileCheck size={15} /> {f.name}
                          <span style={{ marginLeft: 'auto', fontSize: '11px', opacity: 0.7 }}>{f.category || ''}</span>
                        </a>
                      ))
                      : <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0, padding: '12px', background: 'var(--bg-body)', borderRadius: '10px', border: '1px dashed var(--border)', textAlign: 'center' }}>No files in vault.</p>
                    }
                  </div>
                </div>
              </div>

              {/* Scan request — collapsible */}
              <div style={{ ...s.card, padding: 0, overflow: 'hidden' }}>
                <button onClick={() => setIsScanOpen(v => !v)}
                  style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 24px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-main)' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '10px', fontWeight: '800', fontSize: '15px' }}>
                    <Syringe size={18} color="var(--warning)" /> Request Lab / Scan
                  </span>
                  {isScanOpen ? <ChevronUp size={17} color="var(--text-muted)" /> : <ChevronDown size={17} color="var(--text-muted)" />}
                </button>
                <AnimatePresence>
                  {isScanOpen && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: 'hidden' }}>
                      <div style={{ padding: '0 24px 24px 24px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '14px', paddingTop: '20px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                          <div><label style={s.label}>Test Type</label>
                            <select style={s.input} value={scanForm.scanType} onChange={e => setScanForm({ ...scanForm, scanType: e.target.value })}>
                              <option>Blood Test</option><option>MRI Scan</option><option>X-Ray</option><option>CT Scan</option><option>Urine Analysis</option>
                            </select>
                          </div>
                          <div><label style={s.label}>Priority</label>
                            <select style={s.input} value={scanForm.priority} onChange={e => setScanForm({ ...scanForm, priority: e.target.value })}>
                              <option>Routine</option><option>Urgent</option><option>STAT (Immediate)</option>
                            </select>
                          </div>
                        </div>
                        <div><label style={s.label}>Clinical Notes</label><textarea style={{ ...s.input, minHeight: '72px', resize: 'vertical' }} value={scanForm.notes} onChange={e => setScanForm({ ...scanForm, notes: e.target.value })} /></div>
                        <button disabled={isScanSubmitting} onClick={submitScan}
                          style={{ ...s.btn, background: isScanSubmitting ? 'var(--text-muted)' : 'var(--warning)', alignSelf: 'flex-start', padding: '11px 22px' }}>
                          {isScanSubmitting ? 'Sending…' : 'Submit Request'}
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* RIGHT column — Prescription + History */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

              {/* Issue Prescription form */}
              <div style={{ ...s.card, borderTop: '4px solid var(--primary)' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '0 0 24px', color: 'var(--text-main)', fontWeight: '800', fontSize: '17px' }}><UserPlus size={20} color="var(--primary)" /> Issue Prescription</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div><label style={s.label}>Medicine *</label><input style={s.input} value={rxForm.medicine} onChange={e => setRxForm({ ...rxForm, medicine: e.target.value })} placeholder="Drug name..." /></div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div><label style={s.label}>Frequency</label><input style={s.input} value={rxForm.frequency} onChange={e => setRxForm({ ...rxForm, frequency: e.target.value })} placeholder="e.g. Twice daily" /></div>
                    <div><label style={s.label}>Duration</label><input style={s.input} value={rxForm.duration} onChange={e => setRxForm({ ...rxForm, duration: e.target.value })} placeholder="e.g. 7 days" /></div>
                  </div>
                  <div><label style={s.label}>Remarks</label><textarea style={{ ...s.input, minHeight: '80px', resize: 'vertical' }} value={rxForm.remarks} onChange={e => setRxForm({ ...rxForm, remarks: e.target.value })} /></div>
                  <div>
                    <label style={s.label}>Attach Document (IPFS)</label>
                    <label style={{ display: 'flex', gap: '12px', alignItems: 'center', padding: '14px', background: 'var(--bg-body)', borderRadius: '12px', border: '2px dashed var(--border)', cursor: 'pointer' }}>
                      <UploadCloud size={20} color="var(--text-muted)" />
                      <span style={{ fontSize: '13px', color: file ? 'var(--text-main)' : 'var(--text-muted)', fontWeight: '600' }}>{file ? file.name : 'Click to attach a file'}</span>
                      <input type="file" style={{ display: 'none' }} onChange={e => setFile(e.target.files[0])} />
                    </label>
                  </div>
                  <button disabled={isUploading} onClick={issuePrescription}
                    style={{ ...s.btn, background: isUploading ? 'var(--text-muted)' : 'var(--primary)', justifyContent: 'center', padding: '14px', fontSize: '15px' }}>
                    <FilePlus size={18} /> {isUploading ? 'Saving to Ledger…' : 'Sign & Issue'}
                  </button>
                </div>
              </div>

              {/* Prescription History */}
              <div style={s.card}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
                  <Pill size={18} color="var(--primary)" />
                  <h3 style={{ margin: 0, fontWeight: '800', fontSize: '16px', color: 'var(--text-main)' }}>Prescriptions</h3>
                  <span style={{ marginLeft: 'auto', background: 'var(--primary-light)', color: 'var(--primary)', padding: '3px 12px', borderRadius: '99px', fontSize: '12px', fontWeight: '800' }}>{patientData.prescriptions?.length || 0}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {patientData.prescriptions?.length > 0 ? patientData.prescriptions.map((rx, i) => {
                    const statusStyles = {
                      ACTIVE:    { bg: 'var(--success-light, rgba(16,185,129,0.12))', color: 'var(--success, #10b981)', label: 'Active' },
                      DISPENSED: { bg: 'var(--primary-light)', color: 'var(--primary)', label: 'Dispensed' },
                      REVOKED:   { bg: 'var(--danger-light, rgba(239,68,68,0.12))', color: 'var(--danger, #ef4444)', label: 'Revoked' },
                    };
                    const st = statusStyles[rx.status] || statusStyles.ACTIVE;
                    const isActive = !rx.status || rx.status === 'ACTIVE';
                    return (
                      <div key={i} style={{ padding: '14px 16px', background: 'var(--bg-body)', borderRadius: '14px', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '14px' }}>
                        <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: st.bg, color: st.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          <Pill size={16} />
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: '700', fontSize: '14px', color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rx.medicine}</div>
                          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '3px' }}>
                            {rx.frequency && <span>{rx.frequency}</span>}{rx.duration && <span> · {rx.duration}</span>}
                          </div>
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: '99px', fontSize: '11px', fontWeight: '800', background: st.bg, color: st.color, flexShrink: 0 }}>{st.label}</span>
                        {isActive && (
                          <button
                            disabled={revoking === rx.id}
                            onClick={() => revokePrescription(rx.id)}
                            title="Revoke this prescription"
                            style={{ ...s.iconBtn, background: 'var(--danger-light, rgba(239,68,68,0.12))', color: 'var(--danger, #ef4444)', flexShrink: 0, opacity: revoking === rx.id ? 0.5 : 1 }}
                          >
                            <Ban size={15} />
                          </button>
                        )}
                      </div>
                    );
                  }) : (
                    <div style={{ padding: '28px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px', border: '1px dashed var(--border)', borderRadius: '12px', background: 'var(--bg-body)' }}>No prescriptions issued yet.</div>
                  )}
                </div>
              </div>

            </div>
          </div>
        )}
      </motion.div>
    );
  };

  // ════════════════════════════════════════════════
  // VIEW 2 — APPOINTMENTS
  // ════════════════════════════════════════════════
  const AppointmentsView = () => {
    const [appointments, setAppointments] = useState([]);
    const [rescheduleData, setRescheduleData] = useState(null);
    const [form, setForm] = useState({ date: '', time: '' });

    const fetch = async () => {
      try { const res = await axios.get(`http://localhost:5001/api/doctor/appointments/${user.id}`); setAppointments(res.data); } catch { }
    };
    useEffect(() => { fetch(); }, []);

    const updateStatus = async (apt, status, newDate = null, newTime = null) => {
      try {
        await axios.post('http://localhost:5001/api/doctor/appointment/update', { patientId: apt.patientId, appointmentId: apt.id, status, date: newDate, time: newTime });
        showAlert('Updated', `Appointment ${status.toLowerCase()}.`);
        setRescheduleData(null); fetch();
      } catch { showAlert('Error', 'Update failed.', 'error'); }
    };

    const active = appointments.filter(a => ['Upcoming', 'Rescheduled'].includes(a.status));
    const done = appointments.filter(a => ['Completed', 'Cancelled'].includes(a.status));

    const STATUS_STYLE = {
      Upcoming: { bg: 'var(--primary-light)', color: 'var(--primary)' },
      Rescheduled: { bg: 'var(--warning-light)', color: 'var(--warning)' },
      Completed: { bg: 'var(--success-light)', color: 'var(--success)' },
      Cancelled: { bg: 'var(--danger-light)', color: 'var(--danger)' },
    };

    const AptCard = ({ apt }) => {
      const ss = STATUS_STYLE[apt.status] || {};
      return (
        <div style={{ ...s.card, padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '20px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: '800', fontSize: '16px', color: 'var(--text-main)', marginBottom: '6px' }}>{apt.patientName}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--text-muted)', fontSize: '13px', flexWrap: 'wrap' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}><Calendar size={14} /> {formatDate(apt.date)}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}><Clock size={14} /> {apt.time}</span>
            </div>
            <span style={{ display: 'inline-block', marginTop: '10px', padding: '4px 12px', borderRadius: '99px', fontSize: '11px', fontWeight: '800', background: ss.bg, color: ss.color }}>{apt.status}</span>
          </div>
          {['Upcoming', 'Rescheduled'].includes(apt.status) && !rescheduleData && (
            <div style={{ display: 'flex', gap: '8px' }}>
              <button onClick={() => updateStatus(apt, 'Completed')} title="Complete" style={{ ...s.iconBtn, background: 'var(--success-light)', color: 'var(--success)' }}><CheckCircle2 size={17} /></button>
              <button onClick={() => setRescheduleData(apt)} title="Reschedule" style={{ ...s.iconBtn, background: 'var(--warning-light)', color: 'var(--warning)' }}><Calendar size={17} /></button>
              <button onClick={() => updateStatus(apt, 'Cancelled')} title="Cancel" style={{ ...s.iconBtn, background: 'var(--danger-light)', color: 'var(--danger)' }}><XCircle size={17} /></button>
            </div>
          )}
          {rescheduleData?.id === apt.id && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', background: 'var(--bg-body)', padding: '16px', borderRadius: '14px', border: '1px solid var(--border)', width: '100%', marginTop: '4px' }}>
              <div>
                <label style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '7px' }}>New Date</label>
                <input type="date" min={new Date().toISOString().split('T')[0]} style={{ ...s.dateInput, width: '100%', boxSizing: 'border-box', border: form.date ? '1.5px solid var(--primary)' : '1px solid var(--border)' }} onChange={e => setForm({ date: e.target.value, time: '' })} />
              </div>
              {form.date && (() => {
                const todayStr = new Date().toISOString().split('T')[0];
                const isToday = form.date === todayStr;
                const buf = new Date(Date.now() + 30 * 60000);
                const nowHHMM = `${String(buf.getHours()).padStart(2,'0')}:${String(buf.getMinutes()).padStart(2,'0')}`;
                const available = TIME_SLOTS.filter(s => !isToday || s >= nowHHMM);
                const pastCount = TIME_SLOTS.length - available.length;
                return (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <label style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>New Time Slot</label>
                      {isToday && pastCount > 0 && <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>{pastCount} past slots hidden</span>}
                    </div>
                    {available.length === 0
                      ? <div style={{ padding: '14px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px', border: '1px dashed var(--border)', borderRadius: '8px' }}>No slots available today — pick a future date.</div>
                      : <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '6px' }}>
                          {available.map(slot => {
                            const sel = form.time === slot;
                            return (
                              <button key={slot} onClick={() => setForm(f => ({ ...f, time: slot }))}
                                style={{ padding: '8px 4px', border: sel ? '1.5px solid var(--primary)' : '1px solid var(--border)', borderRadius: '8px', background: sel ? 'var(--primary)' : 'var(--bg-surface)', color: sel ? 'white' : 'var(--text-main)', fontWeight: sel ? '800' : '500', fontSize: '11px', cursor: 'pointer', transition: '0.15s', fontFamily: 'inherit' }}>{slot}</button>
                            );
                          })}
                        </div>
                    }
                  </div>
                );
              })()}
              <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                <button onClick={() => updateStatus(apt, 'Rescheduled', form.date, form.time)} disabled={!form.date || !form.time} style={{ ...s.btn, padding: '10px 18px', background: (!form.date || !form.time) ? 'var(--text-muted)' : 'var(--primary)', cursor: (!form.date || !form.time) ? 'default' : 'pointer' }}>Confirm</button>
                <button onClick={() => setRescheduleData(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={18} /></button>
              </div>
            </div>
          )}
        </div>
      );
    };

    const Section = ({ title, icon, items, color, emptyMsg }) => (
      <div style={{ marginBottom: '36px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
          {icon}
          <h3 style={{ margin: 0, color: 'var(--text-main)', fontSize: '17px', fontWeight: '800' }}>{title}</h3>
          <span style={{ background: `${color}20`, color, padding: '3px 12px', borderRadius: '99px', fontSize: '12px', fontWeight: '800' }}>{items.length}</span>
        </div>
        {items.length > 0
          ? <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>{items.map((a, i) => <AptCard key={i} apt={a} />)}</div>
          : <div style={{ padding: '28px', textAlign: 'center', color: 'var(--text-muted)', border: '1px dashed var(--border)', borderRadius: '16px', background: 'var(--bg-surface)', fontSize: '14px' }}>{emptyMsg}</div>
        }
      </div>
    );

    return (
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} style={s.page}>
        <div style={s.pageHeader}>
          <div>
            <h2 style={s.pageTitle}>Schedule Manager</h2>
            <p style={s.pageSub}>Manage upcoming and completed patient appointments.</p>
          </div>
        </div>
        <Section title="Upcoming" icon={<Clock size={20} color="var(--primary)" />} items={active} color="var(--primary)" emptyMsg="No upcoming appointments." />
        {done.length > 0 && <div style={{ opacity: 0.85 }}><Section title="Completed & Cancelled" icon={<CheckCircle2 size={20} color="var(--success)" />} items={done} color="var(--success)" emptyMsg="" /></div>}
      </motion.div>
    );
  };

  // ════════════════════════════════════════════════
  // VIEW 3 — PATIENT HISTORY
  // ════════════════════════════════════════════════
  const PatientHistoryView = () => {
    const [patients, setPatients] = useState([]);
    const [search, setSearch] = useState('');

    useEffect(() => {
      axios.get(`http://localhost:5001/api/doctor/patients/${user.id}`)
        .then(r => setPatients(r.data)).catch(() => { });
    }, []);

    const filtered = patients.filter(p =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.id.toLowerCase().includes(search.toLowerCase()) ||
      (p.history || '').toLowerCase().includes(search.toLowerCase())
    );

    return (
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} style={s.page}>
        <div style={{ ...s.pageHeader, marginBottom: '24px' }}>
          <div>
            <h2 style={s.pageTitle}>Patient History</h2>
            <p style={s.pageSub}>All patients who have consulted with you.</p>
          </div>
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input style={{ ...s.input, paddingLeft: '40px', width: '260px' }} placeholder="Search name, ID, history…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {filtered.length > 0 ? filtered.map((p, i) => (
            <div key={i} style={{ ...s.card, padding: '18px 24px', display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ width: '46px', height: '46px', borderRadius: '14px', background: 'var(--primary-light)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '900', fontSize: '18px', flexShrink: 0 }}>{p.name.charAt(0)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: '800', color: 'var(--text-main)', fontSize: '15px' }}>{p.name}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '3px' }}>ID: {p.id} · Age: {p.age} · {p.weight} kg</div>
                {p.history && <div style={{ fontSize: '12px', color: 'var(--primary)', fontWeight: '600', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '480px' }}>Hx: {p.history}</div>}
              </div>
              <button onClick={() => navigate('/doctor', { state: { patientId: p.id } })}
                style={{ ...s.btn, background: 'var(--primary-light)', color: 'var(--primary)', border: '1px solid var(--primary)', padding: '10px 18px', flexShrink: 0, fontSize: '13px' }}>
                View Record <ArrowRight size={14} />
              </button>
            </div>
          )) : (
            <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)', border: '1px dashed var(--border)', borderRadius: '20px', background: 'var(--bg-surface)' }}>
              <History size={44} style={{ opacity: 0.2, marginBottom: '14px' }} />
              <p style={{ margin: 0, fontWeight: '600' }}>{search ? 'No matches.' : 'No patient history yet.'}</p>
            </div>
          )}
        </div>
      </motion.div>
    );
  };

  return (
    <>
      <CustomAlert />
      <Routes>
        <Route path="/" element={<DashboardView />} />
        <Route path="/appointments" element={<AppointmentsView />} />
        <Route path="/patients" element={<PatientHistoryView />} />
      </Routes>
    </>
  );
}

const s = {
  page: { padding: '36px 40px', maxWidth: '1200px', margin: '0 auto' },
  pageHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '28px', flexWrap: 'wrap', gap: '16px' },
  pageTitle: { margin: 0, fontSize: '26px', fontWeight: '900', color: 'var(--text-main)', letterSpacing: '-0.5px' },
  pageSub: { margin: '5px 0 0', color: 'var(--text-muted)', fontSize: '14px' },
  card: { background: 'var(--bg-surface)', padding: '28px', borderRadius: '22px', boxShadow: 'var(--shadow-sm)', border: '1px solid var(--border)' },
  input: { width: '100%', padding: '12px 14px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--input-bg)', color: 'var(--text-main)', outline: 'none', fontSize: '14px', fontFamily: 'inherit', boxSizing: 'border-box' },
  dateInput: { padding: '10px 12px', borderRadius: '10px', border: '1px solid var(--border)', background: 'var(--bg-surface)', color: 'var(--text-main)', fontSize: '14px', outline: 'none', colorScheme: 'dark' },
  btn: { padding: '11px 20px', border: 'none', borderRadius: '10px', background: 'var(--primary)', color: 'white', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '7px', fontSize: '13px', transition: '0.2s' },
  iconBtn: { padding: '9px', border: 'none', borderRadius: '10px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  iconClose: { position: 'absolute', top: '14px', right: '14px', background: 'var(--bg-body)', border: '1px solid var(--border)', borderRadius: '8px', padding: '6px', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' },
  label: { fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '7px', display: 'block', letterSpacing: '0.5px' },
  statLabel: { fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.4px' },
};