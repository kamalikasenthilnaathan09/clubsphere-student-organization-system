import { Request, Response } from 'express';
import { z } from 'zod';
import prisma from '../lib/prisma.js';
import { recordAuditLog } from '../middleware/audit.js';

const productCreateSchema = z.object({
  name: z.string().min(2),
  description: z.string().min(5),
  category: z.string().default('APPAREL'),
  basePrice: z.number().min(0),
  memberDiscountPercent: z.number().min(0).max(100).default(0),
  imageUrl: z.string().optional(),
  variants: z.array(
    z.object({
      sku: z.string().min(2),
      size: z.string().optional(),
      color: z.string().optional(),
      stockQuantity: z.number().int().min(0),
      lowStockThreshold: z.number().int().min(0).default(5),
    })
  ).min(1),
});

const checkoutSchema = z.object({
  items: z.array(
    z.object({
      productId: z.string(),
      variantId: z.string(),
      quantity: z.number().int().min(1).max(20),
    })
  ).min(1),
  idempotencyKey: z.string().optional(),
});

const stockAdjustSchema = z.object({
  quantityChange: z.number().int(),
  reason: z.enum(['RESTOCK', 'ADJUSTMENT', 'SPOILAGE', 'RETURN']),
  reference: z.string().optional(),
});

export async function listProducts(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { category, search, activeOnly } = req.query;

  const whereClause: any = { organizationId: orgId };

  if (activeOnly !== 'false') {
    whereClause.isActive = true;
  }
  if (category && typeof category === 'string' && category !== 'ALL') {
    whereClause.category = category;
  }
  if (search && typeof search === 'string') {
    whereClause.OR = [
      { name: { contains: search } },
      { description: { contains: search } },
    ];
  }

  const products = await prisma.merchandiseProduct.findMany({
    where: whereClause,
    include: {
      variants: {
        orderBy: { size: 'asc' },
      },
    },
    orderBy: { createdAt: 'desc' },
  });

  res.json(products);
}

export async function createProduct(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const data = productCreateSchema.parse(req.body);

  const product = await prisma.$transaction(async (tx) => {
    const created = await tx.merchandiseProduct.create({
      data: {
        organizationId: orgId,
        name: data.name,
        description: data.description,
        category: data.category,
        basePrice: data.basePrice,
        memberDiscountPercent: data.memberDiscountPercent,
        imageUrl: data.imageUrl || null,
        isActive: true,
        variants: {
          create: data.variants.map((v) => ({
            sku: v.sku,
            size: v.size || null,
            color: v.color || null,
            stockQuantity: v.stockQuantity,
            lowStockThreshold: v.lowStockThreshold,
          })),
        },
      },
      include: { variants: true },
    });

    // Record initial inventory movements
    for (const v of created.variants) {
      if (v.stockQuantity > 0) {
        await tx.inventoryMovement.create({
          data: {
            variantId: v.id,
            quantityChange: v.stockQuantity,
            previousStock: 0,
            newStock: v.stockQuantity,
            reason: 'INITIAL',
            reference: 'INITIAL_STOCK_ENTRY',
          },
        });
      }
    }

    return created;
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'MERCHANDISE_PRODUCT_CREATED',
      entityType: 'MerchandiseProduct',
      entityId: product.id,
      details: { name: product.name, variantCount: product.variants.length },
    });
  }

  res.status(201).json(product);
}

export async function adjustVariantStock(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { variantId } = req.params;
  const data = stockAdjustSchema.parse(req.body);

  const variant = await prisma.productVariant.findUnique({
    where: { id: variantId },
    include: { product: true },
  });

  if (!variant || variant.product.organizationId !== orgId) {
    res.status(404).json({ error: 'Variant not found' });
    return;
  }

  const previousStock = variant.stockQuantity;
  const newStock = previousStock + data.quantityChange;

  if (newStock < 0) {
    res.status(400).json({ error: `Cannot reduce stock below 0. Current stock is ${previousStock}.` });
    return;
  }

  const updated = await prisma.$transaction(async (tx) => {
    const updatedVar = await tx.productVariant.update({
      where: { id: variantId },
      data: { stockQuantity: newStock },
    });

    const movement = await tx.inventoryMovement.create({
      data: {
        variantId,
        quantityChange: data.quantityChange,
        previousStock,
        newStock,
        reason: data.reason,
        reference: data.reference || null,
      },
    });

    return { updatedVar, movement };
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'INVENTORY_ADJUSTED',
      entityType: 'ProductVariant',
      entityId: variantId,
      details: {
        sku: variant.sku,
        change: data.quantityChange,
        previousStock,
        newStock,
        reason: data.reason,
      },
    });
  }

  res.json({
    success: true,
    variant: updated.updatedVar,
    movement: updated.movement,
  });
}

export async function checkoutMerchandiseOrder(req: Request, res: Response): Promise<void> {
  try {
    const orgId = req.organizationId!;
    const userId = req.user!.id;
    const data = checkoutSchema.parse(req.body);

  // Idempotency check
  if (data.idempotencyKey) {
    const existing = await prisma.order.findUnique({
      where: { idempotencyKey: data.idempotencyKey },
      include: { items: true, payment: true },
    });
    if (existing) {
      res.json({
        success: true,
        message: 'Idempotent order playback',
        order: existing,
      });
      return;
    }
  }

  // Check user active membership discount
  const membership = await prisma.organizationMembership.findFirst({
    where: { userId, organizationId: orgId, status: 'ACTIVE' },
  });
  const isMember = Boolean(membership && (!membership.expiryDate || new Date(membership.expiryDate) > new Date()));

  // Atomic checkout transaction
  const result = await prisma.$transaction(async (tx) => {
    let subtotal = 0;
    let totalDiscount = 0;
    const orderItemsData = [];

    for (const item of data.items) {
      const variant = await tx.productVariant.findUnique({
        where: { id: item.variantId },
        include: { product: true },
      });

      if (!variant) throw new Error(`Product variant ${item.variantId} not found`);
      if (variant.product.organizationId !== orgId) throw new Error('Product not part of this organization');
      if (variant.stockQuantity < item.quantity) {
        throw new Error(`Insufficient stock for ${variant.product.name} (${variant.size || 'One Size'}). Only ${variant.stockQuantity} remaining.`);
      }

      // Deduct stock atomically
      const previousStock = variant.stockQuantity;
      const newStock = previousStock - item.quantity;

      await tx.productVariant.update({
        where: { id: variant.id },
        data: { stockQuantity: newStock },
      });

      // Record inventory movement
      await tx.inventoryMovement.create({
        data: {
          variantId: variant.id,
          quantityChange: -item.quantity,
          previousStock,
          newStock,
          reason: 'SALE',
          reference: `ORD-${Date.now().toString().slice(-6)}`,
        },
      });

      const unitPrice = variant.product.basePrice;
      const itemSubtotal = unitPrice * item.quantity;
      const itemDiscount = isMember ? (itemSubtotal * (variant.product.memberDiscountPercent / 100)) : 0;
      const itemFinalTotal = itemSubtotal - itemDiscount;

      subtotal += itemSubtotal;
      totalDiscount += itemDiscount;

      orderItemsData.push({
        productId: variant.productId,
        variantId: variant.id,
        quantity: item.quantity,
        unitPrice,
        totalPrice: itemFinalTotal,
      });
    }

    const totalAmount = Number((subtotal - totalDiscount).toFixed(2));
    const orderNumber = `ORD-SKY-${Date.now().toString().slice(-6)}-${Math.floor(Math.random() * 900 + 100)}`;

    const order = await tx.order.create({
      data: {
        organizationId: orgId,
        userId,
        orderNumber,
        subtotal,
        discount: totalDiscount,
        totalAmount,
        status: 'PAID',
        paymentStatus: 'PAID',
        idempotencyKey: data.idempotencyKey || null,
        items: {
          create: orderItemsData,
        },
      },
      include: { items: true },
    });

    const payment = await tx.payment.create({
      data: {
        organizationId: orgId,
        orderId: order.id,
        amount: totalAmount,
        currency: 'USD',
        provider: 'DEMO_PAYMENT',
        transactionId: `TX-PAY-ORD-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
        status: 'SETTLED',
        isDemo: true,
      },
    });

    // Record into financial ledger
    if (totalAmount > 0) {
      await tx.financialTransaction.create({
        data: {
          organizationId: orgId,
          type: 'INCOME',
          category: 'MERCHANDISE',
          amount: totalAmount,
          currency: 'USD',
          status: 'SETTLED',
          description: `Merchandise order ${orderNumber} (${req.user!.fullName})`,
          reference: orderNumber,
          orderId: order.id,
          createdByUserId: userId,
        },
      });
    }

    return { order, payment, isMember, totalDiscount };
  });

  await prisma.notification.create({
    data: {
      userId,
      title: 'Order Confirmed!',
      message: `Your merchandise order ${result.order.orderNumber} is confirmed. Thank you for supporting the society!`,
      type: 'SUCCESS',
      linkUrl: '/merchandise',
    },
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'MERCHANDISE_ORDER_COMPLETED',
      entityType: 'Order',
      entityId: result.order.id,
      details: {
        orderNumber: result.order.orderNumber,
        totalAmount: result.order.totalAmount,
        memberDiscountSaved: result.totalDiscount,
      },
    });
  }

    res.status(201).json({
      success: true,
      message: 'Merchandise order placed and settled successfully',
      order: result.order,
      payment: result.payment,
      discountSaved: result.totalDiscount,
    });
  } catch (err: any) {
    res.status(400).json({ error: err.message || 'Checkout failed' });
  }
}

export async function listUserOrders(req: Request, res: Response): Promise<void> {
  const userId = req.user!.id;
  const orgId = req.organizationId!;

  const orders = await prisma.order.findMany({
    where: { userId, organizationId: orgId },
    include: {
      items: {
        include: {
          product: true,
          variant: true,
        },
      },
      payment: true,
    },
    orderBy: { createdAt: 'desc' },
  });

  res.json(orders);
}

export async function getLowStockAlerts(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;

  const variants = await prisma.productVariant.findMany({
    where: {
      product: { organizationId: orgId },
      stockQuantity: { lte: 5 },
    },
    include: { product: true },
    orderBy: { stockQuantity: 'asc' },
  });

  res.json(variants);
}
