import { Router } from 'express';
import {
  listMembers,
  updateMember,
  verifyMemberStatus,
  sendRenewalReminder,
  importMembersCsv,
  listMembershipPlans,
  createMembershipPlan,
  subscribeMembership,
} from '../controllers/memberController.js';
import { requireAuth, requireOrg, requireRoles } from '../middleware/auth.js';

const router = Router();

router.use(requireAuth, requireOrg);

router.get('/', listMembers);
router.patch('/:id', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN']), updateMember);
router.get('/verify', verifyMemberStatus);
router.post('/:id/remind', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), sendRenewalReminder);
router.post('/import-csv', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN']), importMembersCsv);

router.get('/plans', listMembershipPlans);
router.post('/plans', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), createMembershipPlan);
router.post('/subscribe', subscribeMembership);

export default router;
