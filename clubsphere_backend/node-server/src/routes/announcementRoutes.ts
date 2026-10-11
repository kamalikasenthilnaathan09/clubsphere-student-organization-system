import { Router } from 'express';
import { listAnnouncements, createAnnouncement, archiveAnnouncement } from '../controllers/announcementController.js';
import { requireAuth, requireOrg, requireRoles } from '../middleware/auth.js';

const router = Router();

router.use(requireAuth, requireOrg);

router.get('/', listAnnouncements);
router.post('/', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER']), createAnnouncement);
router.patch('/:id/archive', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN']), archiveAnnouncement);

export default router;
