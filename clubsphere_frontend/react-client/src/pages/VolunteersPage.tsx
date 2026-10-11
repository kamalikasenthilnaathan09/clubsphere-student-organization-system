import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { VolunteerTask, Campaign, ExpenseClaim } from '../types';
import { Modal } from '../components/common/Modal';
import confetti from 'canvas-confetti';
import {
  CheckSquare,
  Plus,
  Heart,
  DollarSign,
  AlertTriangle,
  Clock,
  User,
  CheckCircle,
  XCircle,
  Receipt,
  FileText,
} from 'lucide-react';

export const VolunteersPage: React.FC = () => {
  const { role, user } = useAuth();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'TASKS' | 'CAMPAIGNS' | 'EXPENSES'>('TASKS');

  // Modals state
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDesc, setTaskDesc] = useState('');
  const [taskPriority, setTaskPriority] = useState<'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'>('MEDIUM');
  const [taskDueDate, setTaskDueDate] = useState('');

  const [isDonationModalOpen, setIsDonationModalOpen] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [donorName, setDonorName] = useState(user?.fullName || '');
  const [donationAmount, setDonationAmount] = useState(50);
  const [donationNote, setDonationNote] = useState('');

  const [isExpenseModalOpen, setIsExpenseModalOpen] = useState(false);
  const [expenseTitle, setExpenseTitle] = useState('');
  const [expenseDesc, setExpenseDesc] = useState('');
  const [expenseAmount, setExpenseAmount] = useState(35);
  const [expenseCategory, setExpenseCategory] = useState<any>('EVENT_SUPPLIES');
  const [receiptUrl, setReceiptUrl] = useState('https://example.com/receipts/doc-receipt.pdf');

  // Review modal
  const [selectedClaim, setSelectedClaim] = useState<ExpenseClaim | null>(null);
  const [reviewStatus, setReviewStatus] = useState<'APPROVED' | 'REJECTED'>('APPROVED');
  const [reviewNotes, setReviewNotes] = useState('Receipt verified against committee allocation');

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const canManageTasks = ['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER'].includes(role);
  const canReviewExpenses = ['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER'].includes(role);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Queries
  const { data: tasks = [] } = useQuery<VolunteerTask[]>({
    queryKey: ['tasks'],
    queryFn: () => api.listTasks(),
  });

  const { data: campaigns = [] } = useQuery<Campaign[]>({
    queryKey: ['campaigns'],
    queryFn: () => api.listCampaigns(),
  });

  const { data: expenses = [] } = useQuery<ExpenseClaim[]>({
    queryKey: ['expenses'],
    queryFn: () => api.listExpenseClaims(),
  });

  // Task status updater
  const handleUpdateTaskStatus = async (taskId: string, newStatus: string) => {
    try {
      await api.updateTask(taskId, { status: newStatus });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      showToast(`Task status updated to ${newStatus}`);
    } catch (err: any) {
      alert(`Update error: ${err.message}`);
    }
  };

  // Create Task
  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createTask({
        title: taskTitle,
        description: taskDesc,
        priority: taskPriority,
        dueDate: taskDueDate ? new Date(taskDueDate).toISOString() : undefined,
        assignedUserIds: user?.id ? [user.id] : [],
      });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setIsTaskModalOpen(false);
      setTaskTitle('');
      setTaskDesc('');
      showToast('Volunteer task created and assigned!');
    } catch (err: any) {
      alert(`Error creating task: ${err.message}`);
    }
  };

  // Record Donation
  const handleDonate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCampaign) return;
    try {
      await api.donateToCampaign(selectedCampaign.id, {
        amount: Number(donationAmount),
        donorName,
        note: donationNote,
      });

      confetti({ particleCount: 70, spread: 60, origin: { y: 0.6 } });
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      queryClient.invalidateQueries({ queryKey: ['financialSummary'] });
      setIsDonationModalOpen(false);
      showToast(`Donation of $${donationAmount} recorded into financial ledger!`);
    } catch (err: any) {
      alert(`Donation error: ${err.message}`);
    }
  };

  // Submit Expense Claim
  const handleSubmitExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.submitExpense({
        title: expenseTitle,
        description: expenseDesc,
        amount: Number(expenseAmount),
        category: expenseCategory,
        receiptUrl,
      });

      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      setIsExpenseModalOpen(false);
      setExpenseTitle('');
      setExpenseDesc('');
      showToast('Reimbursement claim submitted for Treasurer approval!');
    } catch (err: any) {
      alert(`Submission error: ${err.message}`);
    }
  };

  // Review Expense Claim (Treasurer)
  const handleReviewExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClaim) return;

    try {
      await api.reviewExpense(selectedClaim.id, {
        status: reviewStatus,
        reviewNotes,
      });

      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['financialSummary'] });
      setSelectedClaim(null);
      showToast(
        `Claim ${reviewStatus === 'APPROVED' ? 'approved and posted to financial ledger' : 'rejected'}`
      );
    } catch (err: any) {
      alert(`Review error: ${err.message}`);
    }
  };

  const columns = ['TODO', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED'];

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
            <CheckSquare className="w-6 h-6 text-cyan-600" />
            <span>Volunteers & Fundraising Hub</span>
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Coordinate student task forces, manage fundraising milestones, and submit expense reimbursements.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {activeTab === 'TASKS' && canManageTasks && (
            <button
              onClick={() => setIsTaskModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-indigo-500/20 hover:opacity-95 transition"
            >
              <Plus className="w-4 h-4" />
              <span>New Task</span>
            </button>
          )}

          {activeTab === 'EXPENSES' && (
            <button
              onClick={() => setIsExpenseModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs shadow-md shadow-teal-500/20 transition"
            >
              <Receipt className="w-4 h-4" />
              <span>Claim Reimbursement</span>
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => setActiveTab('TASKS')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
            activeTab === 'TASKS'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200/80'
          }`}
        >
          Task Kanban ({tasks.length})
        </button>
        <button
          onClick={() => setActiveTab('CAMPAIGNS')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
            activeTab === 'CAMPAIGNS'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200/80'
          }`}
        >
          Fundraising Drives ({campaigns.length})
        </button>
        <button
          onClick={() => setActiveTab('EXPENSES')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
            activeTab === 'EXPENSES'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200/80'
          }`}
        >
          Expense Claims ({expenses.length})
        </button>
      </div>

      {/* TASKS KANBAN BOARD */}
      {activeTab === 'TASKS' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {columns.map((col) => {
            const colTasks = tasks.filter((t) => t.status === col);
            return (
              <div
                key={col}
                className="glass-panel p-4 rounded-2xl border border-brand-500/20 flex flex-col h-[600px] bg-navy-950/60"
              >
                <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
                  <span className="font-bold text-xs text-white uppercase tracking-wider">
                    {col.replace('_', ' ')}
                  </span>
                  <span className="text-[10px] bg-navy-900 font-bold text-brand-300 px-2 py-0.5 rounded-full border border-slate-800">
                    {colTasks.length}
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                  {colTasks.map((task) => (
                    <div
                      key={task.id}
                      className="p-3.5 rounded-xl bg-navy-900/90 border border-slate-800 hover:border-brand-500/40 transition text-xs space-y-2 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-1">
                        <span className="font-semibold text-slate-100 line-clamp-2">
                          {task.title}
                        </span>
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase shrink-0 ${
                            task.priority === 'URGENT' || task.priority === 'HIGH'
                              ? 'bg-red-950 text-red-300 border border-red-500/30'
                              : 'bg-slate-800 text-slate-300'
                          }`}
                        >
                          {task.priority}
                        </span>
                      </div>

                      <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                        {task.description}
                      </p>

                      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-500">
                        <span>
                          {task.dueDate
                            ? `Due ${new Date(task.dueDate).toLocaleDateString([], { month: 'short', day: 'numeric' })}`
                            : 'No deadline'}
                        </span>
                        <div className="flex items-center gap-1">
                          {columns
                            .filter((c) => c !== col)
                            .map((nextCol) => (
                              <button
                                key={nextCol}
                                onClick={() => handleUpdateTaskStatus(task.id, nextCol)}
                                className="text-[9px] text-slate-400 hover:text-teal-400 bg-slate-800 px-1.5 py-0.5 rounded transition"
                                title={`Move to ${nextCol}`}
                              >
                                → {nextCol.slice(0, 4)}
                              </button>
                            ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* FUNDRAISING CAMPAIGNS TAB */}
      {activeTab === 'CAMPAIGNS' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {campaigns.map((camp) => (
            <div
              key={camp.id}
              className="glass-panel p-6 rounded-2xl border border-brand-500/20 relative overflow-hidden flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold text-teal-400 bg-teal-400/10 px-2 py-0.5 rounded border border-teal-500/20 uppercase">
                    {camp.status}
                  </span>
                  <span className="text-xs text-slate-400">
                    Target: ${camp.goalAmount.toLocaleString()}
                  </span>
                </div>

                <h2 className="text-lg font-bold text-white mt-1">{camp.title}</h2>
                <p className="text-xs text-slate-300 mt-2 leading-relaxed">{camp.description}</p>

                {/* Progress bar */}
                <div className="mt-5 space-y-1.5">
                  <div className="flex justify-between items-baseline text-xs">
                    <span className="font-extrabold text-teal-400 text-sm">
                      ${camp.currentAmount.toLocaleString()} Raised
                    </span>
                    <span className="font-bold text-slate-400">{camp.progressPercent}% of goal</span>
                  </div>
                  <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-brand-500 to-teal-400 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, camp.progressPercent)}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between">
                <span className="text-[11px] text-slate-500">
                  Ends {new Date(camp.endDate).toLocaleDateString()}
                </span>
                <button
                  onClick={() => {
                    setSelectedCampaign(camp);
                    setIsDonationModalOpen(true);
                  }}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-brand-600 to-teal-600 hover:opacity-95 text-white font-semibold text-xs shadow-md shadow-brand-500/20 flex items-center gap-1.5"
                >
                  <Heart className="w-3.5 h-3.5" />
                  <span>Contribute Donation</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* EXPENSE REIMBURSEMENT CLAIMS TAB */}
      {activeTab === 'EXPENSES' && (
        <div className="space-y-4">
          <div className="glass-panel p-4 rounded-2xl border border-brand-500/20 text-xs text-slate-300 bg-brand-950/20">
            <strong>Treasurer Policy:</strong> Claims must include itemized receipts. Approved claims automatically post a settled expense entry into the organization's financial ledger. Self-approval is restricted.
          </div>

          <div className="glass-panel rounded-2xl border border-brand-500/20 overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-navy-900/90 text-slate-400 border-b border-slate-800 uppercase font-semibold">
                <tr>
                  <th className="py-3.5 px-4">Claimant</th>
                  <th className="py-3.5 px-4">Title & Category</th>
                  <th className="py-3.5 px-4">Amount</th>
                  <th className="py-3.5 px-4">Receipt</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Review</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {expenses.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400">
                      No reimbursement claims submitted.
                    </td>
                  </tr>
                ) : (
                  expenses.map((c) => (
                    <tr key={c.id} className="hover:bg-navy-900/40">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-white">{c.claimant?.fullName}</div>
                        <div className="text-[11px] text-slate-400">{c.claimant?.email}</div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-200">{c.title}</div>
                        <div className="text-[11px] text-slate-400">{c.category}</div>
                      </td>
                      <td className="py-3 px-4 font-bold text-white text-sm">
                        ${c.amount.toFixed(2)}
                      </td>
                      <td className="py-3 px-4">
                        {c.receiptUrl ? (
                          <a
                            href={c.receiptUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="text-teal-400 hover:underline flex items-center gap-1 text-[11px]"
                          >
                            <FileText className="w-3.5 h-3.5" />
                            <span>View Doc</span>
                          </a>
                        ) : (
                          <span className="text-slate-500 text-[11px]">No file</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            c.status === 'APPROVED'
                              ? 'bg-teal-950 text-teal-300 border border-teal-500/30'
                              : c.status === 'REJECTED'
                              ? 'bg-red-950 text-red-300 border border-red-500/30'
                              : 'bg-amber-950 text-amber-300 border border-amber-500/30'
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        {canReviewExpenses && c.status === 'PENDING' && (
                          <button
                            onClick={() => {
                              setSelectedClaim(c);
                              setReviewStatus('APPROVED');
                            }}
                            className="px-3 py-1 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs"
                          >
                            Review Claim
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* New Task Modal */}
      <Modal
        isOpen={isTaskModalOpen}
        onClose={() => setIsTaskModalOpen(false)}
        title="Assign New Volunteer Task"
        subtitle="Specify deliverables, working committee priorities, and deadlines."
      >
        <form onSubmit={handleCreateTask} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 mb-1">Task Title</label>
            <input
              type="text"
              required
              placeholder="e.g. Test audio mixer and set up banner stands"
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Description</label>
            <textarea
              rows={3}
              required
              placeholder="Detailed instructions..."
              value={taskDesc}
              onChange={(e) => setTaskDesc(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Priority</label>
              <select
                value={taskPriority}
                onChange={(e) => setTaskPriority(e.target.value as any)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              >
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="URGENT">Urgent</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Due Date</label>
              <input
                type="date"
                value={taskDueDate}
                onChange={(e) => setTaskDueDate(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsTaskModalOpen(false)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold"
            >
              Create Task
            </button>
          </div>
        </form>
      </Modal>

      {/* Donation Modal */}
      <Modal
        isOpen={isDonationModalOpen}
        onClose={() => setIsDonationModalOpen(false)}
        title={`Contribute to: ${selectedCampaign?.title}`}
        subtitle="Donations are recorded directly into the society's financial ledger."
      >
        <form onSubmit={handleDonate} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 mb-1">Donor Full Name</label>
            <input
              type="text"
              required
              value={donorName}
              onChange={(e) => setDonorName(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Contribution Amount ($)</label>
            <input
              type="number"
              min={1}
              required
              value={donationAmount}
              onChange={(e) => setDonationAmount(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Optional Note / Dedication</label>
            <input
              type="text"
              placeholder="e.g. In honor of Class of 2026 CS Dept"
              value={donationNote}
              onChange={(e) => setDonationNote(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsDonationModalOpen(false)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-semibold"
            >
              Record ${donationAmount} Contribution
            </button>
          </div>
        </form>
      </Modal>

      {/* Submit Expense Claim Modal */}
      <Modal
        isOpen={isExpenseModalOpen}
        onClose={() => setIsExpenseModalOpen(false)}
        title="Submit Volunteer Reimbursement Claim"
        subtitle="Upload expense receipts incurred on behalf of student society projects."
      >
        <form onSubmit={handleSubmitExpense} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 mb-1">Expense Title</label>
            <input
              type="text"
              required
              placeholder="e.g. Poster Cardstock and Printing Supplies"
              value={expenseTitle}
              onChange={(e) => setExpenseTitle(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Amount ($)</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={expenseAmount}
                onChange={(e) => setExpenseAmount(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Category</label>
              <select
                value={expenseCategory}
                onChange={(e) => setExpenseCategory(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              >
                <option value="EVENT_SUPPLIES">Event Supplies</option>
                <option value="PRINTING">Printing & Lamination</option>
                <option value="REFRESHMENTS">Refreshments & Catering</option>
                <option value="TRAVEL">Travel / Transportation</option>
                <option value="MARKETING">Marketing & Advertising</option>
                <option value="OTHER">Other Expense</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Justification & Details</label>
            <textarea
              rows={3}
              required
              placeholder="Explain how this expense was utilized..."
              value={expenseDesc}
              onChange={(e) => setExpenseDesc(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Receipt URL / Document Link</label>
            <input
              type="text"
              required
              value={receiptUrl}
              onChange={(e) => setReceiptUrl(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsExpenseModalOpen(false)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-semibold"
            >
              Submit Reimbursement Request
            </button>
          </div>
        </form>
      </Modal>

      {/* Review Claim Modal (Treasurer) */}
      <Modal
        isOpen={Boolean(selectedClaim)}
        onClose={() => setSelectedClaim(null)}
        title={`Review Reimbursement: ${selectedClaim?.title}`}
        subtitle={`Claimant: ${selectedClaim?.claimant.fullName} | Amount: $${selectedClaim?.amount}`}
      >
        <form onSubmit={handleReviewExpense} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 mb-1">Decision</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setReviewStatus('APPROVED')}
                className={`py-2 rounded-xl font-bold border transition ${
                  reviewStatus === 'APPROVED'
                    ? 'bg-teal-600/30 border-teal-400 text-teal-300'
                    : 'bg-navy-950 border-slate-800 text-slate-400'
                }`}
              >
                Approve & Post to Ledger
              </button>
              <button
                type="button"
                onClick={() => setReviewStatus('REJECTED')}
                className={`py-2 rounded-xl font-bold border transition ${
                  reviewStatus === 'REJECTED'
                    ? 'bg-red-600/30 border-red-400 text-red-300'
                    : 'bg-navy-950 border-slate-800 text-slate-400'
                }`}
              >
                Reject Claim
              </button>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Review Notes & Reason</label>
            <textarea
              rows={3}
              required
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setSelectedClaim(null)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold"
            >
              Confirm Resolution
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
