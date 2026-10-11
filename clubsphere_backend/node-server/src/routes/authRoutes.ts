import { Router } from 'express';
import { register, login, getMe, getDemoAccounts, resetDemoData } from '../controllers/authController.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();

router.post('/register', register);
router.post('/login', login);
router.get('/me', requireAuth, getMe);
router.get('/demo-accounts', getDemoAccounts);
router.post('/reset-demo', resetDemoData);

export default router;
