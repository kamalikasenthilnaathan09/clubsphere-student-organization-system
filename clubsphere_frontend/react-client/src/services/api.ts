const BASE_URL = '/api';

export function getAuthToken(): string | null {
  return localStorage.getItem('campussphere_token');
}

export function setAuthToken(token: string): void {
  localStorage.setItem('campussphere_token', token);
}

export function removeAuthToken(): void {
  localStorage.removeItem('campussphere_token');
}

export function getSelectedOrgId(): string | null {
  return localStorage.getItem('campussphere_org_id');
}

export function setSelectedOrgId(orgId: string): void {
  localStorage.setItem('campussphere_org_id', orgId);
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const orgId = getSelectedOrgId();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (orgId) {
    headers['x-organization-id'] = orgId;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message = errorBody.error || errorBody.message || `Request failed with status ${response.status}`;
    const error = new Error(message) as any;
    error.status = response.status;
    error.body = errorBody;
    throw error;
  }

  // Handle CSV/text responses
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('text/csv')) {
    return (await response.text()) as unknown as T;
  }

  return response.json();
}

export const api = {
  // Auth
  login: (credentials: { email: string; password: string }) =>
    request<any>('/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  register: (data: any) =>
    request<any>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  getMe: () =>
    request<any>('/auth/me'),
  getDemoAccounts: () =>
    request<{ demoAccounts: any[] }>('/auth/demo-accounts'),
  resetDemoData: () =>
    request<{ success: boolean; message: string }>('/auth/reset-demo', { method: 'POST' }),

  // Organizations
  listOrganizations: () =>
    request<any[]>('/organizations'),
  getCurrentOrg: () =>
    request<any>('/organizations/current'),
  updateOrgSettings: (data: any) =>
    request<any>('/organizations/settings', { method: 'PATCH', body: JSON.stringify(data) }),
  provisionOrg: (data: any) =>
    request<any>('/organizations/provision', { method: 'POST', body: JSON.stringify(data) }),

  // Members
  listMembers: (params?: { status?: string; role?: string; tier?: string; search?: string }) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<any[]>(`/members?${qs}`);
  },
  updateMember: (id: string, data: any) =>
    request<any>(`/members/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  verifyMemberStatus: (query: string) =>
    request<any>(`/members/verify?query=${encodeURIComponent(query)}`),
  sendRenewalReminder: (id: string) =>
    request<any>(`/members/${id}/remind`, { method: 'POST' }),
  importMembersCsv: (members: any[]) =>
    request<any>('/members/import-csv', { method: 'POST', body: JSON.stringify({ members }) }),
  listMembershipPlans: () =>
    request<any[]>('/members/plans'),
  createMembershipPlan: (data: any) =>
    request<any>('/members/plans', { method: 'POST', body: JSON.stringify(data) }),
  subscribePlan: (planId: string, paymentMethod = 'DEMO_CARD') =>
    request<any>('/members/subscribe', { method: 'POST', body: JSON.stringify({ planId, paymentMethod }) }),

  // Events & Ticketing
  listEvents: (params?: { status?: string; category?: string; upcomingOnly?: boolean }) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<any[]>(`/events?${qs}`);
  },
  getEventDetails: (id: string) =>
    request<any>(`/events/${id}`),
  createEvent: (data: any) =>
    request<any>('/events', { method: 'POST', body: JSON.stringify(data) }),
  updateEventStatus: (id: string, status: string) =>
    request<any>(`/events/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  bookTicket: (eventId: string, data: any) =>
    request<any>(`/events/${eventId}/book`, { method: 'POST', body: JSON.stringify(data) }),
  checkInTicket: (eventId: string, data: { ticketCode: string; checkInMethod?: string; notes?: string }) =>
    request<any>(`/events/${eventId}/check-in`, { method: 'POST', body: JSON.stringify(data) }),
  cancelBooking: (bookingId: string) =>
    request<any>(`/events/bookings/${bookingId}/cancel`, { method: 'POST' }),
  getUserTickets: () =>
    request<any[]>('/events/my-tickets'),

  // Announcements
  listAnnouncements: (params?: { category?: string; audience?: string }) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<any[]>(`/announcements?${qs}`);
  },
  createAnnouncement: (data: any) =>
    request<any>('/announcements', { method: 'POST', body: JSON.stringify(data) }),
  archiveAnnouncement: (id: string) =>
    request<any>(`/announcements/${id}/archive`, { method: 'PATCH' }),

  // Merchandise
  listProducts: (params?: { category?: string; search?: string }) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<any[]>(`/merchandise?${qs}`);
  },
  createProduct: (data: any) =>
    request<any>('/merchandise', { method: 'POST', body: JSON.stringify(data) }),
  adjustStock: (variantId: string, data: any) =>
    request<any>(`/merchandise/variants/${variantId}/adjust`, { method: 'POST', body: JSON.stringify(data) }),
  checkoutOrder: (data: any) =>
    request<any>('/merchandise/checkout', { method: 'POST', body: JSON.stringify(data) }),
  listUserOrders: () =>
    request<any[]>('/merchandise/my-orders'),
  getLowStockAlerts: () =>
    request<any[]>('/merchandise/low-stock'),

  // Volunteers & Fundraising
  listTasks: (params?: { status?: string; priority?: string; myTasksOnly?: boolean }) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<any[]>(`/volunteers/tasks?${qs}`);
  },
  createTask: (data: any) =>
    request<any>('/volunteers/tasks', { method: 'POST', body: JSON.stringify(data) }),
  updateTask: (id: string, data: any) =>
    request<any>(`/volunteers/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  getWorkload: () =>
    request<any[]>('/volunteers/workload'),
  listCampaigns: () =>
    request<any[]>('/volunteers/campaigns'),
  createCampaign: (data: any) =>
    request<any>('/volunteers/campaigns', { method: 'POST', body: JSON.stringify(data) }),
  donateToCampaign: (campaignId: string, data: any) =>
    request<any>(`/volunteers/campaigns/${campaignId}/donate`, { method: 'POST', body: JSON.stringify(data) }),
  listExpenseClaims: (params?: { status?: string; myClaimsOnly?: boolean }) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<any[]>(`/volunteers/expenses?${qs}`);
  },
  submitExpense: (data: any) =>
    request<any>('/volunteers/expenses', { method: 'POST', body: JSON.stringify(data) }),
  reviewExpense: (id: string, data: { status: 'APPROVED' | 'REJECTED'; reviewNotes: string }) =>
    request<any>(`/volunteers/expenses/${id}/review`, { method: 'POST', body: JSON.stringify(data) }),

  // Finance & Ledger
  listTransactions: (params?: any) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<any[]>(`/finance/transactions?${qs}`);
  },
  getFinancialSummary: (params?: any) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<any>(`/finance/summary?${qs}`);
  },
  createTransaction: (data: any) =>
    request<any>('/finance/transactions', { method: 'POST', body: JSON.stringify(data) }),
  reverseTransaction: (id: string, reason: string) =>
    request<any>(`/finance/transactions/${id}/reverse`, { method: 'POST', body: JSON.stringify({ reason }) }),
  listBudgets: () =>
    request<any[]>('/finance/budgets'),
  createOrUpdateBudget: (data: any) =>
    request<any>('/finance/budgets', { method: 'POST', body: JSON.stringify(data) }),

  // Analytics & Dashboard
  getDashboardMetrics: () =>
    request<any>('/analytics/dashboard'),
  exportCsvUrl: (type: 'members' | 'transactions' | 'tickets') =>
    `/api/analytics/export/${type}`,

  // AI Copilot
  queryCopilot: (prompt: string, intent = 'general') =>
    request<any>('/ai/query', { method: 'POST', body: JSON.stringify({ prompt, intent }) }),

  // Audit Logs
  listAuditLogs: (params?: any) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<any[]>(`/audit-logs?${qs}`);
  },

  // Notifications
  listNotifications: () =>
    request<{ notifications: any[]; unreadCount: number }>('/notifications'),
  markNotificationRead: (id: string) =>
    request<any>(`/notifications/${id}/read`, { method: 'PATCH' }),
};
