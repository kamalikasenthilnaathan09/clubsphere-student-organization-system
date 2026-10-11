import { Router } from 'express';
import {
  listProducts,
  createProduct,
  adjustVariantStock,
  checkoutMerchandiseOrder,
  listUserOrders,
  getLowStockAlerts,
} from '../controllers/merchController.js';
import { requireAuth, requireOrg, requireRoles } from '../middleware/auth.js';

const router = Router();

router.use(requireAuth, requireOrg);

router.get('/', listProducts);
router.get('/my-orders', listUserOrders);
router.get('/low-stock', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), getLowStockAlerts);
router.post('/', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), createProduct);
router.post('/variants/:variantId/adjust', requireRoles(['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER']), adjustVariantStock);
router.post('/checkout', checkoutMerchandiseOrder);

export default router;
