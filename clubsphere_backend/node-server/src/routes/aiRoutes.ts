import { Router } from 'express';
import { askCopilot } from '../controllers/aiController.js';
import { requireAuth, requireOrg } from '../middleware/auth.js';

const router = Router();

router.use(requireAuth, requireOrg);

router.post('/query', askCopilot);

export default router;
