import React from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, FileText } from 'lucide-react';

export default function Insurance({ user }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} style={{ padding: '40px', maxWidth: '1100px', margin: '0 auto' }}>
      <header style={{ marginBottom: '30px' }}>
        <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '28px', fontWeight: '800' }}>{user.name} Portal</h2>
        <p style={{ color: 'var(--text-muted)', margin: '5px 0 0 0' }}>Claims & Premium Management Dashboard</p>
      </header>

      <div style={{ background: 'var(--bg-surface)', padding: '50px', borderRadius: '24px', border: '1px dashed var(--primary)', textAlign: 'center', boxShadow: 'var(--shadow-sm)' }}>
        <ShieldCheck size={64} color="var(--primary)" style={{ margin: '0 auto 20px auto', opacity: 0.5 }} />
        <h3 style={{ color: 'var(--text-main)', fontSize: '22px', marginBottom: '10px' }}>Insurance Infrastructure Incoming</h3>
        <p style={{ color: 'var(--text-muted)', maxWidth: '500px', margin: '0 auto', lineHeight: '1.6' }}>
          This portal is currently under construction. It will soon integrate with the HealthScore AI to calculate dynamic premiums and automate claim verifications via Hyperledger Fabric.
        </p>
      </div>
    </motion.div>
  );
}