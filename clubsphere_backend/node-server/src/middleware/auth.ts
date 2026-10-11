import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import prisma from '../lib/prisma.js';

const JWT_SECRET = process.env.JWT_SECRET || 'campussphere_dev_super_secret_jwt_key_2026_xyz';

export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  isSuperAdmin: boolean;
  currentOrgId?: string;
  currentRole?: string;
}

declare global {
  namespace Express {
    interface Request {
      user?: AuthUser;
      organizationId?: string;
    }
  }
}

export function generateToken(payload: { id: string; email: string; isSuperAdmin: boolean }): string {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: '7d' });
}

export async function authenticate(req: Request, res: Response, next: NextFunction): Promise<void> {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    next();
    return;
  }

  const token = authHeader.split(' ')[1];
  try {
    const decoded = jwt.verify(token, JWT_SECRET) as { id: string; email: string; isSuperAdmin: boolean };
    const user = await prisma.user.findUnique({
      where: { id: decoded.id },
      select: { id: true, email: true, fullName: true, isSuperAdmin: true },
    });

    if (!user) {
      next();
      return;
    }

    // Determine current organization
    const orgHeader = req.headers['x-organization-id'] as string | undefined;
    let currentOrgId = orgHeader;
    let currentRole = 'MEMBER';

    if (currentOrgId) {
      const membership = await prisma.organizationMembership.findFirst({
        where: { userId: user.id, organizationId: currentOrgId },
      });
      if (membership) {
        currentRole = membership.role;
      } else if (user.isSuperAdmin) {
        currentRole = 'SUPER_ADMIN';
      }
    } else {
      // Find user's first active membership
      const firstMembership = await prisma.organizationMembership.findFirst({
        where: { userId: user.id },
        include: { organization: true },
      });
      if (firstMembership) {
        currentOrgId = firstMembership.organizationId;
        currentRole = firstMembership.role;
      }
    }

    req.user = {
      ...user,
      currentOrgId,
      currentRole,
    };
    req.organizationId = currentOrgId;

    next();
  } catch (err) {
    // Invalid token, continue as unauthenticated
    next();
  }
}

export function requireAuth(req: Request, res: Response, next: NextFunction): void {
  if (!req.user) {
    res.status(401).json({ error: 'Unauthorized: Authentication required' });
    return;
  }
  next();
}

export function requireOrg(req: Request, res: Response, next: NextFunction): void {
  if (!req.user) {
    res.status(401).json({ error: 'Unauthorized: Authentication required' });
    return;
  }

  const orgId = req.headers['x-organization-id'] as string || req.user.currentOrgId;
  if (!orgId) {
    res.status(400).json({ error: 'Organization context required (x-organization-id header)' });
    return;
  }

  req.organizationId = orgId;
  next();
}

export function requireRoles(allowedRoles: string[]) {
  return async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    if (!req.user) {
      res.status(401).json({ error: 'Unauthorized: Authentication required' });
      return;
    }

    if (req.user.isSuperAdmin) {
      next();
      return;
    }

    const orgId = req.organizationId || (req.headers['x-organization-id'] as string) || req.user.currentOrgId;
    if (!orgId) {
      res.status(400).json({ error: 'Organization context missing' });
      return;
    }

    const membership = await prisma.organizationMembership.findFirst({
      where: { userId: req.user.id, organizationId: orgId },
    });

    if (!membership) {
      res.status(403).json({ error: 'Forbidden: You are not a member of this organization' });
      return;
    }

    // Role hierarchy mapping
    const roleRank: Record<string, number> = {
      SUPER_ADMIN: 100,
      CLUB_ADMIN: 90,
      PRESIDENT: 90,
      TREASURER: 80,
      EVENT_MANAGER: 70,
      VOLUNTEER: 50,
      MEMBER: 10,
    };

    const userRank = roleRank[membership.role] || 0;
    const hasRole = allowedRoles.includes(membership.role) || allowedRoles.some((r) => {
      // If endpoint requires TREASURER or EVENT_MANAGER, CLUB_ADMIN can also access
      if ((r === 'TREASURER' || r === 'EVENT_MANAGER') && membership.role === 'CLUB_ADMIN') return true;
      if (r === 'VOLUNTEER' && userRank >= 50) return true;
      return false;
    });

    if (!hasRole && !req.user.isSuperAdmin) {
      res.status(403).json({
        error: `Forbidden: Insufficient permissions. Required one of: ${allowedRoles.join(', ')}. Current role: ${membership.role}`,
      });
      return;
    }

    req.user.currentRole = membership.role;
    req.user.currentOrgId = orgId;
    req.organizationId = orgId;

    next();
  };
}

export function requireSuperAdmin(req: Request, res: Response, next: NextFunction): void {
  if (!req.user || !req.user.isSuperAdmin) {
    res.status(403).json({ error: 'Forbidden: Super administrator privileges required' });
    return;
  }
  next();
}
