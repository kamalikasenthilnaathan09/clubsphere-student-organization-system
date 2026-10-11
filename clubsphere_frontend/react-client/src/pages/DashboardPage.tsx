import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import {
  Users,
  Wallet,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
  Ticket,
  Clock,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import { Link } from 'react-router-dom';

export const DashboardPage: React.FC = () => {
  const { role, currentOrg } = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ['dashboardMetrics'],
    queryFn: () => api.getDashboardMetrics(),
  });

  const kpis = data?.kpis;
  const currency = currentOrg?.currency || 'USD';

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-10 bg-slate-200 rounded-xl w-64" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 bg-slate-200/70 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Welcome Banner - Radiant Vibrant Combined Color */}
      <div className="rounded-2xl p-6 sm:p-8 relative overflow-hidden bg-gradient-to-r from-violet-600 via-indigo-600 to-blue-600 text-white shadow-lg shadow-indigo-500/20">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold text-white uppercase tracking-widest bg-white/20 px-2.5 py-0.5 rounded-full border border-white/30 backdrop-blur-xs">
                Live Operations
              </span>
              <span className="text-xs text-indigo-100">Current Role: <strong className="text-white font-bold">{role}</strong></span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              {currentOrg?.name || 'Skyline Student Association'}
            </h1>
            <p className="text-xs sm:text-sm text-indigo-100 mt-1 max-w-2xl leading-relaxed">
              Unified governance, real-time ticket attendance, member dues verification, inventory tracking, and financial reconciliation.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <Link
              to="/ai-copilot"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white font-bold text-xs shadow-md shadow-black/10 hover:bg-indigo-50 transition"
              style={{ color: '#4338ca' }}
            >
              <Sparkles className="w-4 h-4 text-violet-600" />
              <span style={{ color: '#4338ca' }} className="font-bold">Ask AI Copilot</span>
            </Link>
            <Link
              to="/events"
              className="px-4 py-2.5 rounded-xl bg-white/20 hover:bg-white/30 border border-white/40 font-bold text-xs transition backdrop-blur-xs flex items-center shadow-xs"
              style={{ color: '#ffffff' }}
            >
              <span style={{ color: '#ffffff' }} className="font-bold">Manage Events</span>
            </Link>
            <Link
              to="/finance"
              className="px-4 py-2.5 rounded-xl bg-white/20 hover:bg-white/30 border border-white/40 font-bold text-xs transition backdrop-blur-xs flex items-center shadow-xs"
              style={{ color: '#ffffff' }}
            >
              <span style={{ color: '#ffffff' }} className="font-bold">View Ledger</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Primary KPI Grid - Vibrant Combined Color Callouts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Active Members - Emerald / Mint Callout */}
        <div className="bg-white p-5 rounded-2xl border border-emerald-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Active Members</span>
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-white shadow-md shadow-emerald-500/20">
              <Users className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-black text-slate-900">{kpis?.activeMembers ?? 0}</span>
            <span className="text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-bold border border-emerald-200">
              In Good Standing
            </span>
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center justify-between">
            <span>Pending activation: <strong className="text-slate-800 font-semibold">{kpis?.pendingMembers ?? 0}</strong></span>
            {kpis?.expiringMembers > 0 && (
              <span className="text-amber-600 font-bold">{kpis.expiringMembers} expiring</span>
            )}
          </div>
        </div>

        {/* Recorded Net Balance - Indigo / Blue Callout */}
        <div className="bg-white p-5 rounded-2xl border border-indigo-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Recorded Balance</span>
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-indigo-500 to-blue-500 text-white shadow-md shadow-indigo-500/20">
              <Wallet className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-black text-slate-900">
              ${kpis?.recordedBalance?.toLocaleString() ?? 0}
            </span>
            <span className="text-xs text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full font-bold border border-indigo-200">
              {currency}
            </span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500 flex items-center justify-between">
            <span className="text-emerald-600 font-bold flex items-center">
              <ArrowUpRight className="w-3 h-3 mr-0.5" /> +${kpis?.totalIncome?.toLocaleString() ?? 0}
            </span>
            <span className="text-rose-500 font-bold flex items-center">
              <ArrowDownRight className="w-3 h-3 mr-0.5" /> -${kpis?.totalExpenses?.toLocaleString() ?? 0}
            </span>
          </div>
        </div>

        {/* Event Tickets & Attendance - Purple / Rose Callout */}
        <div className="bg-white p-5 rounded-2xl border border-purple-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Tickets & Attendance</span>
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-purple-500 to-pink-500 text-white shadow-md shadow-purple-500/20">
              <Ticket className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-black text-slate-900">
              {kpis?.totalConfirmedTickets ?? 0}
            </span>
            <span className="text-xs text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full font-bold border border-purple-200">
              Bookings
            </span>
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center justify-between">
            <span>Checked In: <strong className="text-indigo-600 font-bold">{kpis?.totalCheckedIn ?? 0}</strong></span>
            <span className="text-slate-600">{kpis?.upcomingEventsCount ?? 0} upcoming</span>
          </div>
        </div>

        {/* Pending Action Items - Amber / Coral Callout */}
        <div className="bg-white p-5 rounded-2xl border border-amber-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Pending Action Items</span>
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-400 text-white shadow-md shadow-amber-500/20">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-black text-amber-600">
              {(kpis?.pendingReimbursementsCount ?? 0) + (kpis?.lowStockCount ?? 0)}
            </span>
            <span className="text-xs text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full font-bold border border-amber-200">
              Attention
            </span>
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center justify-between">
            <span>Claims: <strong className="text-slate-800 font-semibold">{kpis?.pendingReimbursementsCount ?? 0}</strong></span>
            <span>Low Stock: <strong className="text-amber-600 font-bold">{kpis?.lowStockCount ?? 0}</strong></span>
          </div>
        </div>
      </div>

      {/* Main Charts & Activity Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Income vs Expenses Chart */}
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">Financial Inflows & Outflows</h2>
              <p className="text-xs text-slate-500">Monthly settled transactions from verified ledger entries</p>
            </div>
            <span className="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-lg border border-slate-200 font-semibold">
              6 Months
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.monthlyTrends || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} tickFormatter={(val) => `$${val}`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '12px', fontSize: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Bar dataKey="income" name="Recorded Income" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="expenses" name="Recorded Expenses" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Upcoming Events Spotlight */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-slate-900">Upcoming Events</h2>
              <Link to="/events" className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold">View all</Link>
            </div>

            <div className="space-y-3">
              {data?.upcomingEvents?.length === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">No upcoming events scheduled</p>
              ) : (
                data?.upcomingEvents?.map((evt: any) => (
                  <div key={evt.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 hover:border-indigo-300 transition">
                    <div className="flex items-start justify-between">
                      <span className="text-xs font-bold text-slate-800 line-clamp-1">{evt.title}</span>
                      <span className="text-[10px] bg-violet-100 text-violet-700 font-bold px-2 py-0.5 rounded">
                        {evt.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-2">
                      <span className="flex items-center gap-1 font-medium">
                        <Clock className="w-3 h-3 text-slate-400" />
                        {new Date(evt.startDate).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                      </span>
                      <span>Cap: {evt.capacity}</span>
                      <span className="text-indigo-600 font-semibold">Booked: {evt.tickets?.length || 0}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-100 text-center">
            <Link
              to="/events"
              className="inline-flex items-center justify-center gap-2 w-full py-2.5 px-3 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs transition border border-indigo-200 shadow-2xs"
            >
              <Ticket className="w-3.5 h-3.5" />
              <span>Launch Ticket Scanner Console</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Ledger Entries & Audit Trail */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Transactions */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">Recent Ledger Transactions</h2>
              <p className="text-xs text-slate-500">Traceable income and expense records</p>
            </div>
            <Link to="/finance" className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold">Ledger details</Link>
          </div>

          <div className="space-y-2.5">
            {data?.recentTransactions?.map((tx: any) => {
              const isIncome = tx.type === 'INCOME';
              return (
                <div key={tx.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between text-xs">
                  <div>
                    <div className="font-semibold text-slate-800 line-clamp-1">{tx.description}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5 flex items-center gap-2">
                      <span>{new Date(tx.transactionDate).toLocaleDateString()}</span>
                      <span className="px-1.5 py-0.2 bg-white border border-slate-200 rounded font-medium">{tx.category}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`font-black text-sm ${isIncome ? 'text-emerald-600' : 'text-indigo-600'}`}>
                      {isIncome ? '+' : '-'}${tx.amount.toLocaleString()}
                    </span>
                    <span className="text-[10px] text-slate-400 block uppercase font-medium">{tx.status}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Audit Log */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">Security & Administrative Audit Trail</h2>
              <p className="text-xs text-slate-500">Immutable ledger of privileged operations</p>
            </div>
            <Link to="/settings" className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold">All audit logs</Link>
          </div>

          <div className="space-y-2.5">
            {data?.recentAudit?.map((log: any) => (
              <div key={log.id} className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs flex items-center justify-between">
                <div>
                  <span className="font-bold text-indigo-700">{log.action.replace(/_/g, ' ')}</span>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    By: <strong className="text-slate-800 font-semibold">{log.actor?.fullName || 'System'}</strong> on {log.entityType}
                  </div>
                </div>
                <span className="text-[10px] text-slate-400 font-medium">
                  {new Date(log.createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
