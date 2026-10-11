import React, { createContext, useContext, useState, useEffect } from 'react';
import type { User, Role, Organization } from '../types';
import { api, setAuthToken, removeAuthToken, setSelectedOrgId, getSelectedOrgId } from '../services/api';

interface AuthContextType {
  user: User | null;
  role: Role;
  currentOrg: Organization | null;
  isLoading: boolean;
  login: (credentials: { email: string; password: string }) => Promise<void>;
  logout: () => void;
  switchRole: (targetRole: Role) => Promise<void>;
  switchOrganization: (orgId: string) => Promise<void>;
  resetDemoData: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Quick mapping for 1-click role switcher
const DEMO_EMAILS: Record<Role, string> = {
  SUPER_ADMIN: 'superadmin@campussphere.edu',
  CLUB_ADMIN: 'president@skyline.edu',
  TREASURER: 'treasurer@skyline.edu',
  EVENT_MANAGER: 'events@skyline.edu',
  VOLUNTEER: 'volunteer@skyline.edu',
  MEMBER: 'member@skyline.edu',
  STUDENT: 'student@skyline.edu',
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [currentOrg, setCurrentOrg] = useState<Organization | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchProfile = async () => {
    try {
      const data = await api.getMe();
      setUser(data);
      if (data.currentOrganization) {
        setCurrentOrg(data.currentOrganization);
        setSelectedOrgId(data.currentOrganization.id);
      }
    } catch (err) {
      setUser(null);
      setCurrentOrg(null);
      removeAuthToken();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const login = async (credentials: { email: string; password: string }) => {
    setIsLoading(true);
    try {
      const res = await api.login(credentials);
      setAuthToken(res.token);
      if (res.user.currentOrgId) {
        setSelectedOrgId(res.user.currentOrgId);
      }
      await fetchProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    removeAuthToken();
    setUser(null);
    setCurrentOrg(null);
  };

  const switchRole = async (targetRole: Role) => {
    setIsLoading(true);
    try {
      const email = DEMO_EMAILS[targetRole] || 'president@skyline.edu';
      const password = targetRole === 'SUPER_ADMIN' ? 'Admin@123' : 'Skyline@123';
      const res = await api.login({ email, password });
      setAuthToken(res.token);
      if (res.user.currentOrgId) {
        setSelectedOrgId(res.user.currentOrgId);
      }
      await fetchProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const switchOrganization = async (orgId: string) => {
    setSelectedOrgId(orgId);
    await fetchProfile();
  };

  const resetDemoData = async () => {
    await api.resetDemoData();
    await fetchProfile();
  };

  const role: Role = (user?.currentRole as Role) || (user?.isSuperAdmin ? 'SUPER_ADMIN' : 'MEMBER');

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        currentOrg,
        isLoading,
        login,
        logout,
        switchRole,
        switchOrganization,
        resetDemoData,
        refreshProfile: fetchProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
