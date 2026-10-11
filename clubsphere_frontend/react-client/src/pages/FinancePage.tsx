import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { FinancialTransaction, Budget } from '../types';
import { Modal } from '../components/common/Modal';
import {
  Wallet,
  ArrowUpRight,
  ArrowDownRight,
  Plus,
  RotateCcw,
  Download,
  Filter,
  Search,
  CheckCircle,
  AlertTriangle,
  PieChart,
} from 'lucide-react';

export const FinancePage: React.FC = () => {
  const { role, currentOrg } = useAuth();
  const queryClient = useQueryClient();

  const [typeFilter, setTypeFilter] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  // Modals
  const [isAddTxOpen, setIsAddTxOpen] = useState(false);
  const [txType, setTxType] = useState<'INCOME' | 'EXPENSE'>('INCOME');
  const [txCategory, setTxCategory] = useState<any>('MEMBERSHIP_DUES');
  const [txAmount, setTxAmount] = useState(100);
  const [txDesc, setTxDesc] = useState('');

  const [selectedReverseTx, setSelectedReverseTx] = useState<FinancialTransaction | null>(null);
  const [reverseReason, setReverseReason] = useState('Reversing accidental voucher entry');

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const canManageFinance = ['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER'].includes(role);
  const currency = currentOrg?.currency || 'USD';

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Queries
  const { data: summary } = useQuery({
    queryKey: ['financialSummary'],
    queryFn: () => api.getFinancialSummary(),
  });

  const { data: transactions = [] } = useQuery<FinancialTransaction[]>({
    queryKey: ['transactions', typeFilter, categoryFilter, searchTerm],
    queryFn: () =>
      api.listTransactions({
        type: typeFilter,
        category: categoryFilter,
        search: searchTerm,
      }),
  });

  const { data: budgets = [] } = useQuery<Budget[]>({
    queryKey: ['budgets'],
    queryFn: () => api.listBudgets(),
  });

  // Create Transaction
  const handleAddTx = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createTransaction({
        type: txType,
        category: txCategory,
        amount: Number(txAmount),
        description: txDesc,
        status: 'SETTLED',
      });

      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['financialSummary'] });
      setIsAddTxOpen(false);
      setTxDesc('');
      showToast('Transaction posted and recorded to ledger!');
    } catch (err: any) {
      alert(`Error creating transaction: ${err.message}`);
    }
  };

  // Reverse Transaction
  const handleReverse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReverseTx) return;

    try {
      await api.reverseTransaction(selectedReverseTx.id, reverseReason);
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['financialSummary'] });
      setSelectedReverseTx(null);
      showToast('Transaction reversed with offsetting correction entry!');
    } catch (err: any) {
      alert(`Reversal error: ${err.message}`);
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
            <Wallet className="w-6 h-6 text-teal-600" />
            <span>Financial Ledger & Accounting</span>
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Auditable double-entry record of membership dues, ticket revenues, store sales, reimbursements, and budget allocations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={api.exportCsvUrl('transactions')}
            download="transactions.csv"
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 text-xs font-semibold transition shadow-2xs"
          >
            <Download className="w-4 h-4 text-slate-500" />
            <span>Export Ledger CSV</span>
          </a>

          {canManageFinance && (
            <button
              onClick={() => setIsAddTxOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-indigo-500/20 hover:opacity-95 transition"
            >
              <Plus className="w-4 h-4" />
              <span>Record Transaction</span>
            </button>
          )}
        </div>
      </div>

      {/* Financial Summary Cards - Vibrant Combined Colors */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Total Settled Income */}
        <div className="bg-white p-5 rounded-2xl border border-emerald-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between text-xs text-slate-500 uppercase font-bold tracking-wider">
            <span>Settled Inflows</span>
            <div className="p-2 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-200">
              <ArrowUpRight className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-black text-emerald-600">
            +${summary?.totalIncome?.toLocaleString() ?? 0}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            Dues, ticket revenues, merchandise, and donations
          </div>
        </div>

        {/* Total Settled Expenses */}
        <div className="bg-white p-5 rounded-2xl border border-indigo-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between text-xs text-slate-500 uppercase font-bold tracking-wider">
            <span>Settled Outflows</span>
            <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-200">
              <ArrowDownRight className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-black text-indigo-600">
            -${summary?.totalExpenses?.toLocaleString() ?? 0}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            Event deposits, merchandise wholesale, and reimbursements
          </div>
        </div>

        {/* Recorded Net Balance */}
        <div className="bg-white p-5 rounded-2xl border border-violet-100 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between text-xs text-slate-500 uppercase font-bold tracking-wider">
            <span>Recorded Balance</span>
            <span className="text-[10px] text-indigo-700 font-bold bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200">
              DECIMAL-SAFE
            </span>
          </div>
          <div className="mt-2 text-2xl font-black text-slate-900">
            ${summary?.recordedBalance?.toLocaleString() ?? 0} {currency}
          </div>
          <div className="mt-1 text-[10px] text-slate-500 leading-tight">
            Formula: Settled Income − Settled Expenses. Internal ledger balance.
          </div>
        </div>
      </div>

      {/* Budget vs Actual Utilization Meters */}
      <div className="glass-panel p-6 rounded-2xl border border-brand-500/20 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white">Budget vs. Actual Spending (FY 2026)</h2>
            <p className="text-xs text-slate-400">Departmental expenditure vs authorized allocations</p>
          </div>
          <span className="text-xs bg-navy-800 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-700">
            Annual Caps
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          {budgets.map((b) => (
            <div key={b.id} className="p-4 rounded-xl bg-navy-900/80 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200">{b.category.replace(/_/g, ' ')}</span>
                <span className="font-mono text-slate-400">
                  ${b.actualSpent.toLocaleString()} / ${b.allocatedAmount.toLocaleString()}
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    b.isOverBudget
                      ? 'bg-red-500'
                      : b.utilizationRate > 80
                      ? 'bg-amber-400'
                      : 'bg-teal-400'
                  }`}
                  style={{ width: `${Math.min(100, b.utilizationRate)}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-[11px]">
                <span className={b.isOverBudget ? 'text-red-400 font-bold' : 'text-slate-400'}>
                  {b.isOverBudget ? 'OVER BUDGET' : `${b.utilizationRate}% utilized`}
                </span>
                <span className="text-slate-400">Remaining: ${b.remaining.toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Transactions Filter Toolbar */}
      <div className="glass-panel p-4 rounded-2xl border border-brand-500/20 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
          <input
            type="text"
            placeholder="Search description, reference ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-xl bg-navy-900 border border-slate-700/60 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 rounded-xl bg-navy-900 border border-slate-700/60 text-xs text-slate-200 focus:outline-none"
          >
            <option value="ALL">All Types</option>
            <option value="INCOME">Income Inflows</option>
            <option value="EXPENSE">Expense Outflows</option>
          </select>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-3 py-2 rounded-xl bg-navy-900 border border-slate-700/60 text-xs text-slate-200 focus:outline-none"
          >
            <option value="ALL">All Categories</option>
            <option value="MEMBERSHIP_DUES">Membership Dues</option>
            <option value="EVENT_TICKETS">Event Tickets</option>
            <option value="MERCHANDISE">Merchandise Sales</option>
            <option value="FUNDRAISING">Fundraising</option>
            <option value="VOLUNTEER_REIMBURSEMENT">Reimbursements</option>
            <option value="EVENT_EXPENSES">Event Expenses</option>
            <option value="OPERATING_EXPENSES">Operating Expenses</option>
            <option value="REFUND">Refunds & Reversals</option>
          </select>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="glass-panel rounded-2xl border border-brand-500/20 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-navy-900/90 text-slate-400 border-b border-slate-800 uppercase font-semibold">
              <tr>
                <th className="py-3.5 px-4">Date</th>
                <th className="py-3.5 px-4">Type</th>
                <th className="py-3.5 px-4">Category</th>
                <th className="py-3.5 px-4">Description</th>
                <th className="py-3.5 px-4">Reference</th>
                <th className="py-3.5 px-4">Amount</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4 text-right">Reversal</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {transactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">
                    No ledger transactions matching the selected filters.
                  </td>
                </tr>
              ) : (
                transactions.map((t) => {
                  const isIncome = t.type === 'INCOME';
                  const isReversed = t.status === 'REVERSED';

                  return (
                    <tr key={t.id} className="hover:bg-navy-900/40 transition">
                      <td className="py-3 px-4 text-slate-400">
                        {new Date(t.transactionDate).toLocaleDateString([], {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`font-bold ${
                            isIncome ? 'text-teal-400' : 'text-brand-400'
                          }`}
                        >
                          {t.type}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded bg-navy-900 border border-slate-800 text-[10px] text-slate-300">
                          {t.category}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-200 line-clamp-1">{t.description}</div>
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                        {t.reference || 'N/A'}
                      </td>
                      <td className="py-3 px-4 font-bold text-sm">
                        <span className={isIncome ? 'text-teal-400' : 'text-brand-300'}>
                          {isIncome ? '+' : '-'}${t.amount.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            isReversed
                              ? 'bg-slate-800 text-slate-400 border border-slate-700'
                              : t.status === 'SETTLED'
                              ? 'bg-teal-950 text-teal-300 border border-teal-500/30'
                              : 'bg-amber-950 text-amber-300 border border-amber-500/30'
                          }`}
                        >
                          {t.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        {canManageFinance && !isReversed && t.status === 'SETTLED' && (
                          <button
                            onClick={() => setSelectedReverseTx(t)}
                            className="p-1 rounded-lg bg-navy-800 hover:bg-slate-700 text-slate-400 hover:text-red-400 transition"
                            title="Reverse transaction with auditable offsetting correction"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
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

      {/* Record Manual Transaction Modal */}
      <Modal
        isOpen={isAddTxOpen}
        onClose={() => setIsAddTxOpen(false)}
        title="Record Financial Transaction"
        subtitle="Post a manual income or expenditure voucher into the ledger."
      >
        <form onSubmit={handleAddTx} className="space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Transaction Type</label>
              <select
                value={txType}
                onChange={(e) => setTxType(e.target.value as any)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              >
                <option value="INCOME">Income (Inflow)</option>
                <option value="EXPENSE">Expense (Outflow)</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Category</label>
              <select
                value={txCategory}
                onChange={(e) => setTxCategory(e.target.value as any)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              >
                <option value="MEMBERSHIP_DUES">Membership Dues</option>
                <option value="EVENT_TICKETS">Event Tickets</option>
                <option value="MERCHANDISE">Merchandise Sales</option>
                <option value="FUNDRAISING">Fundraising</option>
                <option value="EVENT_EXPENSES">Event Expenses</option>
                <option value="OPERATING_EXPENSES">Operating Expenses</option>
                <option value="MERCH_COSTS">Merchandise Wholesale Costs</option>
                <option value="VOLUNTEER_REIMBURSEMENT">Volunteer Reimbursement</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Amount ($ USD)</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              value={txAmount}
              onChange={(e) => setTxAmount(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Description / Memo</label>
            <input
              type="text"
              required
              placeholder="e.g. Deposit for sound system rental"
              value={txDesc}
              onChange={(e) => setTxDesc(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsAddTxOpen(false)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold"
            >
              Post to Ledger
            </button>
          </div>
        </form>
      </Modal>

      {/* Reverse Transaction Modal */}
      <Modal
        isOpen={Boolean(selectedReverseTx)}
        onClose={() => setSelectedReverseTx(null)}
        title={`Reverse Transaction: ${selectedReverseTx?.reference || selectedReverseTx?.id.slice(0, 8)}`}
        subtitle="Accounting Rule: Finalized records are never silently erased; an authorized offsetting entry is generated."
      >
        <form onSubmit={handleReverse} className="space-y-4 text-xs">
          <div className="p-3.5 rounded-xl bg-navy-950 border border-slate-800 space-y-1">
            <div className="text-slate-400">Original Transaction:</div>
            <div className="font-bold text-white">{selectedReverseTx?.description}</div>
            <div className="text-teal-400 font-extrabold text-sm">
              {selectedReverseTx?.type === 'INCOME' ? '+' : '-'}${selectedReverseTx?.amount.toFixed(2)}
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Reason for Reversal</label>
            <textarea
              rows={3}
              required
              placeholder="State reason (e.g. duplicate voucher, supplier refund)..."
              value={reverseReason}
              onChange={(e) => setReverseReason(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setSelectedReverseTx(null)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white font-semibold"
            >
              Confirm Reversal Correction
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
