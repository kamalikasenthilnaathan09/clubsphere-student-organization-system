import { Request, Response } from 'express';
import prisma from '../lib/prisma.js';

export async function listNotifications(req: Request, res: Response): Promise<void> {
  const userId = req.user!.id;

  const notifications = await prisma.notification.findMany({
    where: { userId },
    orderBy: { createdAt: 'desc' },
    take: 25,
  });

  const unreadCount = await prisma.notification.count({
    where: { userId, isRead: false },
  });

  res.json({ notifications, unreadCount });
}

export async function markNotificationRead(req: Request, res: Response): Promise<void> {
  const userId = req.user!.id;
  const { id } = req.params;

  if (id === 'all') {
    await prisma.notification.updateMany({
      where: { userId, isRead: false },
      data: { isRead: true },
    });
    res.json({ success: true, message: 'All notifications marked as read' });
    return;
  }

  const updated = await prisma.notification.updateMany({
    where: { id, userId },
    data: { isRead: true },
  });

  res.json({ success: true, updated });
}
