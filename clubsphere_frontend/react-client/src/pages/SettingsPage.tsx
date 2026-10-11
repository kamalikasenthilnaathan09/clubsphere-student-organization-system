import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { AuditLog } from '../types';
import { Modal } from '../components/common/Modal';
import {
  Settings,
  Shield,
  Palette,
  Building,
  CheckCircle,
  Clock,
  User,
  Plus,
  RefreshCw,
} from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { currentOrg, role, switchOrganization, resetDemoData } = useAuth();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'ORG' | 'AUDIT' | 'ONBOARDING'>('ORG');

  // Org form
  const [orgName, setOrgName] = useState(currentOrg?.name || 'Skyline Student Association');
  const [orgDesc, setOrgDesc] = useState(currentOrg?.description || '');
  const [primaryColor, setPrimaryColor] = useState(currentOrg?.primaryColor || '#8b5cf6');

  // Provisioning form
  const [newOrgName, setNewOrgName] = useState('');
  const [newOrgSlug, setNewOrgSlug] = useState('');
  const [newOrgDesc, setNewOrgDesc] = useState('');

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const canEditSettings = ['CLUB_ADMIN', 'SUPER_ADMIN'].includes(role);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Queries
  const { data: orgs = [] } = useQuery({
    queryKey: ['allOrgs'],
    queryFn: () => api.listOrganizations(),
  });

  const { data: auditLogs = [] } = useQuery<AuditLog[]>({
    queryKey: ['auditLogs'],
    queryFn: () => api.listAuditLogs(),
    enabled: activeTab === 'AUDIT' && canEditSettings,
  });

  const handleUpdateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.updateOrgSettings({
        name: orgName,
        description: orgDesc,
        primaryColor,
      });
      queryClient.invalidateQueries({ queryKey: ['currentOrg'] });
      showToast('Organization settings updated successfully!');
    } catch (err: any) {
      alert(`Update failed: ${err.message}`);
    }
  };

  const handleProvisionOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.provisionOrg({
        name: newOrgName,
        slug: newOrgSlug,
        description: newOrgDesc,
      });

      queryClient.invalidateQueries({ queryKey: ['allOrgs'] });
      setNewOrgName('');
      setNewOrgSlug('');
      setNewOrgDesc('');
      showToast(`Provisioned organization "${res.name}"!`);
      await switchOrganization(res.id);
    } catch (err: any) {
      alert(`Provisioning error: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 glass-panel bg-navy-900 border border-teal-500/40 text-slate-100 px-4 py-3 rounded-2xl shadow-2xl flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-teal-400" />
          <span className="text-sm font-semibold">{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 flex items-center gap-2.5">
            <Settings className="w-6 h-6 text-slate-600" />
            <span>Organization Settings & Audit Log</span>
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Configure branding, switch between organizations, and review immutable audit records.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => setActiveTab('ORG')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
            activeTab === 'ORG'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200/80'
          }`}
        >
          Club Profile & Branding
        </button>
        {canEditSettings && (
          <button
            onClick={() => setActiveTab('AUDIT')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
              activeTab === 'AUDIT'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200/80'
            }`}
          >
            Audit Trail ({auditLogs.length})
          </button>
        )}
        <button
          onClick={() => setActiveTab('ONBOARDING')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
            activeTab === 'ONBOARDING'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200/80'
          }`}
        >
          Provision New Club
        </button>
      </div>

      {/* ORG PROFILE TAB */}
      {activeTab === 'ORG' && (
        <div className="glass-panel p-6 rounded-2xl border border-brand-500/20 max-w-2xl space-y-5">
          <div>
            <h2 className="text-base font-bold text-white">Organization Details</h2>
            <p className="text-xs text-slate-400">Public profile and branding identity</p>
          </div>

          <form onSubmit={handleUpdateOrg} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Organization Name</label>
              <input
                type="text"
                disabled={!canEditSettings}
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white disabled:opacity-60"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1">Description & Mission</label>
              <textarea
                rows={3}
                disabled={!canEditSettings}
                value={orgDesc}
                onChange={(e) => setOrgDesc(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white disabled:opacity-60"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-300 mb-1">Primary Brand Accent</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    disabled={!canEditSettings}
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-8 h-8 rounded-lg bg-transparent border-0 cursor-pointer"
                  />
                  <span className="font-mono text-slate-300">{primaryColor}</span>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">Currency</label>
                <input
                  type="text"
                  disabled
                  value={currentOrg?.currency || 'USD'}
                  className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-800 text-slate-400"
                />
              </div>
            </div>

            {canEditSettings && (
              <div className="pt-2">
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs transition"
                >
                  Save Profile Settings
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* AUDIT LOG TAB */}
      {activeTab === 'AUDIT' && (
        <div className="space-y-4">
          <div className="glass-panel rounded-2xl border border-brand-500/20 overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-navy-900/90 text-slate-400 border-b border-slate-800 uppercase font-semibold">
                <tr>
                  <th className="py-3.5 px-4">Timestamp</th>
                  <th className="py-3.5 px-4">Actor</th>
                  <th className="py-3.5 px-4">Action</th>
                  <th className="py-3.5 px-4">Entity</th>
                  <th className="py-3.5 px-4">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-navy-900/40">
                    <td className="py-3 px-4 text-slate-400">
                      {new Date(log.createdAt).toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-white">{log.actor?.fullName}</div>
                      <div className="text-[10px] text-slate-400">{log.actor?.email}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-brand-300 font-bold">{log.action}</span>
                    </td>
                    <td className="py-3 px-4 text-slate-300">{log.entityType}</td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-400 max-w-xs truncate">
                      {JSON.stringify(log.parsedDetails || {})}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ONBOARDING NEW CLUB TAB */}
      {activeTab === 'ONBOARDING' && (
        <div className="glass-panel p-6 rounded-2xl border border-brand-500/20 max-w-2xl space-y-5">
          <div>
            <h2 className="text-base font-bold text-white">Provision New Student Society</h2>
            <p className="text-xs text-slate-400">
              Establish a new independent club tenant with dedicated membership records, events, and isolated financial ledger.
            </p>
          </div>

          <form onSubmit={handleProvisionOrg} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Club / Society Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Skyline Robotics Club"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1">URL Identifier (Slug)</label>
              <input
                type="text"
                required
                placeholder="e.g. skyline-robotics"
                value={newOrgSlug}
                onChange={(e) => setNewOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 font-mono text-white"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1">Description</label>
              <textarea
                rows={3}
                placeholder="Autonomous systems, drone competitions, and hardware hackathons."
                value={newOrgDesc}
                onChange={(e) => setNewOrgDesc(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>

            <div className="pt-2">
              <button
                type="submit"
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-brand-600 to-teal-600 hover:opacity-95 text-white font-semibold text-xs shadow-md shadow-brand-500/20"
              >
                Provision & Activate Club Tenant
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
