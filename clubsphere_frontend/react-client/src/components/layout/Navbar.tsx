import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import type { Role } from '../../types';
import {
  Bell,
  RotateCcw,
  Sparkles,
  Menu,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';

interface NavbarProps {
  onToggleSidebar: () => void;
}

const ROLES_LIST: { role: Role; label: string; icon: string }[] = [
  { role: 'SUPER_ADMIN', label: 'Super Admin', icon: '👑' },
  { role: 'CLUB_ADMIN', label: 'President', icon: '🏛️' },
  { role: 'TREASURER', label: 'Treasurer', icon: '💳' },
  { role: 'EVENT_MANAGER', label: 'Events', icon: '🎟️' },
  { role: 'VOLUNTEER', label: 'Volunteer', icon: '🤝' },
  { role: 'MEMBER', label: 'Member', icon: '⭐' },
  { role: 'STUDENT', label: 'Student', icon: '🎓' },
];

export const Navbar: React.FC<NavbarProps> = ({ onToggleSidebar }) => {
  const { user, role, currentOrg, switchRole, resetDemoData } = useAuth();
  const [showNotifications, setShowNotifications] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const { data: notificationsData, refetch: refetchNotifs } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.listNotifications(),
    refetchInterval: 15000,
  });

  const handleReset = async () => {
    if (confirm('Reset demo database to fresh competition state with sample records?')) {
      setIsResetting(true);
      try {
        await resetDemoData();
        alert('Demo database reset successfully!');
      } finally {
        setIsResetting(false);
      }
    }
  };

  const handleMarkAllRead = async () => {
    await api.markNotificationRead('all');
    refetchNotifs();
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/90 bg-white/95 backdrop-blur-md shadow-sm">
      {/* Interactive Competition Demo Control Strip - Bright Combined Color Palette */}
      <div className="bg-gradient-to-r from-violet-100/90 via-indigo-50/90 to-teal-50/90 px-4 py-1.5 border-b border-indigo-100 flex flex-wrap items-center justify-between text-xs text-slate-700 gap-2">
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 font-semibold text-violet-700 bg-white/80 px-2 py-0.5 rounded-md border border-violet-200 shadow-sm">
            <Sparkles className="w-3.5 h-3.5 text-teal-600 animate-pulse" />
            COMPETITION DEMO CONSOLE
          </span>
          <span className="hidden sm:inline text-slate-500 font-medium">1-Click Role Switcher:</span>
        </div>

        {/* 1-Click Role Switcher Pills */}
        <div className="flex items-center gap-1 overflow-x-auto py-0.5">
          {ROLES_LIST.map((item) => {
            const isActive = role === item.role;
            return (
              <button
                key={item.role}
                onClick={() => switchRole(item.role)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition flex items-center gap-1 whitespace-nowrap ${
                  isActive
                    ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-md shadow-indigo-500/20 font-bold'
                    : 'bg-white/85 text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200/90 shadow-2xs'
                }`}
                title={`Switch login to ${item.label}`}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        <button
          onClick={handleReset}
          disabled={isResetting}
          className="flex items-center gap-1 bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 px-2.5 py-1 rounded-md transition font-medium text-xs whitespace-nowrap shadow-2xs"
        >
          <RotateCcw className={`w-3 h-3 ${isResetting ? 'animate-spin' : ''}`} />
          <span>{isResetting ? 'Resetting...' : 'Reset Demo'}</span>
        </button>
      </div>

      {/* Main Bar */}
      <div className="px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onToggleSidebar}
            className="lg:hidden p-2 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100"
          >
            <Menu className="w-5 h-5" />
          </button>

          {/* Org Logo & Name */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center font-black text-white text-base shadow-md shadow-violet-500/20">
              CS
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900 text-sm tracking-tight">
                  {currentOrg?.name || 'Skyline Student Association'}
                </span>
                <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 text-[10px] rounded-full font-bold">
                  LIVE
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-medium">CampusSphere AI Platform</p>
            </div>
          </div>
        </div>

        {/* Right side controls */}
        <div className="flex items-center gap-3">
          {/* Notifications Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 transition shadow-2xs"
            >
              <Bell className="w-4 h-4" />
              {Boolean(notificationsData?.unreadCount && notificationsData.unreadCount > 0) && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-pulse">
                  {notificationsData?.unreadCount}
                </span>
              )}
            </button>

            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-2xl border border-slate-200 shadow-2xl p-4 z-50">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-slate-900">Notifications</span>
                    <span className="text-xs bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full font-semibold">
                      {notificationsData?.notifications?.length || 0}
                    </span>
                  </div>
                  <button
                    onClick={handleMarkAllRead}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold transition"
                  >
                    Mark all read
                  </button>
                </div>

                <div className="max-h-72 overflow-y-auto mt-2 space-y-2">
                  {notificationsData?.notifications?.length === 0 ? (
                    <p className="text-xs text-slate-500 py-4 text-center">No notifications</p>
                  ) : (
                    notificationsData?.notifications?.map((n) => (
                      <div
                        key={n.id}
                        className={`p-2.5 rounded-xl text-xs transition border ${
                          n.isRead
                            ? 'bg-slate-50 border-slate-200/80 text-slate-600'
                            : 'bg-violet-50/70 border-violet-200/80 text-slate-800'
                        }`}
                      >
                        <div className="font-semibold text-slate-900">{n.title}</div>
                        <p className="mt-1 text-slate-600 leading-relaxed">{n.message}</p>
                        <span className="text-[10px] text-slate-400 mt-1 block">
                          {new Date(n.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* User profile capsule */}
          <div className="flex items-center gap-2.5 pl-2 border-l border-slate-200">
            <img
              src={user?.avatarUrl || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150'}
              alt={user?.fullName || 'User'}
              className="w-8 h-8 rounded-full object-cover ring-2 ring-violet-500/20"
            />
            <div className="hidden sm:block text-left">
              <div className="text-xs font-bold text-slate-800 leading-tight">
                {user?.fullName || 'Guest User'}
              </div>
              <div className="text-[10px] font-bold text-violet-600 uppercase tracking-wider">
                {role.replace('_', ' ')}
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
