import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { Announcement } from '../types';
import { Modal } from '../components/common/Modal';
import {
  Megaphone,
  Plus,
  Mail,
  Send,
  AlertTriangle,
  Calendar,
  Award,
  BookOpen,
  CheckCircle,
} from 'lucide-react';

export const AnnouncementsPage: React.FC = () => {
  const { role } = useAuth();
  const queryClient = useQueryClient();

  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [audienceFilter, setAudienceFilter] = useState('ALL');

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState<'GENERAL' | 'URGENT' | 'EVENT' | 'ACADEMIC' | 'OPPORTUNITY'>('GENERAL');
  const [targetAudience, setTargetAudience] = useState<'ALL_MEMBERS' | 'ACTIVE_ONLY' | 'VOLUNTEERS' | 'EXECUTIVES'>('ALL_MEMBERS');
  const [sendEmail, setSendEmail] = useState(true);

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const canCreate = ['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER'].includes(role);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const { data: announcements = [], isLoading } = useQuery<Announcement[]>({
    queryKey: ['announcements', categoryFilter, audienceFilter],
    queryFn: () =>
      api.listAnnouncements({
        category: categoryFilter,
        audience: audienceFilter,
      }),
  });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createAnnouncement({
        title,
        content,
        category,
        targetAudience,
        status: 'PUBLISHED',
        sendEmailNotification: sendEmail,
      });

      queryClient.invalidateQueries({ queryKey: ['announcements'] });
      setIsCreateOpen(false);
      setTitle('');
      setContent('');
      showToast('Announcement broadcasted successfully across platform and mailers!');
    } catch (err: any) {
      alert(`Error broadcasting announcement: ${err.message}`);
    }
  };

  const categoryIcons: Record<string, any> = {
    URGENT: AlertTriangle,
    EVENT: Calendar,
    OPPORTUNITY: Award,
    ACADEMIC: BookOpen,
    GENERAL: Megaphone,
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
            <Megaphone className="w-6 h-6 text-amber-500" />
            <span>Centralized Announcement Center</span>
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Publish official broadcasts, target membership segments, and trigger synchronized email alerts.
          </p>
        </div>

        {canCreate && (
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-indigo-500/20 hover:opacity-95 transition"
          >
            <Plus className="w-4 h-4" />
            <span>Broadcast Announcement</span>
          </button>
        )}
      </div>

      {/* Filters Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500 mr-1 font-bold">Category:</span>
          {['ALL', 'URGENT', 'EVENT', 'GENERAL', 'ACADEMIC', 'OPPORTUNITY'].map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                categoryFilter === cat
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:text-slate-900 hover:bg-slate-200 border border-slate-200/80'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-bold">Target:</span>
          <select
            value={audienceFilter}
            onChange={(e) => setAudienceFilter(e.target.value)}
            className="px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-300 text-xs text-slate-800 font-medium focus:bg-white"
          >
            <option value="ALL">All Audiences</option>
            <option value="ALL_MEMBERS">All Members</option>
            <option value="ACTIVE_ONLY">Active Paid Only</option>
            <option value="VOLUNTEERS">Volunteers</option>
            <option value="EXECUTIVES">Executives</option>
          </select>
        </div>
      </div>

      {/* Announcements Feed */}
      <div className="space-y-4">
        {announcements.length === 0 ? (
          <div className="glass-panel p-8 text-center rounded-2xl border border-brand-500/20">
            <Megaphone className="w-10 h-10 text-slate-500 mx-auto mb-2" />
            <p className="text-sm font-semibold text-slate-300">No announcements found</p>
            <p className="text-xs text-slate-500 mt-1">Check back later or broadcast a new message above.</p>
          </div>
        ) : (
          announcements.map((a) => {
            const Icon = categoryIcons[a.category] || Megaphone;
            const isUrgent = a.category === 'URGENT';

            return (
              <div
                key={a.id}
                className={`glass-panel p-5 rounded-2xl border transition-all ${
                  isUrgent
                    ? 'border-red-500/40 bg-gradient-to-r from-red-950/20 via-navy-950 to-navy-950'
                    : 'border-brand-500/20 hover:border-brand-500/35'
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`p-2 rounded-xl ${
                        isUrgent
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-brand-500/20 text-brand-300'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-white">{a.title}</h2>
                      <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                        <span>
                          {a.publishedAt
                            ? new Date(a.publishedAt).toLocaleDateString([], {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              })
                            : 'Draft'}
                        </span>
                        <span>•</span>
                        <span className="font-medium text-brand-400 uppercase">
                          Target: {a.targetAudience.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                        isUrgent
                          ? 'bg-red-950 text-red-300 border border-red-500/30'
                          : 'bg-brand-950 text-brand-300 border border-brand-500/30'
                      }`}
                    >
                      {a.category}
                    </span>

                    {a.emailSent && (
                      <span className="text-[10px] bg-teal-950 text-teal-300 border border-teal-500/30 font-semibold px-2 py-0.5 rounded-full flex items-center gap-1">
                        <Mail className="w-3 h-3" />
                        <span>Email Sent ({a.emailRecipientCount})</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-xs text-slate-300 whitespace-pre-line leading-relaxed pl-11">
                  {a.content}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Broadcast Announcement Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Broadcast Announcement"
        subtitle="Deliver notification to web dashboards and simulated campus email lists."
      >
        <form onSubmit={handleCreate} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 mb-1">Headline / Subject</label>
            <input
              type="text"
              required
              placeholder="e.g. Society General Meeting & Annual Elections"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as any)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              >
                <option value="GENERAL">General Notice</option>
                <option value="URGENT">Urgent Alert</option>
                <option value="EVENT">Event Announcement</option>
                <option value="ACADEMIC">Academic / Research</option>
                <option value="OPPORTUNITY">Opportunity / Grants</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1">Target Audience</label>
              <select
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value as any)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              >
                <option value="ALL_MEMBERS">All Members</option>
                <option value="ACTIVE_ONLY">Active Paid Members Only</option>
                <option value="VOLUNTEERS">Volunteers Only</option>
                <option value="EXECUTIVES">Executive Committee</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Announcement Body</label>
            <textarea
              rows={5}
              required
              placeholder="Write announcement details..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full p-3 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="flex items-center gap-2 p-3 rounded-xl bg-navy-950 border border-slate-800">
            <input
              type="checkbox"
              id="sendEmail"
              checked={sendEmail}
              onChange={(e) => setSendEmail(e.target.checked)}
              className="rounded text-brand-600 focus:ring-brand-500"
            />
            <label htmlFor="sendEmail" className="text-slate-300 font-medium cursor-pointer">
              Send Email Broadcast to registered student mailboxes (Demo notification adapter)
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsCreateOpen(false)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold flex items-center gap-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Broadcast Now</span>
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
