import prisma from '../lib/prisma.js';

interface AuditParams {
  organizationId: string;
  actorUserId: string;
  action: string;
  entityType: string;
  entityId: string;
  details?: Record<string, any>;
  ipAddress?: string;
}

export async function recordAuditLog(params: AuditParams): Promise<void> {
  try {
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorUserId: params.actorUserId,
        action: params.action,
        entityType: params.entityType,
        entityId: params.entityId,
        details: JSON.stringify(params.details || {}),
        ipAddress: params.ipAddress || null,
      },
    });
  } catch (error) {
    console.error('Failed to write audit log:', error);
  }
}
