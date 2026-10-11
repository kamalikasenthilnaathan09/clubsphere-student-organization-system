import { Router } from 'express';
import {
  listTasks,
  createTask,
  updateTask,
  getVolunteerWorkload,
  listCampaigns,
  createCampaign,
  recordDonation,
  submitExpenseClaim,
  reviewExpenseClaim,
  listExpenseClaims,
} from '../controllers/volunteerController.js';
import { requireAuth, requireOrg, requireRoles } from '../middleware/auth.js';

const router = Router();

router.use(requireAuth, requireOrg);

// Tasks
router.get('/tasks', listTasks);
router.post('/tasks', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER']), createTask);
router.patch('/tasks/:id', updateTask);
router.get('/workload', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER']), getVolunteerWorkload);

// Campaigns & Donations
router.get('/campaigns', listCampaigns);
router.post('/campaigns', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), createCampaign);
router.post('/campaigns/:id/donate', recordDonation);

// Expense Claims
router.get('/expenses', listExpenseClaims);
router.post('/expenses', submitExpenseClaim);
router.post('/expenses/:id/review', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), reviewExpenseClaim);

export default router;
