import { Router } from 'express';
import { getDashboardMetrics, exportCsvData } from '../controllers/analyticsController.js';
import { requireAuth, requireOrg, requireRoles } from '../middleware/auth.js';

const router = Router();

router.use(requireAuth, requireOrg);

router.get('/dashboard', getDashboardMetrics);
router.get('/export/:type', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), exportCsvData);

export default router;
