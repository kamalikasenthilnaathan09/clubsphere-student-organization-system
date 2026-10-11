import { Router } from 'express';
import { listAuditLogs } from '../controllers/auditController.js';
import { requireAuth, requireOrg, requireRoles } from '../middleware/auth.js';

const router = Router();

router.use(requireAuth, requireOrg);

router.get('/', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), listAuditLogs);

export default router;
