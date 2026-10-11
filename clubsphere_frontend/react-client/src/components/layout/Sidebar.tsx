import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Calendar,
  Megaphone,
  ShoppingBag,
  CheckSquare,
  Wallet,
  Sparkles,
  Settings,
  LogOut,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { logout, currentOrg } = useAuth();

  const navItems = [
    { to: '/', label: 'Overview Dashboard', icon: LayoutDashboard, iconColor: 'text-blue-500' },
    { to: '/members', label: 'Membership Roster', icon: Users, iconColor: 'text-purple-500' },
    { to: '/events', label: 'Events & Ticketing', icon: Calendar, iconColor: 'text-rose-500' },
    { to: '/announcements', label: 'Announcements', icon: Megaphone, iconColor: 'text-amber-500' },
    { to: '/merchandise', label: 'Merchandise Store', icon: ShoppingBag, iconColor: 'text-emerald-500' },
    { to: '/volunteers', label: 'Volunteers & Tasks', icon: CheckSquare, iconColor: 'text-cyan-500' },
    { to: '/finance', label: 'Financial Ledger', icon: Wallet, iconColor: 'text-teal-500' },
    { to: '/ai-copilot', label: 'AI Club Copilot', icon: Sparkles, iconColor: 'text-violet-500', highlight: true },
    { to: '/settings', label: 'Settings & Audit Logs', icon: Settings, iconColor: 'text-slate-500' },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-xs lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar container - Bright Clean Theme */}
      <aside
        className={`fixed lg:static top-0 bottom-0 left-0 z-50 w-64 bg-white/95 border-r border-slate-200/90 flex flex-col transition-transform duration-300 ease-in-out shadow-xs ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Brand header */}
        <div className="h-16 px-6 flex items-center justify-between border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-teal-400 flex items-center justify-center font-black text-white text-sm shadow-md shadow-violet-500/20">
              ⚡
            </div>
            <div>
              <span className="font-black text-sm tracking-wide text-slate-900">
                CampusSphere
              </span>
              <span className="text-[10px] block font-bold text-violet-600 uppercase tracking-widest">
                AI CORE
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden text-slate-500 hover:text-slate-800 p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <div className="px-3 pb-2 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
            Management Modules
          </div>

          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => onClose()}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition ${
                    isActive
                      ? 'bg-gradient-to-r from-violet-600 via-indigo-600 to-blue-600 text-white shadow-md shadow-indigo-500/20 font-bold'
                      : item.highlight
                      ? 'bg-violet-50 text-violet-700 hover:bg-violet-100/80 border border-violet-200/60'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`w-4 h-4 transition ${
                        isActive ? 'text-white' : item.iconColor
                      }`}
                    />
                    <span className="flex-1">{item.label}</span>
                    {item.highlight && (
                      <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded-full uppercase tracking-tighter ${
                        isActive ? 'bg-white/20 text-white' : 'bg-violet-200/80 text-violet-800'
                      }`}>
                        AI
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </div>

        {/* Club status card */}
        <div className="p-3 border-t border-slate-100">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/90 text-xs shadow-2xs">
            <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
              <span>Active Organization</span>
              <span className="w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-emerald-200"></span>
            </div>
            <div className="font-bold text-slate-900 truncate">
              {currentOrg?.name || 'Skyline Student Assoc.'}
            </div>
            <div className="text-[10px] text-indigo-600 font-semibold mt-0.5">
              Currency: {currentOrg?.currency || 'USD'}
            </div>
          </div>

          <button
            onClick={logout}
            className="w-full mt-2 flex items-center justify-center gap-2 py-2 px-3 text-xs text-red-600 hover:bg-red-50 rounded-xl transition border border-transparent hover:border-red-200 font-medium"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out Session</span>
          </button>
        </div>
      </aside>
    </>
  );
};
