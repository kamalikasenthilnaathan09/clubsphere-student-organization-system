import { Router } from 'express';
import { getCurrentOrg, listOrganizations, updateOrgSettings, provisionOrganization } from '../controllers/orgController.js';
import { requireAuth, requireOrg, requireRoles } from '../middleware/auth.js';

const router = Router();

router.get('/', listOrganizations);
router.get('/current', requireAuth, requireOrg, getCurrentOrg);
router.patch('/settings', requireAuth, requireOrg, requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN']), updateOrgSettings);
router.post('/provision', requireAuth, provisionOrganization);

export default router;
