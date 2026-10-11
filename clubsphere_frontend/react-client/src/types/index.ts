export type Role = 'SUPER_ADMIN' | 'CLUB_ADMIN' | 'TREASURER' | 'EVENT_MANAGER' | 'VOLUNTEER' | 'MEMBER' | 'STUDENT';

export interface User {
  id: string;
  email: string;
  fullName: string;
  phone?: string;
  avatarUrl?: string;
  isSuperAdmin: boolean;
  currentOrgId?: string;
  currentRole?: Role;
  currentOrganization?: Organization;
  membershipStatus?: string;
  membershipTier?: string;
  activeSubscription?: any;
  memberships?: {
    id: string;
    organizationId: string;
    organizationName: string;
    organizationSlug: string;
    role: Role;
    status: string;
    tier: string;
    expiryDate?: string;
  }[];
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description?: string;
  logoUrl?: string;
  primaryColor?: string;
  currency: string;
  createdAt: string;
  _count?: {
    memberships: number;
    events: number;
    products: number;
  };
}

export interface Member {
  id: string;
  userId: string;
  organizationId: string;
  role: Role;
  status: 'ACTIVE' | 'PENDING' | 'EXPIRED' | 'ARCHIVED';
  tier: string;
  studentId?: string;
  department?: string;
  joinDate: string;
  expiryDate?: string;
  user: {
    id: string;
    fullName: string;
    email: string;
    phone?: string;
    avatarUrl?: string;
  };
  subscriptions?: {
    id: string;
    plan: {
      id: string;
      name: string;
      price: number;
      discountPercentage: number;
    };
    payments?: {
      id: string;
      amount: number;
      paidAt: string;
    }[];
  }[];
}

export interface MembershipPlan {
  id: string;
  name: string;
  description?: string;
  price: number;
  durationMonths: number;
  benefitsList: string[];
  discountPercentage: number;
  isActive: boolean;
}

export interface TicketType {
  id: string;
  eventId: string;
  name: string;
  description?: string;
  memberPrice: number;
  nonMemberPrice: number;
  totalQuantity: number;
  remainingQuantity: number;
}

export interface EventItem {
  id: string;
  organizationId: string;
  title: string;
  description: string;
  category: string;
  venue: string;
  isOnline: boolean;
  meetingUrl?: string;
  bannerUrl?: string;
  startDate: string;
  endDate: string;
  capacity: number;
  registrationOpensAt: string;
  registrationClosesAt: string;
  status: 'DRAFT' | 'PUBLISHED' | 'SOLD_OUT' | 'CLOSED' | 'COMPLETED' | 'CANCELLED';
  budget: number;
  cancellationPolicy?: string;
  organizerInfo?: string;
  ticketTypes: TicketType[];
  _count?: {
    tickets: number;
    checkIns: number;
  };
}

export interface Ticket {
  id: string;
  bookingId: string;
  ticketTypeId: string;
  eventId: string;
  ticketCode: string;
  qrSecret: string;
  qrCodeDataUrl?: string;
  attendeeName: string;
  attendeeEmail: string;
  isCheckedIn: boolean;
  checkedInAt?: string;
  status: 'VALID' | 'USED' | 'CANCELLED';
  event: EventItem;
  ticketType: TicketType;
  booking?: {
    bookingReference: string;
    totalAmount: number;
  };
}

export interface Announcement {
  id: string;
  organizationId: string;
  authorId: string;
  title: string;
  content: string;
  category: 'GENERAL' | 'URGENT' | 'EVENT' | 'ACADEMIC' | 'OPPORTUNITY';
  targetAudience: 'ALL_MEMBERS' | 'ACTIVE_ONLY' | 'VOLUNTEERS' | 'EXECUTIVES';
  status: 'DRAFT' | 'PUBLISHED' | 'SCHEDULED' | 'ARCHIVED';
  publishedAt?: string;
  emailSent: boolean;
  emailRecipientCount: number;
  createdAt: string;
}

export interface ProductVariant {
  id: string;
  productId: string;
  sku: string;
  size?: string;
  color?: string;
  stockQuantity: number;
  lowStockThreshold: number;
}

export interface Product {
  id: string;
  name: string;
  description: string;
  category: string;
  basePrice: number;
  memberDiscountPercent: number;
  imageUrl?: string;
  isActive: boolean;
  variants: ProductVariant[];
}

export interface Campaign {
  id: string;
  title: string;
  description: string;
  goalAmount: number;
  currentAmount: number;
  progressPercent: number;
  startDate: string;
  endDate: string;
  status: 'ACTIVE' | 'COMPLETED' | 'PAUSED';
}

export interface VolunteerTask {
  id: string;
  title: string;
  description: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  status: 'TODO' | 'IN_PROGRESS' | 'BLOCKED' | 'COMPLETED';
  dueDate?: string;
  createdByUserId: string;
  assignments: {
    id: string;
    user: {
      id: string;
      fullName: string;
      email: string;
      avatarUrl?: string;
    };
  }[];
}

export interface ExpenseClaim {
  id: string;
  claimantId: string;
  title: string;
  description: string;
  amount: number;
  category: string;
  receiptUrl?: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  reviewNotes?: string;
  reviewedAt?: string;
  createdAt: string;
  claimant: {
    id: string;
    fullName: string;
    email: string;
  };
  reviewer?: {
    id: string;
    fullName: string;
  };
}

export interface FinancialTransaction {
  id: string;
  type: 'INCOME' | 'EXPENSE';
  category: string;
  amount: number;
  currency: string;
  status: 'SETTLED' | 'PENDING' | 'CANCELLED' | 'REVERSED';
  description: string;
  reference?: string;
  transactionDate: string;
  event?: { id: string; title: string };
  campaign?: { id: string; title: string };
  expenseClaim?: { id: string; title: string; claimant: { fullName: string } };
}

export interface Budget {
  id: string;
  category: string;
  allocatedAmount: number;
  actualSpent: number;
  remaining: number;
  utilizationRate: number;
  isOverBudget: boolean;
  period: string;
  fiscalYear: number;
}

export interface AuditLog {
  id: string;
  action: string;
  entityType: string;
  entityId: string;
  createdAt: string;
  actor: {
    id: string;
    fullName: string;
    email: string;
  };
  parsedDetails?: any;
}
