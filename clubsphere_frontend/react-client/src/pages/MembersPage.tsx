import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { Member, MembershipPlan } from '../types';
import { Modal } from '../components/common/Modal';
import {
  Users,
  Search,
  Filter,
  Download,
  Upload,
  QrCode,
  Bell,
  CheckCircle,
  XCircle,
  AlertCircle,
  CreditCard,
  Plus,
  Sparkles,
} from 'lucide-react';

export const MembersPage: React.FC = () => {
  const { role, user } = useAuth();
  const queryClient = useQueryClient();

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [roleFilter, setRoleFilter] = useState('ALL');

  // Modals state
  const [isVerifyOpen, setIsVerifyOpen] = useState(false);
  const [verifyQuery, setVerifyQuery] = useState('');
  const [verifyResult, setVerifyResult] = useState<any>(null);

  const [isImportOpen, setIsImportOpen] = useState(false);
  const [csvText, setCsvText] = useState('');

  const [isSubscribeOpen, setIsSubscribeOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<MembershipPlan | null>(null);

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const canManageMembers = ['CLUB_ADMIN', 'SUPER_ADMIN'].includes(role);
  const canSendReminders = ['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER'].includes(role);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Queries
  const { data: members = [], isLoading } = useQuery<Member[]>({
    queryKey: ['members', statusFilter, roleFilter, searchTerm],
    queryFn: () =>
      api.listMembers({
        status: statusFilter,
        role: roleFilter,
        search: searchTerm,
      }),
  });

  const { data: plans = [] } = useQuery<MembershipPlan[]>({
    queryKey: ['membershipPlans'],
    queryFn: () => api.listMembershipPlans(),
  });

  // Verify status handler
  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verifyQuery.trim()) return;
    try {
      const res = await api.verifyMemberStatus(verifyQuery.trim());
      setVerifyResult(res);
    } catch (err: any) {
      setVerifyResult({
        isValid: false,
        message: err.message || 'Verification search failed',
      });
    }
  };

  // Send renewal reminder handler
  const handleRemind = async (memberId: string, memberEmail: string) => {
    try {
      const res = await api.sendRenewalReminder(memberId);
      showToast(`Renewal reminder dispatched to ${memberEmail}!`);
    } catch (err: any) {
      alert(`Error sending reminder: ${err.message}`);
    }
  };

  // Import CSV handler
  const handleImportCsv = async () => {
    try {
      const lines = csvText.trim().split('\n');
      if (lines.length === 0) return;
      const parsedMembers = [];
      for (const line of lines) {
        const parts = line.split(',').map((p) => p.trim().replace(/^"|"$/g, ''));
        if (parts.length >= 2 && parts[0] && parts[1]) {
          parsedMembers.push({
            fullName: parts[0],
            email: parts[1],
            studentId: parts[2] || undefined,
            department: parts[3] || undefined,
            tier: parts[4] || 'STANDARD',
          });
        }
      }
      const res = await api.importMembersCsv(parsedMembers);
      queryClient.invalidateQueries({ queryKey: ['members'] });
      setIsImportOpen(false);
      setCsvText('');
      showToast(`Imported ${res.createdCount} member records successfully!`);
    } catch (err: any) {
      alert(`Import error: ${err.message}`);
    }
  };

  // Subscribe plan handler
  const handleSubscribe = async () => {
    if (!selectedPlan) return;
    try {
      await api.subscribePlan(selectedPlan.id, 'DEMO_CARD');
      queryClient.invalidateQueries({ queryKey: ['members'] });
      setIsSubscribeOpen(false);
      showToast(`Subscribed to ${selectedPlan.name}! Status updated to Active Member.`);
    } catch (err: any) {
      alert(`Subscription error: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 glass-panel bg-navy-900 border border-teal-500/40 text-slate-100 px-4 py-3 rounded-2xl shadow-2xl flex items-center gap-3 animate-fade-in">
          <CheckCircle className="w-5 h-5 text-teal-400" />
          <span className="text-sm font-semibold">{toastMessage}</span>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 flex items-center gap-2.5">
            <Users className="w-6 h-6 text-purple-600" />
            <span>Membership Management</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Maintain the official student roster, track paid benefits & dues, configure tiers, and verify entry credentials.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => {
              setVerifyResult(null);
              setVerifyQuery('');
              setIsVerifyOpen(true);
            }}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-teal-50 text-teal-700 border border-teal-200 hover:bg-teal-100 text-xs font-bold transition shadow-2xs"
          >
            <QrCode className="w-4 h-4 text-teal-600" />
            <span>Verify Member ID</span>
          </button>

          {canManageMembers && (
            <button
              onClick={() => setIsImportOpen(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 text-xs font-semibold transition shadow-2xs"
            >
              <Upload className="w-4 h-4 text-slate-500" />
              <span>Import CSV</span>
            </button>
          )}

          <a
            href={api.exportCsvUrl('members')}
            download="members.csv"
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 text-xs font-semibold transition shadow-2xs"
          >
            <Download className="w-4 h-4 text-slate-500" />
            <span>Export CSV</span>
          </a>

          <button
            onClick={() => {
              setSelectedPlan(plans[0] || null);
              setIsSubscribeOpen(true);
            }}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-indigo-500/20 hover:opacity-95 transition"
          >
            <CreditCard className="w-4 h-4" />
            <span>Join / Renew Plan</span>
          </button>
        </div>
      </div>

      {/* Membership Tiers Showcase Cards - Vibrant Combined Colors */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {plans.map((p) => (
          <div
            key={p.id}
            className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden flex flex-col justify-between hover:shadow-md transition"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-base text-slate-900">{p.name}</span>
                <span className="text-xl font-black text-indigo-600">${p.price}</span>
              </div>
              <p className="text-xs text-slate-500 mb-3">{p.description}</p>
              <div className="flex flex-wrap gap-1.5">
                {p.benefitsList?.map((benefit, idx) => (
                  <span
                    key={idx}
                    className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 font-semibold px-2 py-0.5 rounded-full"
                  >
                    ✓ {benefit}
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-slate-500 font-medium">Duration: {p.durationMonths} Months</span>
              <button
                onClick={() => {
                  setSelectedPlan(p);
                  setIsSubscribeOpen(true);
                }}
                className="text-xs font-bold text-indigo-600 hover:text-indigo-800"
              >
                Subscribe ($ {p.price}) →
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Search & Filter Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
          <input
            type="text"
            placeholder="Search by name, email, student ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 font-medium focus:bg-white focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="ACTIVE">Active (Paid)</option>
            <option value="PENDING">Pending Approval</option>
            <option value="EXPIRED">Expired Dues</option>
          </select>

          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 font-medium focus:bg-white focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Roles</option>
            <option value="CLUB_ADMIN">President / Admin</option>
            <option value="TREASURER">Treasurer</option>
            <option value="EVENT_MANAGER">Event Manager</option>
            <option value="VOLUNTEER">Volunteer</option>
            <option value="MEMBER">Member</option>
          </select>
        </div>
      </div>

      {/* Roster Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 border-b border-slate-200 uppercase font-bold text-[11px]">
              <tr>
                <th className="py-3.5 px-4">Student Member</th>
                <th className="py-3.5 px-4">Student ID / Dept</th>
                <th className="py-3.5 px-4">Role & Tier</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Expiry Date</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {members.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    No member records found matching the filter criteria.
                  </td>
                </tr>
              ) : (
                members.map((m) => {
                  const isExpired = m.expiryDate ? new Date(m.expiryDate) < new Date() : false;
                  return (
                    <tr key={m.id} className="hover:bg-slate-50/70 transition">
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-3">
                          <img
                            src={m.user.avatarUrl || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150'}
                            alt={m.user.fullName}
                            className="w-8 h-8 rounded-full object-cover ring-1 ring-slate-200"
                          />
                          <div>
                            <div className="font-bold text-slate-900">{m.user.fullName}</div>
                            <div className="text-[11px] text-slate-500">{m.user.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-mono font-semibold text-slate-700">{m.studentId || 'N/A'}</div>
                        <div className="text-[11px] text-slate-500">{m.department || 'General'}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="font-bold text-indigo-600">{m.role}</span>
                        <div className="text-[11px] text-teal-600 font-bold">{m.tier}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            isExpired
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : m.status === 'ACTIVE'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          {isExpired ? 'EXPIRED' : m.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 font-medium">
                        {m.expiryDate ? new Date(m.expiryDate).toLocaleDateString() : 'Continuous'}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        {canSendReminders && (m.status !== 'ACTIVE' || isExpired) && (
                          <button
                            onClick={() => handleRemind(m.id, m.user.email)}
                            className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900 transition"
                            title="Send Renewal Reminder Notification"
                          >
                            <Bell className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Verify Member Status Modal */}
      <Modal
        isOpen={isVerifyOpen}
        onClose={() => setIsVerifyOpen(false)}
        title="Verify Membership Validity"
        subtitle="Check student dues standing, tier eligibility, and event discounts in real time."
      >
        <form onSubmit={handleVerify} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Enter Email, Student ID, or Member UUID
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. member@skyline.edu or SKY-2025-108"
                value={verifyQuery}
                onChange={(e) => setVerifyQuery(e.target.value)}
                className="flex-1 px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500"
              />
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs transition shadow-2xs"
              >
                Verify
              </button>
            </div>
          </div>

          {verifyResult && (
            <div
              className={`p-4 rounded-xl border ${
                verifyResult.isValid
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                  : 'bg-rose-50 border-rose-300 text-rose-900'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                {verifyResult.isValid ? (
                  <>
                    <CheckCircle className="w-5 h-5 text-emerald-600" />
                    <span className="font-bold text-emerald-800 text-sm">
                      VERIFIED ACTIVE MEMBER — ENTRY APPROVED
                    </span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-5 h-5 text-rose-600" />
                    <span className="font-bold text-rose-800 text-sm">
                      {verifyResult.message || 'NOT AN ACTIVE PAID MEMBER'}
                    </span>
                  </>
                )}
              </div>

              {verifyResult.member && (
                <div className="text-xs space-y-1 text-slate-700">
                  <div>Name: <strong className="text-slate-900">{verifyResult.member.name}</strong></div>
                  <div>Student ID: <strong>{verifyResult.member.studentId || 'N/A'}</strong></div>
                  <div>Tier: <strong>{verifyResult.member.tier}</strong></div>
                  <div>Discount Entitlement: <strong className="text-emerald-700">{verifyResult.member.discountPercentage}% Off</strong></div>
                  <div>Status: <strong className="uppercase">{verifyResult.member.status}</strong></div>
                </div>
              )}
            </div>
          )}
        </form>
      </Modal>

      {/* CSV Import Modal */}
      <Modal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        title="Import Member Roster (CSV)"
        subtitle="Paste CSV rows in format: Full Name, Email, Student ID, Department, Tier"
      >
        <div className="space-y-4">
          <textarea
            rows={6}
            placeholder={`Samantha Lee, samantha@skyline.edu, SKY-2026-801, Physics, STANDARD\nLucas Vance, lucas@skyline.edu, SKY-2026-802, Biology, VIP_GOLD`}
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            className="w-full p-3 rounded-xl bg-slate-50 border border-slate-300 text-xs font-mono text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setIsImportOpen(false)}
              className="px-3.5 py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-semibold"
            >
              Cancel
            </button>
            <button
              onClick={handleImportCsv}
              disabled={!csvText.trim()}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs disabled:opacity-50 shadow-2xs"
            >
              Import Members
            </button>
          </div>
        </div>
      </Modal>

      {/* Subscribe Plan Modal */}
      <Modal
        isOpen={isSubscribeOpen}
        onClose={() => setIsSubscribeOpen(false)}
        title="Subscribe to Membership Plan"
        subtitle="Activate full voting rights, event discounts, and exclusive society merchandise privileges."
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 mb-1">Select Tier</label>
            <select
              value={selectedPlan?.id || ''}
              onChange={(e) => setSelectedPlan(plans.find((p) => p.id === e.target.value) || null)}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none"
            >
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — ${p.price} / {p.durationMonths} Mos
                </option>
              ))}
            </select>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <div className="font-bold text-slate-900 mb-1 text-sm">{selectedPlan?.name}</div>
            <p className="text-slate-600 mb-2">{selectedPlan?.description}</p>
            <div className="flex justify-between items-center text-sm font-black text-indigo-700 pt-2 border-t border-slate-200">
              <span>Total Amount:</span>
              <span>${selectedPlan?.price} USD</span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-teal-50 border border-teal-200 text-teal-800 text-[11px] font-medium">
            ⚡ Sandbox Demo Card Payment: Transactions are automatically settled into the organization ledger without external fees.
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setIsSubscribeOpen(false)}
              className="px-3.5 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-semibold"
            >
              Cancel
            </button>
            <button
              onClick={handleSubscribe}
              className="px-5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-indigo-500/20"
            >
              Pay ${selectedPlan?.price} & Activate
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
