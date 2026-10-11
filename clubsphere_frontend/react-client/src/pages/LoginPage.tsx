import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Shield, Key, User, ArrowRight, CheckCircle2 } from 'lucide-react';

const DEMO_PRESETS = [
  {
    role: 'SUPER_ADMIN',
    label: 'Kamalika (Main Admin)',
    email: 'kamalika@skyline.edu',
    pass: '12345678',
    desc: 'Main System Executive & Super Club Administrator',
    badge: '👑 Main Admin',
  },
  {
    role: 'SUPER_ADMIN',
    label: 'Platform Super Admin',
    email: 'superadmin@campussphere.edu',
    pass: 'Admin@123',
    desc: 'Platform administration & multi-org health',
    badge: '👑 Admin',
  },
  {
    role: 'CLUB_ADMIN',
    label: 'Club President',
    email: 'president@skyline.edu',
    pass: 'Skyline@123',
    desc: 'Full club authority: events, merchandise, settings',
    badge: '🏛️ President',
  },
  {
    role: 'TREASURER',
    label: 'Club Treasurer',
    email: 'treasurer@skyline.edu',
    pass: 'Skyline@123',
    desc: 'Financial ledger, expense reviews, budget tracking',
    badge: '💳 Finance',
  },
  {
    role: 'EVENT_MANAGER',
    label: 'Event Manager',
    email: 'events@skyline.edu',
    pass: 'Skyline@123',
    desc: 'Event planning & live door QR ticket scanner',
    badge: '🎟️ Events',
  },
  {
    role: 'VOLUNTEER',
    label: 'Student Volunteer',
    email: 'volunteer@skyline.edu',
    pass: 'Skyline@123',
    desc: 'Volunteer task boards & expense reimbursement claims',
    badge: '🤝 Volunteer',
  },
  {
    role: 'MEMBER',
    label: 'Active Paid Member',
    email: 'member@skyline.edu',
    pass: 'Skyline@123',
    desc: 'VIP Gold member discounts, ticket wallet & merch orders',
    badge: '⭐ VIP Member',
  },
  {
    role: 'STUDENT',
    label: 'General Student',
    email: 'student@skyline.edu',
    pass: 'Skyline@123',
    desc: 'Non-member pricing & public event registration',
    badge: '🎓 Student',
  },
];

export const LoginPage: React.FC = () => {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('president@skyline.edu');
  const [password, setPassword] = useState('Skyline@123');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await login({ email, password });
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    }
  };

  const handleQuickPreset = async (presetEmail: string, presetPass: string) => {
    setEmail(presetEmail);
    setPassword(presetPass);
    setError(null);
    try {
      await login({ email: presetEmail, password: presetPass });
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/50 to-purple-50/40 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden font-sans">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-200/40 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-teal-200/40 rounded-full blur-3xl pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center relative z-10">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-teal-400 mx-auto flex items-center justify-center font-black text-white text-xl shadow-lg shadow-violet-500/25">
          ⚡
        </div>
        <h1 className="mt-4 text-3xl font-black text-slate-900 tracking-tight">
          CampusSphere AI
        </h1>
        <p className="mt-1 text-xs text-slate-500 font-medium">
          One Campus. Every Club. One Intelligent Platform.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-xl relative z-10 space-y-6">
        {/* Sign in Box */}
        <div className="bg-white p-6 sm:p-8 rounded-3xl border border-slate-200/90 shadow-xl space-y-6">
          {error && (
            <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-bold text-slate-700 mb-1">Email Address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block font-bold text-slate-700 mb-1">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-blue-600 hover:opacity-95 text-white font-bold text-xs shadow-md shadow-indigo-500/25 disabled:opacity-50 transition flex items-center justify-center gap-2 mt-2"
            >
              <span>{isLoading ? 'Authenticating...' : 'Sign In to CampusSphere'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* 1-Click Competition Evaluation Presets */}
          <div className="pt-4 border-t border-slate-100">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-violet-700 flex items-center gap-1.5 uppercase tracking-wider">
                <Sparkles className="w-3.5 h-3.5 text-teal-600" />
                Competition Fast-Login Presets
              </span>
              <span className="text-[10px] text-slate-400 font-medium">Click to sign in instantly</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {DEMO_PRESETS.map((p) => (
                <button
                  key={p.role}
                  type="button"
                  onClick={() => handleQuickPreset(p.email, p.pass)}
                  className="p-2.5 rounded-xl bg-slate-50/90 border border-slate-200/90 hover:border-indigo-400 text-left transition hover:bg-indigo-50/40 group shadow-2xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 text-xs group-hover:text-indigo-600 transition">
                      {p.label}
                    </span>
                    <span className="text-[10px] text-indigo-600 font-semibold">{p.badge}</span>
                  </div>
                  <p className="text-[10px] text-slate-500 line-clamp-1 mt-0.5">{p.desc}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
