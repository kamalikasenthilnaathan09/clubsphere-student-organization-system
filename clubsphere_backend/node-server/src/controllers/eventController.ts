import { Request, Response } from 'express';
import { z } from 'zod';
import crypto from 'crypto';
import QRCode from 'qrcode';
import prisma from '../lib/prisma.js';
import { recordAuditLog } from '../middleware/audit.js';

export async function attachQrToTicket(ticket: any) {
  try {
    const qrDataUrl = await QRCode.toDataURL(ticket.ticketCode, {
      errorCorrectionLevel: 'M',
      margin: 2,
      width: 256,
      color: {
        dark: '#0f172a',
        light: '#ffffff',
      },
    });
    return {
      ...ticket,
      qrCodeDataUrl: qrDataUrl,
    };
  } catch {
    return {
      ...ticket,
      qrCodeDataUrl: null,
    };
  }
}

const eventCreateSchema = z.object({
  title: z.string().min(2),
  description: z.string().min(5),
  category: z.string().default('GENERAL'),
  venue: z.string().min(2),
  isOnline: z.boolean().default(false),
  meetingUrl: z.string().optional(),
  bannerUrl: z.string().optional(),
  startDate: z.string(),
  endDate: z.string(),
  capacity: z.number().int().min(1),
  registrationOpensAt: z.string(),
  registrationClosesAt: z.string(),
  budget: z.number().min(0).default(0),
  cancellationPolicy: z.string().optional(),
  organizerInfo: z.string().optional(),
  ticketTypes: z.array(
    z.object({
      name: z.string().min(1),
      description: z.string().optional(),
      memberPrice: z.number().min(0),
      nonMemberPrice: z.number().min(0),
      totalQuantity: z.number().int().min(1),
    })
  ).min(1),
});

const bookingSchema = z.object({
  ticketTypeId: z.string(),
  quantity: z.number().int().min(1).max(5).default(1),
  attendeeName: z.string().min(2),
  attendeeEmail: z.string().email(),
  idempotencyKey: z.string().optional(),
});

const checkInSchema = z.object({
  ticketCode: z.string().min(1),
  checkInMethod: z.enum(['QR_SCAN', 'MANUAL']).default('QR_SCAN'),
  notes: z.string().optional(),
});

export async function listEvents(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { status, category, upcomingOnly } = req.query;

  const whereClause: any = { organizationId: orgId };

  if (status && typeof status === 'string' && status !== 'ALL') {
    whereClause.status = status;
  }
  if (category && typeof category === 'string' && category !== 'ALL') {
    whereClause.category = category;
  }
  if (upcomingOnly === 'true') {
    whereClause.endDate = { gte: new Date() };
  }

  const events = await prisma.event.findMany({
    where: whereClause,
    include: {
      ticketTypes: true,
      _count: {
        select: {
          tickets: true,
          checkIns: true,
        },
      },
    },
    orderBy: { startDate: 'asc' },
  });

  res.json(events);
}

export async function getEventDetails(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { id } = req.params;

  const event = await prisma.event.findFirst({
    where: { id, organizationId: orgId },
    include: {
      ticketTypes: true,
      tickets: {
        include: {
          checkIns: true,
        },
      },
      bookings: {
        include: {
          user: { select: { fullName: true, email: true } },
          payment: true,
        },
      },
    },
  });

  if (!event) {
    res.status(404).json({ error: 'Event not found' });
    return;
  }

  // Calculate event statistics
  const confirmedBookings = event.bookings.filter((b) => b.status === 'CONFIRMED');
  const totalRevenue = confirmedBookings.reduce((sum, b) => sum + b.totalAmount, 0);
  const totalTicketsIssued = event.tickets.filter((t) => t.status === 'VALID' || t.status === 'USED').length;
  const totalCheckedIn = event.tickets.filter((t) => t.isCheckedIn).length;
  const attendanceRate = totalTicketsIssued > 0 ? Number(((totalCheckedIn / totalTicketsIssued) * 100).toFixed(1)) : 0;

  res.json({
    event,
    stats: {
      totalRevenue,
      totalTicketsIssued,
      totalCheckedIn,
      attendanceRate,
      remainingCapacity: Math.max(0, event.capacity - totalTicketsIssued),
    },
  });
}

export async function createEvent(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const data = eventCreateSchema.parse(req.body);

  const totalTicketQty = data.ticketTypes.reduce((acc, t) => acc + t.totalQuantity, 0);
  if (totalTicketQty > data.capacity) {
    res.status(400).json({ error: `Total ticket quantity (${totalTicketQty}) cannot exceed venue capacity (${data.capacity})` });
    return;
  }

  const newEvent = await prisma.event.create({
    data: {
      organizationId: orgId,
      title: data.title,
      description: data.description,
      category: data.category,
      venue: data.venue,
      isOnline: data.isOnline,
      meetingUrl: data.meetingUrl || null,
      bannerUrl: data.bannerUrl || null,
      startDate: new Date(data.startDate),
      endDate: new Date(data.endDate),
      capacity: data.capacity,
      registrationOpensAt: new Date(data.registrationOpensAt),
      registrationClosesAt: new Date(data.registrationClosesAt),
      budget: data.budget,
      cancellationPolicy: data.cancellationPolicy || null,
      organizerInfo: data.organizerInfo || null,
      status: 'PUBLISHED',
      ticketTypes: {
        create: data.ticketTypes.map((tt) => ({
          name: tt.name,
          description: tt.description || null,
          memberPrice: tt.memberPrice,
          nonMemberPrice: tt.nonMemberPrice,
          totalQuantity: tt.totalQuantity,
          remainingQuantity: tt.totalQuantity,
        })),
      },
    },
    include: { ticketTypes: true },
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'EVENT_CREATED',
      entityType: 'Event',
      entityId: newEvent.id,
      details: { title: newEvent.title, capacity: newEvent.capacity },
    });
  }

  res.status(201).json(newEvent);
}

export async function updateEventStatus(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { id } = req.params;
  const { status } = req.body;

  const validStatuses = ['DRAFT', 'PUBLISHED', 'SOLD_OUT', 'CLOSED', 'COMPLETED', 'CANCELLED'];
  if (!validStatuses.includes(status)) {
    res.status(400).json({ error: 'Invalid event status' });
    return;
  }

  const updated = await prisma.event.update({
    where: { id },
    data: { status },
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'EVENT_STATUS_UPDATED',
      entityType: 'Event',
      entityId: id,
      details: { newStatus: status },
    });
  }

  res.json(updated);
}

export async function bookEventTicket(req: Request, res: Response): Promise<void> {
  try {
    const orgId = req.organizationId!;
    const userId = req.user!.id;
    const { id: eventId } = req.params;
    const data = bookingSchema.parse(req.body);

    // Check idempotency if key provided
    if (data.idempotencyKey) {
      const existingBooking = await prisma.booking.findUnique({
        where: { idempotencyKey: data.idempotencyKey },
        include: { tickets: true },
      });
      if (existingBooking) {
        const enrichedTickets = await Promise.all(existingBooking.tickets.map(attachQrToTicket));
        res.json({
          success: true,
          message: 'Returning existing booking (Idempotent replay)',
          booking: {
            ...existingBooking,
            tickets: enrichedTickets,
          },
        });
        return;
      }
    }

    // Check user active membership status in organization for member pricing
    const membership = await prisma.organizationMembership.findFirst({
      where: { userId, organizationId: orgId },
    });
    const isMember = membership?.status === 'ACTIVE' && (!membership.expiryDate || new Date(membership.expiryDate) > new Date());

    // Execute booking atomically inside Prisma transaction
    const result = await prisma.$transaction(async (tx) => {
      const event = await tx.event.findFirst({
        where: { id: eventId, organizationId: orgId },
      });

      if (!event) throw new Error('Event not found');
      if (event.status !== 'PUBLISHED') throw new Error(`Event is not open for registration (Status: ${event.status})`);
      if (new Date() < new Date(event.registrationOpensAt)) throw new Error('Registration has not opened yet');
      if (new Date() > new Date(event.registrationClosesAt)) throw new Error('Registration has closed');

      const ticketType = await tx.ticketType.findFirst({
        where: { id: data.ticketTypeId, eventId },
      });

      if (!ticketType) throw new Error('Ticket type not found');
      if (ticketType.remainingQuantity < data.quantity) {
        throw new Error(`Insufficient tickets remaining. Only ${ticketType.remainingQuantity} left.`);
      }

      // Check overall event capacity
      const currentValidTicketsCount = await tx.ticket.count({
        where: { eventId, status: { in: ['VALID', 'USED'] } },
      });

      if (currentValidTicketsCount + data.quantity > event.capacity) {
        throw new Error(`Event has reached maximum seat capacity (${event.capacity}).`);
      }

      // Deduct ticket remaining inventory atomically
      await tx.ticketType.update({
        where: { id: ticketType.id },
        data: { remainingQuantity: ticketType.remainingQuantity - data.quantity },
      });

      // Check if tickets now 0
      if (ticketType.remainingQuantity - data.quantity === 0) {
        // Check if all ticket types sold out
        const allTypes = await tx.ticketType.findMany({ where: { eventId } });
        const totalRemaining = allTypes.reduce((acc, t) => acc + (t.id === ticketType.id ? 0 : t.remainingQuantity), 0);
        if (totalRemaining === 0) {
          await tx.event.update({ where: { id: eventId }, data: { status: 'SOLD_OUT' } });
        }
      }

      const pricePerTicket = isMember ? ticketType.memberPrice : ticketType.nonMemberPrice;
      const totalAmount = pricePerTicket * data.quantity;
      const bookingRef = `BK-${Date.now().toString().slice(-6)}-${Math.floor(Math.random() * 900 + 100)}`;

      const booking = await tx.booking.create({
        data: {
          eventId,
          userId,
          bookingReference: bookingRef,
          totalAmount,
          status: 'CONFIRMED',
          paymentStatus: 'PAID',
          idempotencyKey: data.idempotencyKey || null,
        },
      });

      // Generate Tickets with unpredictable cryptographic QR secrets
      const generatedTickets = [];
      for (let i = 0; i < data.quantity; i++) {
        const ticketCode = `TKT-${Math.random().toString(36).substring(2, 7).toUpperCase()}-${Math.floor(Math.random() * 9000 + 1000)}`;
        const qrSecret = crypto.randomBytes(16).toString('hex');

        const ticket = await tx.ticket.create({
          data: {
            bookingId: booking.id,
            ticketTypeId: ticketType.id,
            eventId,
            ticketCode,
            qrSecret,
            attendeeName: data.attendeeName,
            attendeeEmail: data.attendeeEmail,
            status: 'VALID',
            isCheckedIn: false,
          },
        });
        generatedTickets.push(ticket);
      }

      // Record demo payment
      const payment = await tx.payment.create({
        data: {
          organizationId: orgId,
          bookingId: booking.id,
          amount: totalAmount,
          currency: 'USD',
          provider: 'DEMO_PAYMENT',
          transactionId: `TX-PAY-TKT-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
          status: 'SETTLED',
          isDemo: true,
        },
      });

      // Record into financial ledger if totalAmount > 0
      if (totalAmount > 0) {
        await tx.financialTransaction.create({
          data: {
            organizationId: orgId,
            type: 'INCOME',
            category: 'EVENT_TICKETS',
            amount: totalAmount,
            currency: 'USD',
            status: 'SETTLED',
            description: `Ticket booking: ${event.title} (${data.quantity}x ${ticketType.name}) - ${data.attendeeName}`,
            reference: bookingRef,
            eventId,
            createdByUserId: userId,
          },
        });
      }

      return { booking, tickets: generatedTickets, payment, event, isMember, pricePerTicket };
    });

    // Create In-App Notification
    await prisma.notification.create({
      data: {
        userId,
        title: 'Ticket Confirmed!',
        message: `Your booking for "${result.event.title}" is confirmed. Check your QR ticket in your wallet.`,
        type: 'SUCCESS',
        linkUrl: `/events`,
      },
    });

    if (req.user) {
      await recordAuditLog({
        organizationId: orgId,
        actorUserId: req.user.id,
        action: 'EVENT_TICKET_BOOKED',
        entityType: 'Booking',
        entityId: result.booking.id,
        details: {
          event: result.event.title,
          ticketCount: data.quantity,
          totalPaid: result.booking.totalAmount,
          isMemberDiscountApplied: isMember,
        },
      });
    }

    const ticketsWithQr = await Promise.all(result.tickets.map(attachQrToTicket));

    res.status(201).json({
      success: true,
      message: 'Tickets booked and confirmed successfully',
      booking: result.booking,
      tickets: ticketsWithQr,
      payment: result.payment,
      isMemberDiscountApplied: result.isMember,
      pricePerTicket: result.pricePerTicket,
    });
  } catch (err: any) {
    const message = err.message || 'Failed to book event ticket';
    res.status(400).json({
      success: false,
      error: message,
      message,
    });
  }
}

export async function validateAndCheckInTicket(req: Request, res: Response): Promise<void> {
  try {
    const orgId = req.organizationId!;
    const staffUserId = req.user!.id;
    const { id: eventId } = req.params;
    const data = checkInSchema.parse(req.body);

    let rawCode = data.ticketCode.trim();
    // Parse if QR scanner output is a JSON payload
    try {
      if (rawCode.startsWith('{') && rawCode.endsWith('}')) {
        const parsed = JSON.parse(rawCode);
        rawCode = parsed.ticketCode || parsed.code || parsed.qrSecret || parsed.id || rawCode;
      }
    } catch {
      // Continue with raw code
    }

    const cleanCode = rawCode.trim();
    const upperCode = cleanCode.toUpperCase();

    // Find ticket by ticketCode, qrSecret, or UUID id
    const ticket = await prisma.ticket.findFirst({
      where: {
        OR: [
          { ticketCode: upperCode },
          { ticketCode: cleanCode },
          { qrSecret: cleanCode },
          { id: cleanCode },
        ],
      },
      include: {
        event: true,
        ticketType: true,
        booking: { include: { user: true } },
      },
    });

    if (!ticket) {
      res.status(404).json({
        success: false,
        validationStatus: 'INVALID_TICKET',
        message: '❌ Ticket Not Found: The scanned code is not registered in the system.',
      });
      return;
    }

    // Check event association
    if (ticket.eventId !== eventId) {
      res.status(400).json({
        success: false,
        validationStatus: 'WRONG_EVENT',
        message: `⚠️ Wrong Event: This ticket is issued for "${ticket.event.title}", not the current event!`,
        ticketDetails: {
          attendeeName: ticket.attendeeName,
          issuedForEvent: ticket.event.title,
        },
      });
      return;
    }

    // Check if already checked in (CRITICAL RULE: Prevent duplicate check-in)
    if (ticket.isCheckedIn || ticket.status === 'USED') {
      res.status(409).json({
        success: false,
        validationStatus: 'ALREADY_USED',
        message: `🚫 Already Used: This ticket was already checked in on ${ticket.checkedInAt ? new Date(ticket.checkedInAt).toLocaleString() : 'earlier today'}!`,
        ticketDetails: {
          ticketCode: ticket.ticketCode,
          attendeeName: ticket.attendeeName,
          checkedInAt: ticket.checkedInAt,
          checkedInBy: ticket.checkedInByUserId,
        },
      });
      return;
    }

    if (ticket.status === 'CANCELLED') {
      res.status(400).json({
        success: false,
        validationStatus: 'CANCELLED_TICKET',
        message: '❌ Cancelled Ticket: This ticket was previously cancelled and voided.',
      });
      return;
    }

    // Atomically perform check-in
    const updatedTicket = await prisma.$transaction(async (tx) => {
      const checkInRecord = await tx.checkIn.create({
        data: {
          ticketId: ticket.id,
          eventId,
          checkedInByUserId: staffUserId,
          checkedInAt: new Date(),
          checkInMethod: data.checkInMethod,
          notes: data.notes || null,
        },
      });

      const updated = await tx.ticket.update({
        where: { id: ticket.id },
        data: {
          isCheckedIn: true,
          checkedInAt: new Date(),
          checkedInByUserId: staffUserId,
          status: 'USED',
        },
        include: { event: true, ticketType: true },
      });

      return { updated, checkInRecord };
    });

    await recordAuditLog({
      organizationId: orgId,
      actorUserId: staffUserId,
      action: 'TICKET_CHECKED_IN',
      entityType: 'Ticket',
      entityId: ticket.id,
      details: {
        attendee: ticket.attendeeName,
        ticketCode: ticket.ticketCode,
        method: data.checkInMethod,
      },
    });

    const ticketWithQr = await attachQrToTicket(updatedTicket.updated);

    res.json({
      success: true,
      validationStatus: 'SUCCESS',
      message: `✅ Admission Approved: Welcome ${ticket.attendeeName}!`,
      ticket: ticketWithQr,
      checkInTime: updatedTicket.checkInRecord.checkedInAt,
    });
  } catch (err: any) {
    res.status(400).json({
      success: false,
      validationStatus: 'ERROR',
      message: err.message || 'Ticket check-in validation failed',
    });
  }
}

export async function cancelBooking(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const userId = req.user!.id;
  const { bookingId } = req.params;

  const booking = await prisma.booking.findFirst({
    where: { id: bookingId },
    include: { tickets: true, event: true },
  });

  if (!booking) {
    res.status(404).json({ error: 'Booking not found' });
    return;
  }

  // Authorization: user must own booking or be CLUB_ADMIN / EVENT_MANAGER
  const isOwner = booking.userId === userId;
  const canManage = req.user!.currentRole && ['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER'].includes(req.user!.currentRole);

  if (!isOwner && !canManage) {
    res.status(403).json({ error: 'Forbidden: You cannot cancel this booking' });
    return;
  }

  if (booking.status === 'CANCELLED') {
    res.status(400).json({ error: 'Booking is already cancelled' });
    return;
  }

  // Check if any tickets have already been checked in
  const hasUsedTickets = booking.tickets.some((t) => t.isCheckedIn || t.status === 'USED');
  if (hasUsedTickets) {
    res.status(400).json({ error: 'Cannot cancel booking: One or more tickets have already been checked in at the event' });
    return;
  }

  // Atomic cancellation & inventory restoration
  await prisma.$transaction(async (tx) => {
    // 1. Mark booking cancelled
    await tx.booking.update({
      where: { id: booking.id },
      data: { status: 'CANCELLED', paymentStatus: 'REFUNDED' },
    });

    // 2. Mark tickets cancelled
    for (const t of booking.tickets) {
      await tx.ticket.update({
        where: { id: t.id },
        data: { status: 'CANCELLED' },
      });

      // Restore inventory
      await tx.ticketType.update({
        where: { id: t.ticketTypeId },
        data: { remainingQuantity: { increment: 1 } },
      });
    }

    // 3. Reverse financial ledger entry if paid
    if (booking.totalAmount > 0) {
      await tx.financialTransaction.create({
        data: {
          organizationId: orgId,
          type: 'EXPENSE',
          category: 'REFUND',
          amount: booking.totalAmount,
          currency: 'USD',
          status: 'SETTLED',
          description: `Refund for cancelled booking ${booking.bookingReference} (${booking.event.title})`,
          reference: `REF-${booking.bookingReference}`,
          eventId: booking.eventId,
          createdByUserId: userId,
        },
      });
    }
  });

  await recordAuditLog({
    organizationId: orgId,
    actorUserId: userId,
    action: 'BOOKING_CANCELLED_INVENTORY_RESTORED',
    entityType: 'Booking',
    entityId: booking.id,
    details: { bookingRef: booking.bookingReference, ticketsRestored: booking.tickets.length },
  });

  res.json({
    success: true,
    message: 'Booking cancelled and ticket inventory successfully restored',
  });
}

export async function getUserTickets(req: Request, res: Response): Promise<void> {
  const userId = req.user!.id;
  const orgId = req.organizationId!;

  const tickets = await prisma.ticket.findMany({
    where: {
      booking: { userId },
      event: { organizationId: orgId },
    },
    include: {
      event: true,
      ticketType: true,
      booking: true,
    },
    orderBy: { createdAt: 'desc' },
  });

  const ticketsWithQr = await Promise.all(tickets.map(attachQrToTicket));
  res.json(ticketsWithQr);
}

export async function getTicketQrCode(req: Request, res: Response): Promise<void> {
  const { ticketId } = req.params;
  const ticket = await prisma.ticket.findUnique({
    where: { id: ticketId },
    include: { event: true },
  });

  if (!ticket) {
    res.status(404).json({ error: 'Ticket not found' });
    return;
  }

  const qrDataUrl = await QRCode.toDataURL(ticket.ticketCode, {
    errorCorrectionLevel: 'M',
    margin: 2,
    width: 320,
    color: {
      dark: '#0f172a',
      light: '#ffffff',
    },
  });

  res.json({
    ticketId: ticket.id,
    ticketCode: ticket.ticketCode,
    qrSecret: ticket.qrSecret,
    qrCodeDataUrl: qrDataUrl,
    eventTitle: ticket.event.title,
    attendeeName: ticket.attendeeName,
  });
}
