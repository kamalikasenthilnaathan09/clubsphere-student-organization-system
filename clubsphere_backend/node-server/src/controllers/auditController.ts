import { Request, Response } from 'express';
import prisma from '../lib/prisma.js';

export async function listAuditLogs(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { action, entityType, limit = '50' } = req.query;

  const whereClause: any = { organizationId: orgId };

  if (action && typeof action === 'string' && action !== 'ALL') {
    whereClause.action = action;
  }
  if (entityType && typeof entityType === 'string' && entityType !== 'ALL') {
    whereClause.entityType = entityType;
  }

  const logs = await prisma.auditLog.findMany({
    where: whereClause,
    include: {
      actor: {
        select: { id: true, fullName: true, email: true },
      },
    },
    orderBy: { createdAt: 'desc' },
    take: parseInt(limit as string, 10) || 50,
  });

  const parsed = logs.map((l) => ({
    ...l,
    parsedDetails: (() => {
      try {
        return JSON.parse(l.details);
      } catch {
        return l.details;
      }
    })(),
  }));

  res.json(parsed);
}
