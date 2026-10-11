import { Request, Response } from 'express';
import { z } from 'zod';
import prisma from '../lib/prisma.js';
import { recordAuditLog } from '../middleware/audit.js';
import { sendNotificationEmail } from '../services/emailService.js';

const announcementSchema = z.object({
  title: z.string().min(3),
  content: z.string().min(10),
  category: z.enum(['GENERAL', 'URGENT', 'EVENT', 'ACADEMIC', 'OPPORTUNITY']).default('GENERAL'),
  targetAudience: z.enum(['ALL_MEMBERS', 'ACTIVE_ONLY', 'VOLUNTEERS', 'EXECUTIVES']).default('ALL_MEMBERS'),
  status: z.enum(['DRAFT', 'PUBLISHED', 'SCHEDULED', 'ARCHIVED']).default('PUBLISHED'),
  scheduledFor: z.string().optional(),
  sendEmailNotification: z.boolean().default(false),
});

export async function listAnnouncements(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { category, audience } = req.query;

  const whereClause: any = {
    organizationId: orgId,
    status: 'PUBLISHED',
  };

  if (category && typeof category === 'string' && category !== 'ALL') {
    whereClause.category = category;
  }
  if (audience && typeof audience === 'string' && audience !== 'ALL') {
    whereClause.targetAudience = audience;
  }

  const announcements = await prisma.announcement.findMany({
    where: whereClause,
    orderBy: { publishedAt: 'desc' },
  });

  res.json(announcements);
}

export async function createAnnouncement(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const authorId = req.user!.id;
  const data = announcementSchema.parse(req.body);

  let emailSent = false;
  let emailRecipientCount = 0;

  if (data.sendEmailNotification && data.status === 'PUBLISHED') {
    // Look up target audience member count
    const memberAudienceCount = await prisma.organizationMembership.count({
      where: {
        organizationId: orgId,
        status: data.targetAudience === 'ACTIVE_ONLY' ? 'ACTIVE' : undefined,
      },
    });

    const emailRes = await sendNotificationEmail({
      to: `members@${orgId}.campussphere.edu`,
      subject: `[${data.category}] ${data.title}`,
      body: data.content,
      category: data.category,
      isAnnouncement: true,
    });

    emailSent = emailRes.success;
    emailRecipientCount = memberAudienceCount || 1;
  }

  const announcement = await prisma.announcement.create({
    data: {
      organizationId: orgId,
      authorId,
      title: data.title,
      content: data.content,
      category: data.category,
      targetAudience: data.targetAudience,
      status: data.status,
      scheduledFor: data.scheduledFor ? new Date(data.scheduledFor) : null,
      publishedAt: data.status === 'PUBLISHED' ? new Date() : null,
      emailSent,
      emailRecipientCount,
    },
  });

  // Also create in-app notification for active members in the org
  const memberships = await prisma.organizationMembership.findMany({
    where: { organizationId: orgId, status: 'ACTIVE' },
    select: { userId: true },
    take: 50,
  });

  for (const m of memberships) {
    await prisma.notification.create({
      data: {
        userId: m.userId,
        title: `📢 ${data.title}`,
        message: data.content.slice(0, 120) + (data.content.length > 120 ? '...' : ''),
        type: data.category === 'URGENT' ? 'ALERT' : 'INFO',
        linkUrl: '/announcements',
      },
    });
  }

  await recordAuditLog({
    organizationId: orgId,
    actorUserId: authorId,
    action: 'ANNOUNCEMENT_PUBLISHED',
    entityType: 'Announcement',
    entityId: announcement.id,
    details: {
      title: announcement.title,
      category: announcement.category,
      emailSent,
      emailRecipientCount,
    },
  });

  res.status(201).json(announcement);
}

export async function archiveAnnouncement(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { id } = req.params;

  const updated = await prisma.announcement.update({
    where: { id },
    data: { status: 'ARCHIVED' },
  });

  await recordAuditLog({
    organizationId: orgId,
    actorUserId: req.user!.id,
    action: 'ANNOUNCEMENT_ARCHIVED',
    entityType: 'Announcement',
    entityId: id,
    details: { title: updated.title },
  });

  res.json(updated);
}
