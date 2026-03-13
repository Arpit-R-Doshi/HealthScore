import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Routes, Route, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Pill, Search, Package, ClipboardList, PlusCircle, AlertTriangle, 
  ArrowUpDown, AlertCircle, CheckCircle2, X, FileCheck 
} from 'lucide-react';

export default function Pharmacist({ user }) {
  const [greeting, setGreeting] = useState('');
  
  // Custom Alert State
  const[alertConfig, setAlertConfig] = useState({ isOpen: false, title: '', message: '', type: 'success' });
  const showAlert = (title, message, type = 'success') => setAlertConfig({ isOpen: true, title, message, type });
  const closeAlert = () => setAlertConfig({ ...alertConfig, isOpen: false });

  useEffect(() => {
    const hour = new Date().getHours();
    setGreeting(hour < 12 ? "Good Morning" : hour < 18 ? "Good Afternoon" : "Good Evening");
  },[]);

  // --- REUSABLE CUSTOM ALERT MODAL ---
  const CustomAlert = () => (
    <AnimatePresence>
      {alertConfig.isOpen && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.4)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(5px)' }}>
          <motion.div initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9, y: 20 }} style={{ background: 'var(--bg-surface)', padding: '30px', borderRadius: '24px', width: '90%', maxWidth: '400px', border: '1px solid var(--border)', boxShadow: '0 20px 40px rgba(0,0,0,0.2)', textAlign: 'center', position: 'relative' }}>
            <button onClick={closeAlert} style={{ position: 'absolute', top: '15px', right: '15px', background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={20}/></button>
            <div style={{ display: 'inline-flex', marginBottom: '15px', background: alertConfig.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)', padding: '15px', borderRadius: '50%' }}>
              {alertConfig.type === 'error' ? <AlertCircle color="var(--danger)" size={40}/> : <CheckCircle2 color="var(--success)" size={40}/>}
            </div>
            <h3 style={{ margin: '0 0 10px 0', color: 'var(--text-main)', fontSize: '22px' }}>{alertConfig.title}</h3>
            <p style={{ color: 'var(--text-muted)', margin: '0 0 25px 0', lineHeight: '1.5' }}>{alertConfig.message}</p>
            <button onClick={closeAlert} style={{ width: '100%', padding: '14px', background: alertConfig.type === 'error' ? 'var(--danger)' : 'var(--success)', color: 'white', border: 'none', borderRadius: '12px', fontWeight: 'bold', fontSize: '16px', cursor: 'pointer' }}>Acknowledge</button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  // ==========================================
  // ROUTE 1: PRESCRIPTION LOOKUP & DISPENSE
  // ==========================================
  const DispenseView = () => {
    const [patientId, setPatientId] = useState('');
    const [rxList, setRxList] = useState([]);
    
    const fetchPatientRx = async () => {
      if (!patientId) return showAlert("Missing Info", "Please enter a Patient ID.", "error");
      try {
        const res = await axios.get(`http://localhost:5001/api/patient/${patientId}?role=Pharmacist`);
        setRxList(res.data.prescriptions);
      } catch (err) { 
        showAlert("Not Found", "Patient ID does not exist or has no records.", "error"); 
        setRxList([]); 
      }
    };

    const dispenseMedicine = async (rxId, medicineName) => {
      try {
        const res = await axios.post('http://localhost:5001/api/dispense', { rxId, patientId, medicineName });
        showAlert("Success", res.data.message, "success");
        fetchPatientRx(); // Refresh List
      } catch (err) { 
        showAlert("Dispense Failed", err.response?.data?.error || "Transaction failed.", "error"); 
      }
    };

    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} style={{ padding: '40px', maxWidth: '900px', margin: '0 auto' }}>
        <header style={{ marginBottom: '30px' }}>
          <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '28px', fontWeight: '800' }}>{greeting}, {user.name}</h2>
          <p style={{ color: 'var(--text-muted)', margin: '5px 0 0 0' }}>Verify prescriptions and dispense medication securely.</p>
        </header>

        <div style={s.card}>
          <h3 style={{ color: 'var(--primary)', display: 'flex', gap: '10px', alignItems: 'center', margin: '0 0 15px 0' }}><Search /> Prescription Lookup</h3>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input style={s.input} placeholder="Enter Patient ID (e.g. PT-1000)" onChange={e => setPatientId(e.target.value)} onKeyDown={e => e.key === 'Enter' && fetchPatientRx()} />
            <button style={{...s.btn, width: '150px'}} onClick={fetchPatientRx}>Find Records</button>
          </div>

          {rxList.length > 0 && (() => {
            const visibleRx = rxList.filter(rx => rx.status !== 'REVOKED');
            return visibleRx.length > 0 ? (
            <div style={{ marginTop: '30px' }}>
              <h4 style={{ color: 'var(--text-main)', marginBottom: '15px' }}>Found {visibleRx.length} active prescription{visibleRx.length !== 1 ? 's' : ''}:</h4>
              {visibleRx.map((rx, i) => (
                <div key={i} style={{ padding: '20px', background: 'var(--input-bg)', borderRadius: '12px', marginBottom: '15px', border: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ margin: '0 0 5px 0', color: 'var(--text-main)' }}>{rx.medicine}</h3>
                    <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                      <strong>Freq:</strong> {rx.frequency} &nbsp;|&nbsp; <strong>Dur:</strong> {rx.duration}
                    </div>
                    {rx.ipfsHash && (
                      <a href={`https://gateway.pinata.cloud/ipfs/${rx.ipfsHash}`} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', marginTop: '8px', fontSize: '12px', color: 'var(--primary)', textDecoration: 'none', fontWeight: 'bold' }}>
                        <FileCheck size={14}/> View Scanned Rx
                      </a>
                    )}
                  </div>
                  
                  {(!rx.dispensedDate && rx.status !== 'DISPENSED') ? (
                    <button style={{...s.btn, background: 'var(--warning)', color: '#fff'}} onClick={() => dispenseMedicine(rx.id, rx.medicine)}>
                      Dispense & Deduct Stock
                    </button>
                  ) : (
                    <div style={{ background: 'var(--success)', color: 'white', padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle2 size={16}/> Dispensed
                    </div>
                  )}
                </div>
              ))}
            </div>
            ) : (
            <div style={{ marginTop: '30px', padding: '24px', textAlign: 'center', color: 'var(--text-muted)', border: '1px dashed var(--border)', borderRadius: '12px', fontSize: '14px' }}>All prescriptions for this patient have been revoked.</div>
            );
          })()}
        </div>
      </motion.div>
    );
  };

  // ==========================================
  // ROUTE 2: INVENTORY MANAGER
  // ==========================================
  const InventoryView = () => {
    const [inventory, setInventory] = useState([]);
    const[newMed, setNewMed] = useState({ name: '', stock: '', price: '', expiry: '' });

    const fetchInventory = async () => {
      try { const res = await axios.get('http://localhost:5001/api/inventory'); setInventory(res.data); } catch(e){}
    };
    useEffect(() => { fetchInventory(); },[]);

    const addStock = async () => {
      if(!newMed.name || !newMed.stock) return showAlert("Missing Info", "Name and Quantity are required.", "error");
      try {
        await axios.post('http://localhost:5001/api/inventory/add', newMed);
        showAlert("Inventory Updated", `${newMed.name} stock has been successfully updated.`, "success");
        fetchInventory();
        setNewMed({ name: '', stock: '', price: '', expiry: '' });
      } catch(e) { showAlert("Update Error", "Failed to communicate with inventory database.", "error"); }
    };

    return (
      <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto' }}>
        <header style={{ marginBottom: '30px' }}>
          <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '28px', fontWeight: '800' }}>Inventory Manager</h2>
          <p style={{ color: 'var(--text-muted)', margin: '5px 0 0 0' }}>Track local stock levels and add incoming shipments.</p>
        </header>

        <div style={s.card}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1.5fr auto', gap: '10px', marginBottom: '20px', padding: '20px', background: 'var(--input-bg)', borderRadius: '12px', border: '1px solid var(--border)' }}>
            <input style={s.tinyInput} placeholder="Medicine Name" value={newMed.name} onChange={e => setNewMed({...newMed, name: e.target.value})} />
            <input style={s.tinyInput} type="number" placeholder="Qty" value={newMed.stock} onChange={e => setNewMed({...newMed, stock: e.target.value})} />
            <input style={s.tinyInput} type="number" placeholder="Price (₹)" value={newMed.price} onChange={e => setNewMed({...newMed, price: e.target.value})} />
            <input style={s.tinyInput} type="date" value={newMed.expiry} onChange={e => setNewMed({...newMed, expiry: e.target.value})} />
            <button style={{...s.btn, padding: '12px'}} onClick={addStock} title="Add to Inventory"><PlusCircle size={20}/></button>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ color: 'var(--text-muted)', fontSize: '12px', borderBottom: '2px solid var(--border)', textTransform: 'uppercase' }}>
                <th style={{padding: '15px 10px'}}>Medicine</th>
                <th style={{padding: '15px 10px'}}>Stock Level</th>
                <th style={{padding: '15px 10px'}}>Price</th>
                <th style={{padding: '15px 10px'}}>Expiry</th>
                <th style={{padding: '15px 10px'}}>Status</th>
              </tr>
            </thead>
            <tbody>
              {inventory.map((item, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-main)', fontSize: '14px' }}>
                  <td style={{padding: '15px 10px', fontWeight: 'bold'}}>{item.name}</td>
                  <td style={{padding: '15px 10px'}}>{item.stock} units</td>
                  <td style={{padding: '15px 10px'}}>₹{item.price}</td>
                  <td style={{padding: '15px 10px', color: 'var(--text-muted)'}}>{item.expiry}</td>
                  <td style={{padding: '15px 10px'}}>
                    {item.stock < 20 ? 
                      <span style={{ color: 'var(--danger)', background: 'rgba(239, 68, 68, 0.1)', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 'bold', display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                        <AlertTriangle size={14}/> Low Stock
                      </span> : 
                      <span style={{ color: 'var(--success)', background: 'rgba(16, 185, 129, 0.1)', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 'bold' }}>
                        In Stock
                      </span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    );
  };

  // ==========================================
  // ROUTE 3: DISPENSE LOGS
  // ==========================================
  const LogsView = () => {
    const [logs, setLogs] = useState([]);
    const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

    useEffect(() => {
      const fetchLogs = async () => {
        try { const res = await axios.get('http://localhost:5001/api/pharmacist/logs'); setLogs(res.data); } catch(e){}
      }; fetchLogs();
    },[]);

    const requestSort = (key) => {
      let direction = 'asc';
      if (sortConfig.key === key && sortConfig.direction === 'asc') direction = 'desc';
      setSortConfig({ key, direction });
      
      const sorted = [...logs].sort((a, b) => {
        if (a[key] < b[key]) return direction === 'asc' ? -1 : 1;
        if (a[key] > b[key]) return direction === 'asc' ? 1 : -1;
        return 0;
      });
      setLogs(sorted);
    };

    return (
      <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto' }}>
        <header style={{ marginBottom: '30px' }}>
          <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '28px', fontWeight: '800' }}>Distribution Logs</h2>
          <p style={{ color: 'var(--text-muted)', margin: '5px 0 0 0' }}>Historical record of all dispensed medications across the network.</p>
        </header>

        <div style={s.card}>          
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'var(--input-bg)', borderBottom: '2px solid var(--border)' }}>
                <th style={s.th} onClick={() => requestSort('date')}>Date/Time <ArrowUpDown size={12}/></th>
                <th style={s.th} onClick={() => requestSort('patientName')}>Patient Name <ArrowUpDown size={12}/></th>
                <th style={s.th} onClick={() => requestSort('medicine')}>Medicine <ArrowUpDown size={12}/></th>
                <th style={{...s.th, cursor: 'default'}}>RX Ledger ID</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-main)', fontSize: '14px' }}>
                  <td style={{padding: '16px', fontSize: '13px', color: 'var(--text-muted)'}}>{log.date}</td>
                  <td style={{padding: '16px', fontWeight: 'bold'}}>{log.patientName}</td>
                  <td style={{padding: '16px', color: 'var(--primary)', fontWeight: '600'}}>{log.medicine}</td>
                  <td style={{padding: '16px', color: 'var(--text-muted)', fontFamily: 'monospace'}}>{log.rxId}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    );
  };

  return (
    <>
      <CustomAlert />
      <Routes>
        <Route path="/" element={<DispenseView />} />
        <Route path="/inventory" element={<InventoryView />} />
        <Route path="/logs" element={<LogsView />} />
      </Routes>
    </>
  );
}

// --- STYLES ---
const s = {
  card: { background: 'var(--bg-surface)', padding: '30px', borderRadius: '24px', boxShadow: 'var(--shadow-sm)', border: '1px solid var(--border)' },
  input: { width: '100%', padding: '14px 16px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--input-bg)', color: 'var(--text-main)', fontSize: '14px', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit' },
  tinyInput: { width: '100%', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border)', background: 'var(--bg-surface)', color: 'var(--text-main)', fontSize: '13px', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', colorScheme: 'dark' },
  btn: { padding: '14px 20px', border: 'none', borderRadius: '12px', background: 'var(--primary)', color: 'white', fontWeight: 'bold', cursor: 'pointer', transition: '0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' },
  th: { padding: '16px', color: 'var(--text-muted)', fontSize: '12px', cursor: 'pointer', userSelect: 'none', textTransform: 'uppercase', letterSpacing: '0.5px' }
};