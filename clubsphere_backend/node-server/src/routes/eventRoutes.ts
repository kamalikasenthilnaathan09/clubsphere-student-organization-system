import { Router } from 'express';
import {
  listEvents,
  getEventDetails,
  createEvent,
  updateEventStatus,
  bookEventTicket,
  validateAndCheckInTicket,
  cancelBooking,
  getUserTickets,
  getTicketQrCode,
} from '../controllers/eventController.js';
import { requireAuth, requireOrg, requireRoles } from '../middleware/auth.js';

const router = Router();

router.use(requireAuth, requireOrg);

router.get('/', listEvents);
router.get('/my-tickets', getUserTickets);
router.get('/tickets/:ticketId/qr', getTicketQrCode);
router.get('/:id', getEventDetails);
router.post('/', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER']), createEvent);
router.patch('/:id/status', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER']), updateEventStatus);
router.post('/:id/book', bookEventTicket);
router.post('/:id/check-in', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER', 'VOLUNTEER']), validateAndCheckInTicket);
router.post('/bookings/:bookingId/cancel', cancelBooking);

export default router;
