import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { Product, ProductVariant } from '../types';
import { Modal } from '../components/common/Modal';
import confetti from 'canvas-confetti';
import {
  ShoppingBag,
  Plus,
  ShoppingCart,
  AlertTriangle,
  CheckCircle,
  Tag,
  Package,
  Layers,
  ArrowRight,
} from 'lucide-react';

export const MerchandisePage: React.FC = () => {
  const { role, user } = useAuth();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'STORE' | 'ORDERS' | 'INVENTORY'>('STORE');

  // Modals state
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null);
  const [orderQty, setOrderQty] = useState(1);

  // Cart
  const [cart, setCart] = useState<{ product: Product; variant: ProductVariant; quantity: number }[]>([]);
  const [isCartOpen, setIsCartOpen] = useState(false);

  // Stock adjust modal
  const [adjustModalVariant, setAdjustModalVariant] = useState<any>(null);
  const [adjustQty, setAdjustQty] = useState(10);
  const [adjustReason, setAdjustReason] = useState<'RESTOCK' | 'ADJUSTMENT' | 'SPOILAGE'>('RESTOCK');

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const canManageInventory = ['CLUB_ADMIN', 'SUPER_ADMIN', 'TREASURER'].includes(role);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Queries
  const { data: products = [] } = useQuery<Product[]>({
    queryKey: ['products'],
    queryFn: () => api.listProducts(),
  });

  const { data: orders = [] } = useQuery<any[]>({
    queryKey: ['userOrders'],
    queryFn: () => api.listUserOrders(),
  });

  const { data: lowStockVariants = [] } = useQuery<any[]>({
    queryKey: ['lowStock'],
    queryFn: () => api.getLowStockAlerts(),
    enabled: canManageInventory,
  });

  // Add to cart
  const handleAddToCart = () => {
    if (!selectedProduct || !selectedVariant) return;

    if (selectedVariant.stockQuantity < orderQty) {
      alert(`Only ${selectedVariant.stockQuantity} items in stock!`);
      return;
    }

    setCart((prev) => [
      ...prev,
      { product: selectedProduct, variant: selectedVariant, quantity: orderQty },
    ]);
    setSelectedProduct(null);
    showToast(`Added ${orderQty}x ${selectedProduct.name} (${selectedVariant.size}) to cart!`);
    setIsCartOpen(true);
  };

  // Checkout order
  const handleCheckout = async () => {
    if (cart.length === 0) return;
    try {
      const items = cart.map((c) => ({
        productId: c.product.id,
        variantId: c.variant.id,
        quantity: c.quantity,
      }));

      const res = await api.checkoutOrder({ items });

      confetti({
        particleCount: 80,
        spread: 60,
        origin: { y: 0.6 },
      });

      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['userOrders'] });
      queryClient.invalidateQueries({ queryKey: ['lowStock'] });
      setCart([]);
      setIsCartOpen(false);
      showToast(`Order ${res.order.orderNumber} confirmed and paid!`);
      setActiveTab('ORDERS');
    } catch (err: any) {
      alert(`Checkout error: ${err.message}`);
    }
  };

  // Stock Adjustment
  const handleStockAdjust = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adjustModalVariant) return;

    try {
      await api.adjustStock(adjustModalVariant.id, {
        quantityChange: Number(adjustQty),
        reason: adjustReason,
      });

      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['lowStock'] });
      setAdjustModalVariant(null);
      showToast('Inventory stock level updated successfully!');
    } catch (err: any) {
      alert(`Adjustment error: ${err.message}`);
    }
  };

  const cartSubtotal = cart.reduce((acc, c) => acc + c.product.basePrice * c.quantity, 0);

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 glass-panel bg-navy-900 border border-teal-500/40 text-slate-100 px-4 py-3 rounded-2xl shadow-2xl flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-teal-400" />
          <span className="text-sm font-semibold">{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 flex items-center gap-2.5">
            <ShoppingBag className="w-6 h-6 text-emerald-600" />
            <span>Club Merchandise & Inventory</span>
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Official apparel, drinkware, and accessories with member discounts and atomic inventory control.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsCartOpen(true)}
            className="relative flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-indigo-500/20 hover:opacity-95 transition"
          >
            <ShoppingCart className="w-4 h-4" />
            <span>Cart</span>
            {cart.length > 0 && (
              <span className="bg-amber-400 text-slate-950 font-black text-[10px] w-5 h-5 rounded-full flex items-center justify-center">
                {cart.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => setActiveTab('STORE')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
            activeTab === 'STORE'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200/80'
          }`}
        >
          Product Catalog ({products.length})
        </button>
        <button
          onClick={() => setActiveTab('ORDERS')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
            activeTab === 'ORDERS'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200/80'
          }`}
        >
          My Orders ({orders.length})
        </button>
        {canManageInventory && (
          <button
            onClick={() => setActiveTab('INVENTORY')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTab === 'INVENTORY'
                ? 'bg-teal-600 text-white shadow-sm'
                : 'text-teal-700 hover:text-teal-900 bg-teal-50 hover:bg-teal-100 border border-teal-200'
            }`}
          >
            <Package className="w-3.5 h-3.5" />
            <span>Stock Management & Low Alerts ({lowStockVariants.length})</span>
          </button>
        )}
      </div>

      {/* STORE CATALOG TAB */}
      {activeTab === 'STORE' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {products.map((prod) => {
            const minStock = Math.min(...prod.variants.map((v) => v.stockQuantity));
            const totalStock = prod.variants.reduce((acc, v) => acc + v.stockQuantity, 0);
            const hasDiscount = prod.memberDiscountPercent > 0;

            return (
              <div
                key={prod.id}
                className="glass-panel rounded-2xl border border-brand-500/20 overflow-hidden flex flex-col justify-between glass-panel-hover"
              >
                <div>
                  <div className="h-44 bg-navy-900 relative overflow-hidden">
                    <img
                      src={
                        prod.imageUrl ||
                        'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=600'
                      }
                      alt={prod.name}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute top-3 right-3 flex gap-1">
                      {hasDiscount && (
                        <span className="text-[10px] bg-teal-500 text-navy-950 font-extrabold px-2 py-0.5 rounded-full shadow-md">
                          {prod.memberDiscountPercent}% Member Off
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="p-5">
                    <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">
                      {prod.category}
                    </div>
                    <h2 className="text-base font-bold text-white line-clamp-1">{prod.name}</h2>
                    <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                      {prod.description}
                    </p>

                    <div className="mt-4 flex items-center justify-between">
                      <div>
                        <div className="text-lg font-extrabold text-white">
                          ${prod.basePrice.toFixed(2)}
                        </div>
                        {hasDiscount && (
                          <div className="text-[11px] text-teal-400 font-semibold">
                            Member Price: $
                            {(prod.basePrice * (1 - prod.memberDiscountPercent / 100)).toFixed(2)}
                          </div>
                        )}
                      </div>

                      <div className="text-right">
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            totalStock <= 5
                              ? 'bg-amber-950 text-amber-300 border border-amber-500/30'
                              : 'bg-emerald-950 text-emerald-300 border border-emerald-500/30'
                          }`}
                        >
                          {totalStock <= 5 ? `Low Stock (${totalStock})` : `${totalStock} In Stock`}
                        </span>
                      </div>
                    </div>

                    {/* Sizes preview */}
                    <div className="mt-3 flex items-center gap-1.5 overflow-x-auto">
                      {prod.variants.map((v) => (
                        <span
                          key={v.id}
                          className="px-2 py-0.5 rounded bg-navy-900 border border-slate-700/60 text-[10px] text-slate-300"
                        >
                          {v.size || 'One Size'} ({v.stockQuantity})
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="p-5 pt-0">
                  <button
                    onClick={() => {
                      setSelectedProduct(prod);
                      setSelectedVariant(prod.variants[0] || null);
                      setOrderQty(1);
                    }}
                    disabled={totalStock === 0}
                    className="w-full py-2.5 rounded-xl bg-gradient-to-r from-brand-600 to-teal-600 text-white font-semibold text-xs shadow-md shadow-brand-500/20 hover:opacity-95 disabled:opacity-50 transition"
                  >
                    {totalStock === 0 ? 'Out of Stock' : 'Select Size & Add'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* MY ORDERS TAB */}
      {activeTab === 'ORDERS' && (
        <div className="space-y-4">
          {orders.length === 0 ? (
            <div className="glass-panel p-8 text-center rounded-2xl border border-brand-500/20">
              <ShoppingBag className="w-10 h-10 text-slate-500 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-300">No orders placed yet</p>
            </div>
          ) : (
            orders.map((ord: any) => (
              <div
                key={ord.id}
                className="glass-panel p-5 rounded-2xl border border-brand-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-white text-sm">{ord.orderNumber}</span>
                    <span className="text-[10px] font-bold bg-teal-950 text-teal-300 border border-teal-500/30 px-2 py-0.5 rounded-full uppercase">
                      {ord.status}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    Placed on {new Date(ord.createdAt).toLocaleDateString()}
                  </div>

                  <div className="mt-2 space-y-1">
                    {ord.items?.map((it: any) => (
                      <div key={it.id} className="text-xs text-slate-300">
                        {it.quantity}x {it.product?.name} ({it.variant?.size}) — ${it.totalPrice}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="text-right border-t sm:border-t-0 pt-2 sm:pt-0 border-slate-800">
                  <div className="text-[10px] text-slate-400">Total Settled</div>
                  <div className="text-lg font-extrabold text-teal-400">${ord.totalAmount}</div>
                  {ord.discount > 0 && (
                    <div className="text-[10px] text-slate-400">
                      Saved ${ord.discount.toFixed(2)} with member pass
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* INVENTORY MANAGEMENT TAB (ADMIN / TREASURER) */}
      {activeTab === 'INVENTORY' && (
        <div className="space-y-6">
          {/* Low Stock Alerts */}
          {lowStockVariants.length > 0 && (
            <div className="p-4 rounded-2xl bg-amber-950/40 border border-amber-500/40 text-amber-200 text-xs">
              <div className="flex items-center gap-2 font-bold text-amber-300 text-sm mb-1">
                <AlertTriangle className="w-4 h-4" />
                <span>Urgent: {lowStockVariants.length} Variant(s) Below Safety Threshold</span>
              </div>
              <p>Reorder quantities are recommended to avoid stockouts during major campus festival sales.</p>
            </div>
          )}

          <div className="glass-panel rounded-2xl border border-brand-500/20 overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-navy-900/90 text-slate-400 border-b border-slate-800 uppercase font-semibold">
                <tr>
                  <th className="py-3.5 px-4">Product & SKU</th>
                  <th className="py-3.5 px-4">Variant (Size/Color)</th>
                  <th className="py-3.5 px-4">Available Stock</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {products.flatMap((prod) =>
                  prod.variants.map((v) => (
                    <tr key={v.id} className="hover:bg-navy-900/40">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-white">{prod.name}</div>
                        <div className="font-mono text-[11px] text-slate-400">{v.sku}</div>
                      </td>
                      <td className="py-3 px-4 text-slate-300">{v.size || 'One Size'} / {v.color || 'Standard'}</td>
                      <td className="py-3 px-4 font-bold text-white text-sm">{v.stockQuantity}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            v.stockQuantity <= v.lowStockThreshold
                              ? 'bg-amber-950 text-amber-300 border border-amber-500/30'
                              : 'bg-emerald-950 text-emerald-300 border border-emerald-500/30'
                          }`}
                        >
                          {v.stockQuantity <= v.lowStockThreshold ? 'LOW STOCK' : 'HEALTHY'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => {
                            setAdjustModalVariant({ ...v, productName: prod.name });
                            setAdjustQty(10);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-navy-800 hover:bg-slate-700 text-teal-400 border border-slate-700 font-semibold text-xs"
                        >
                          Adjust Stock
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Product Variant Selector Modal */}
      <Modal
        isOpen={Boolean(selectedProduct)}
        onClose={() => setSelectedProduct(null)}
        title={selectedProduct?.name || ''}
        subtitle="Select size variant and confirm quantity"
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 mb-1">Select Size</label>
            <div className="grid grid-cols-3 gap-2">
              {selectedProduct?.variants.map((v) => (
                <button
                  key={v.id}
                  onClick={() => setSelectedVariant(v)}
                  className={`p-2.5 rounded-xl border text-center transition ${
                    selectedVariant?.id === v.id
                      ? 'bg-brand-600/30 border-brand-400 text-white font-bold'
                      : 'bg-navy-950 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="font-semibold">{v.size || 'Standard'}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">{v.stockQuantity} in stock</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Quantity</label>
            <input
              type="number"
              min={1}
              max={selectedVariant?.stockQuantity || 1}
              value={orderQty}
              onChange={(e) => setOrderQty(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setSelectedProduct(null)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              onClick={handleAddToCart}
              className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold"
            >
              Add to Cart
            </button>
          </div>
        </div>
      </Modal>

      {/* Cart Drawer / Checkout Modal */}
      <Modal
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        title="Your Cart & Checkout"
        subtitle="Review selected merchandise. Payments are processed in demo sandbox mode."
      >
        <div className="space-y-4 text-xs">
          {cart.length === 0 ? (
            <p className="text-center py-6 text-slate-400">Cart is empty.</p>
          ) : (
            <>
              <div className="divide-y divide-slate-800 space-y-2">
                {cart.map((item, idx) => (
                  <div key={idx} className="pt-2 flex justify-between items-center">
                    <div>
                      <div className="font-semibold text-white">{item.product.name}</div>
                      <div className="text-[11px] text-slate-400">
                        Size: {item.variant.size} • Qty: {item.quantity}
                      </div>
                    </div>
                    <div className="font-bold text-white">
                      ${(item.product.basePrice * item.quantity).toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-3 rounded-xl bg-navy-950 border border-slate-800 flex justify-between items-center text-sm font-bold text-teal-400">
                <span>Total Amount:</span>
                <span>${cartSubtotal.toFixed(2)} USD</span>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setIsCartOpen(false)}
                  className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
                >
                  Continue Shopping
                </button>
                <button
                  onClick={handleCheckout}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-brand-600 to-teal-600 text-white font-semibold shadow-lg shadow-brand-500/20"
                >
                  Confirm & Pay (Demo Mode)
                </button>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* Stock Adjust Modal */}
      <Modal
        isOpen={Boolean(adjustModalVariant)}
        onClose={() => setAdjustModalVariant(null)}
        title={`Adjust Stock: ${adjustModalVariant?.productName}`}
        subtitle={`SKU: ${adjustModalVariant?.sku} | Current Stock: ${adjustModalVariant?.stockQuantity}`}
      >
        <form onSubmit={handleStockAdjust} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 mb-1">Stock Quantity Change</label>
            <input
              type="number"
              required
              placeholder="e.g. 15 for addition, -5 for deduction"
              value={adjustQty}
              onChange={(e) => setAdjustQty(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Reason for Movement</label>
            <select
              value={adjustReason}
              onChange={(e) => setAdjustReason(e.target.value as any)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            >
              <option value="RESTOCK">Restock / Shipment Arrival</option>
              <option value="ADJUSTMENT">Inventory Audit Adjustment</option>
              <option value="SPOILAGE">Damaged / Spoilage</option>
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setAdjustModalVariant(null)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-semibold"
            >
              Save Stock Adjustment
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
