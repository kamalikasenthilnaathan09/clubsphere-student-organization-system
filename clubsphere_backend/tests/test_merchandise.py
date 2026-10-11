import pytest
from tests.conftest import create_user, login


def test_merchandise_creation_and_variant_stock(client, db):
    """Create merchandise item with multiple size variants and stock counts."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    res = client.post('/merchandise/new', data={
        'name': 'Club Hoodie 2026',
        'category': 'Apparel',
        'description': 'Warm fleece hoodie',
        'base_price': '850.00',
        'qty_S': '10',
        'qty_M': '20',
        'qty_L': '15',
        'qty_XL': '5'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"created with size variants" in res.data

    item = db.execute("SELECT * FROM merchandise_items WHERE name = 'Club Hoodie 2026'").fetchone()
    assert item is not None

    variants = db.execute("SELECT * FROM merchandise_variants WHERE item_id = ? ORDER BY size", (item['id'],)).fetchall()
    assert len(variants) == 4
    sizes = {v['size']: v['stock_quantity'] for v in variants}
    assert sizes['S'] == 10
    assert sizes['M'] == 20
    assert sizes['L'] == 15
    assert sizes['XL'] == 5


def test_merchandise_order_and_stock_deduction(client, db):
    """Customer order placement deducts stock and records income in ledger."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    # Create product and variant
    cursor = db.cursor()
    cursor.execute("INSERT INTO merchandise_items (name, base_price) VALUES ('Tech T-Shirt', 400)")
    item_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold)
        VALUES (?, 'M', 'TSHIRT-M', 15, 5)
    """, (item_id,))
    variant_id = cursor.lastrowid
    db.commit()

    # Place order for 2 units
    res = client.post('/merchandise/order', data={
        'customer_name': 'Divya Kumar',
        'customer_email': 'divya@example.com',
        'customer_phone': '9988776655',
        'variant_id': str(variant_id),
        'quantity': '2',
        'payment_method': 'UPI'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"confirmed! Deducted 2 units" in res.data

    # Check remaining stock: 15 - 2 = 13
    variant = db.execute("SELECT * FROM merchandise_variants WHERE id = ?", (variant_id,)).fetchone()
    assert variant['stock_quantity'] == 13

    # Check order recorded
    order = db.execute("SELECT * FROM merchandise_orders WHERE customer_email = 'divya@example.com'").fetchone()
    assert order is not None
    assert order['total_amount'] == 800.0  # 400 * 2

    # Check financial ledger entry
    ftx = db.execute("SELECT * FROM financial_transactions WHERE source_type = 'merchandise_order'").fetchone()
    assert ftx is not None
    assert ftx['amount'] == 800.0
    assert ftx['category'] == 'Merchandise Sale'


def test_merchandise_overselling_prevention(client, db):
    """Reject merchandise orders exceeding available stock and prevent negative stock."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    # Create product with only 2 units in stock
    cursor = db.cursor()
    cursor.execute("INSERT INTO merchandise_items (name, base_price) VALUES ('Limited Edition Cap', 300)")
    item_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold)
        VALUES (?, 'Free Size', 'CAP-FS', 2, 1)
    """, (item_id,))
    variant_id = cursor.lastrowid
    db.commit()

    # Attempt to order 3 units (insufficient stock)
    res = client.post('/merchandise/order', data={
        'customer_name': 'Greedy Buyer',
        'customer_email': 'buyer@example.com',
        'variant_id': str(variant_id),
        'quantity': '3',
        'payment_method': 'Cash'
    }, follow_redirects=True)

    assert b"Insufficient stock" in res.data

    # Stock must remain unchanged at 2
    variant = db.execute("SELECT * FROM merchandise_variants WHERE id = ?", (variant_id,)).fetchone()
    assert variant['stock_quantity'] == 2

    # No order should have been created
    orders = db.execute("SELECT COUNT(*) AS count FROM merchandise_orders").fetchone()
    assert orders['count'] == 0


def test_merchandise_restocking(client, db):
    """Restocking adds units to variant inventory."""
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'treasurer', 'Treasurer')
    login(client, 'treasurer')

    cursor = db.cursor()
    cursor.execute("INSERT INTO merchandise_items (name, base_price) VALUES ('Sticker Pack', 50)")
    item_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold)
        VALUES (?, 'Pack', 'STK-PK', 5, 5)
    """, (item_id,))
    variant_id = cursor.lastrowid
    db.commit()

    res = client.post(f'/merchandise/variants/{variant_id}/restock', data={
        'quantity': '20'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Restocked 20 units" in res.data

    variant = db.execute("SELECT * FROM merchandise_variants WHERE id = ?", (variant_id,)).fetchone()
    assert variant['stock_quantity'] == 25


def test_merchandise_page_ui_and_product_cards(client, db):
    """Verify merchandise catalog page displays product cards, images, prices, sizes, and tables."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    # Seed Hoodie with sizes S, M, L, XL
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO merchandise_items (name, category, description, base_price, is_active)
        VALUES ('Official Club Hoodie 2026', 'Apparel', 'Heavyweight fleece hoodie with embroidered ClubSphere crest.', 850.0, 1)
    """)
    hoodie_id = cursor.lastrowid
    cursor.execute("INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold) VALUES (?, 'S', 'HOODIE-S', 9, 5)", (hoodie_id,))
    cursor.execute("INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold) VALUES (?, 'M', 'HOODIE-M', 15, 5)", (hoodie_id,))
    cursor.execute("INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold) VALUES (?, 'L', 'HOODIE-L', 3, 5)", (hoodie_id,))
    cursor.execute("INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold) VALUES (?, 'XL', 'HOODIE-XL', 0, 5)", (hoodie_id,))

    # Seed Enamel Pin & Decal Pack
    cursor.execute("""
        INSERT INTO merchandise_items (name, category, description, base_price, is_active)
        VALUES ('ClubSphere Enamel Pin & Decal Pack', 'Accessories', 'Metallic finish collectible badge and laptop vinyl stickers.', 100.0, 1)
    """)
    pin_id = cursor.lastrowid
    cursor.execute("INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold) VALUES (?, 'Free Size', 'PIN-FS', 50, 10)", (pin_id,))

    # Seed an order
    cursor.execute("""
        INSERT INTO merchandise_orders (order_ref, customer_name, customer_email, total_amount, payment_status, payment_method)
        VALUES ('CS-ORD-TEST-001', 'Ananya Sharma', 'ananya.sharma@example.edu', 850.0, 'Paid', 'UPI')
    """)
    db.commit()

    res = client.get('/merchandise')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # 1. Page Header & Branding
    assert 'Club Merchandise &amp; Inventory' in html or 'Club Merchandise & Inventory' in html
    assert 'Featured Campus Merchandise' in html
    assert 'Stock Levels &amp; Size Variants' in html or 'Stock Levels & Size Variants' in html
    assert 'Recent Merchandise Orders' in html

    # 2. Card 1: Official Club Hoodie 2026
    assert 'Official Club Hoodie 2026' in html
    assert 'pic%2001.jpg' in html or 'pic 01.jpg' in html
    assert '850.00' in html
    assert 'HOODIE-S' in html
    assert 'HOODIE-M' in html
    assert 'HOODIE-L' in html
    assert 'HOODIE-XL' in html

    # 3. Card 2: ClubSphere Enamel Pin & Decal Pack
    assert 'ClubSphere Enamel Pin &amp; Decal Pack' in html or 'ClubSphere Enamel Pin & Decal Pack' in html
    assert 'pic%2002.jpg' in html or 'pic 02.jpg' in html
    assert '100.00' in html
    assert 'PIN-FS' in html
    assert '50' in html

    # 4. Inventory Table & Orders Table
    assert 'CS-ORD-TEST-001' in html
    assert 'Ananya Sharma' in html
    assert 'ananya.sharma@example.edu' in html
    assert 'Restock' in html

