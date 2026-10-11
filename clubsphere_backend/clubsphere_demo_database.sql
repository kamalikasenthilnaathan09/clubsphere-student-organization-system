BEGIN TRANSACTION;
CREATE TABLE achievement_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        points INTEGER NOT NULL CHECK(points != 0),
        reason TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_id INTEGER,
        awarded_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, source_type, source_id)
    );
INSERT INTO "achievement_points" VALUES(2,4,30,'Volunteer Task Completed: Prepare Announcement and Event Posters','task_completed',6,1,'2026-10-11 01:24:16');
INSERT INTO "achievement_points" VALUES(3,4,30,'Volunteer Task Completed: Verify Event Equipment and Supplies','task_completed',5,1,'2026-10-11 01:24:18');
INSERT INTO "achievement_points" VALUES(5,5,50,'Earned Certificate: AI & Robotics National Hackat','certificate',1,1,'2026-10-11 02:52:06');
INSERT INTO "achievement_points" VALUES(6,14,50,'Earned Certificate: Python & AI Workshop — Completi','certificate',2,1,'2026-10-11 02:52:06');
CREATE TABLE announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        audience TEXT NOT NULL DEFAULT 'All' CHECK(audience IN ('All', 'Members', 'Volunteers', 'Executive')),
        priority TEXT NOT NULL DEFAULT 'Normal' CHECK(priority IN ('Normal', 'Important', 'Urgent')),
        published_by INTEGER NOT NULL REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "announcements" VALUES(1,'Hackathon 2026 Problem Statements Released!','All participants can now review the AI and IoT problem statements. Check-in opens at 8:30 AM in the Main Auditorium.','All','Important',3,'2026-10-10 07:03:34');
INSERT INTO "announcements" VALUES(2,'Volunteer Briefing Meeting — Saturday 8:00 AM','All assigned volunteers please report to Innovation Lab for radio assignment and zone badges.','Volunteers','Urgent',3,'2026-10-10 07:03:34');
INSERT INTO "announcements" VALUES(3,'Executive Committee: Budget & Expense Review','Treasurer and core leads meeting on Monday to finalize vendor payments and audited accounts.','Executive','Normal',3,'2026-10-10 07:03:34');
INSERT INTO "announcements" VALUES(4,'Volunteer Briefing Meeting - Saturday 8:00 AM','All assigned volunteers please report to Innovation Lab for radio assignment and zone badges.','Volunteers','Urgent',3,'2026-10-10 07:04:07');
CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        event_date DATE NOT NULL,
        event_time TEXT NOT NULL,
        venue TEXT NOT NULL,
        capacity INTEGER NOT NULL CHECK(capacity > 0),
        member_price REAL NOT NULL DEFAULT 0.0 CHECK(member_price >= 0),
        non_member_price REAL NOT NULL DEFAULT 0.0 CHECK(non_member_price >= 0),
        status TEXT NOT NULL DEFAULT 'Upcoming' CHECK(status IN ('Upcoming', 'Ongoing', 'Completed', 'Cancelled')),
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    , poster_image TEXT);
INSERT INTO "events" VALUES(1,'AI & Robotics National Hackathon 2026','Annual 24-hour hackathon with industry mentors, hardware kits, and cash prizes.','2026-10-24','09:00','Main Auditorium & Innovation Lab',100,150.0,300.0,'Upcoming',3,'2026-10-10 07:03:08','images/pic 1.jpg');
INSERT INTO "events" VALUES(2,'Winter Acoustic Jam & Open Mic','Evening of live music, poetry performances, and refreshments under the stars.','2026-11-07','18:00','Amphitheatre Lawn',50,50.0,120.0,'Upcoming',3,'2026-10-10 07:03:08','images/pic 2.jpg');
INSERT INTO "events" VALUES(3,'Alumni Career & Leadership Summit','Panel discussions with distinguished alumni working in AI, Cloud, and Product.','2026-09-30','11:00','Seminar Hall B',40,0.0,100.0,'Completed',3,'2026-10-10 07:03:08','images/pic 3.jpg');
CREATE TABLE expense_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        requested_by INTEGER NOT NULL REFERENCES users(id),
        description TEXT NOT NULL,
        receipt_ref TEXT,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected', 'Paid')),
        approved_by INTEGER REFERENCES users(id),
        approved_date TIMESTAMP,
        rejection_reason TEXT,
        paid_by INTEGER REFERENCES users(id),
        paid_date TIMESTAMP,
        payment_method TEXT,
        payment_ref TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "expense_requests" VALUES(1,'PA Sound & Audio System Rental','Equipment & Tech',3000.0,3,'Stage amplifiers, 4 cordless microphones, and speaker towers for Hackathon auditorium.','REC-PA-9921',1,'Paid',2,'2026-10-10',NULL,2,'2026-10-10','Bank Transfer','UTR-NEFT-99112','2026-10-10 07:03:34');
INSERT INTO "expense_requests" VALUES(2,'Hackathon Catering & Midnight Snacks','Refreshments',2500.0,3,'Sandwiches, hot coffee, and mineral water for 100 participants.','EST-CAT-4412',1,'Paid',2,'2026-10-10',NULL,1,'2026-10-10 13:56:41','Bank Transfer','','2026-10-10 07:03:34');
INSERT INTO "expense_requests" VALUES(3,'Participant Badge Lanyards & Banners','Printing & Stationery',850.0,3,'Eco-friendly identity badges and auditorium backdrop banner.','QUO-PRN-001',1,'Paid',1,'2026-10-10 13:56:37',NULL,1,'2026-10-10 17:00:46','Bank Transfer','','2026-10-10 07:03:34');
CREATE TABLE financial_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Income', 'Expense')),
        category TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        description TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_id INTEGER,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        payment_method TEXT DEFAULT 'Cash',
        transaction_date DATE NOT NULL,
        recorded_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "financial_transactions" VALUES(1,'Income','Membership Fee',500.0,'Membership Fee for Ananya Sharma (CS-DEMO-MEM-001)','membership_payment',1,NULL,'UPI','2026-07-12',1,'2026-10-10 07:03:08');
INSERT INTO "financial_transactions" VALUES(2,'Income','Membership Fee',600.0,'Membership Fee for Rohan Varma (CS-DEMO-MEM-002)','membership_payment',2,NULL,'Cash','2026-08-11',1,'2026-10-10 07:03:08');
INSERT INTO "financial_transactions" VALUES(3,'Income','Ticket Sale',150.0,'Ticket CS-TKT-DEMO-001 for Attendee Ananya Sharma','ticket_sale',1,1,'UPI','2026-10-10',3,'2026-10-10 07:03:08');
INSERT INTO "financial_transactions" VALUES(4,'Income','Ticket Sale',300.0,'Ticket CS-TKT-DEMO-002 for Attendee Vikram Sen','ticket_sale',2,1,'Cash','2026-10-10',3,'2026-10-10 07:03:08');
INSERT INTO "financial_transactions" VALUES(5,'Income','Ticket Sale',300.0,'Ticket CS-TKT-DEMO-003 for Attendee Deepa Menon','ticket_sale',3,1,'Card','2026-10-10',3,'2026-10-10 07:03:08');
INSERT INTO "financial_transactions" VALUES(6,'Income','Ticket Sale',100.0,'Ticket CS-TKT-DEMO-005 for Attendee Rajiv Nair','ticket_sale',5,3,'UPI','2026-10-10',3,'2026-10-10 07:03:08');
INSERT INTO "financial_transactions" VALUES(7,'Income','Merchandise Sale',850.0,'Order CS-ORD-DEMO-001: 1x HOODIE-M for Ananya Sharma','merchandise_order',1,NULL,'UPI','2026-10-10',1,'2026-10-10 07:03:34');
INSERT INTO "financial_transactions" VALUES(8,'Income','Merchandise Sale',200.0,'Order CS-ORD-DEMO-002: 2x PIN-FS for Rohan Varma','merchandise_order',2,NULL,'Cash','2026-10-10',1,'2026-10-10 07:03:34');
INSERT INTO "financial_transactions" VALUES(9,'Expense','Expense Reimbursement',3000.0,'Paid Expense #1: PA Sound & Audio System Rental','expense_request',1,1,'Bank Transfer','2026-10-10',2,'2026-10-10 07:03:34');
INSERT INTO "financial_transactions" VALUES(10,'Income','Sponsorship',15000.0,'Tech Global Corp Title Sponsorship for Hackathon 2026','manual_income',NULL,1,'Bank Transfer','2026-10-10',2,'2026-10-10 07:03:34');
INSERT INTO "financial_transactions" VALUES(11,'Expense','Expense Reimbursement',2500.0,'Paid Expense #2: Hackathon Catering & Midnight Snacks (Refreshments)','expense_request',2,1,'Bank Transfer','2026-10-10',1,'2026-10-10 08:26:41');
INSERT INTO "financial_transactions" VALUES(12,'Income','Ticket Sale',100.0,'Ticket CS-TKT-3-5F83EF9C for Alumni Career & Leadership Summit (john)','ticket_sale',6,3,'Cash','2026-10-10',1,'2026-10-10 11:30:23');
INSERT INTO "financial_transactions" VALUES(13,'Expense','Expense Reimbursement',850.0,'Paid Expense #3: Participant Badge Lanyards & Banners (Printing & Stationery)','expense_request',3,1,'Bank Transfer','2026-10-10',1,'2026-10-10 11:30:46');
INSERT INTO "financial_transactions" VALUES(14,'Income','Ticket Sale',300.0,'Ticket CS-TKT-1-18523D2F for AI & Robotics National Hackathon 2026 (Aarav Live Demo) [Demo Payment]','ticket_sale_demo',7,1,'Demo Payment (Simulated)','2026-10-10',1,'2026-10-10 13:03:11');
INSERT INTO "financial_transactions" VALUES(15,'Income','Ticket Sale',300.0,'Ticket CS-TKT-1-3B642070 for AI & Robotics National Hackathon 2026 (Alex Rivera) [Demo Payment]','ticket_sale_demo',8,1,'Demo Payment (Simulated)','2026-10-10',1,'2026-10-10 15:25:03');
INSERT INTO "financial_transactions" VALUES(16,'Income','Membership Fee',500.0,'Membership Fee for Live Test Member (CS-MEM-2026-0005)','membership_payment',3,NULL,'UPI','2026-10-10',1,'2026-10-10 17:33:51');
INSERT INTO "financial_transactions" VALUES(17,'Income','Merchandise Sale',850.0,'Merchandise Order CS-ORD-1ABEC6E8: 1x Official Club Hoodie 2026 (S) for Live Customer','merchandise_order',3,NULL,'Cash','2026-10-10',1,'2026-10-10 17:33:51');
INSERT INTO "financial_transactions" VALUES(18,'Income','Ticket Sale',300.0,'Ticket CS-TKT-1-16E3571C for AI & Robotics National Hackathon 2026 (Alex Rivera) [Demo Payment]','ticket_sale_demo',9,1,'Demo Payment (Simulated)','2026-10-10',1,'2026-10-10 17:34:33');
INSERT INTO "financial_transactions" VALUES(19,'Income','Ticket Sale',300.0,'Ticket CS-TKT-1-A059E88A for AI & Robotics National Hackathon 2026 (Alex Rivera) [Demo Payment]','ticket_sale_demo',10,1,'Demo Payment (Simulated)','2026-10-10',1,'2026-10-10 17:55:59');
INSERT INTO "financial_transactions" VALUES(20,'Income','Ticket Sale',300.0,'Ticket CS-TKT-1-EE1591F6 for AI & Robotics National Hackathon 2026 (Test User) [Demo Payment]','ticket_sale_demo',11,1,'Demo Payment (Simulated)','2026-10-10',1,'2026-10-10 18:08:29');
INSERT INTO "financial_transactions" VALUES(21,'Income','Membership Fee',500.0,'Membership Fee for New Member (CS-MEM-2026-0006)','membership_payment',4,NULL,'Cash','2026-01-01',1,'2026-10-10 18:08:30');
INSERT INTO "financial_transactions" VALUES(22,'Income','Membership Fee',100.0,'Dues Payment for Rohan Varma (CS-DEMO-MEM-002)','membership_payment',5,NULL,'Cash','2026-10-10',1,'2026-10-10 18:09:40');
INSERT INTO "financial_transactions" VALUES(23,'Income','Membership Fee',500.0,'Membership Renewal for Rohan Varma (CS-DEMO-MEM-002)','membership_payment',6,NULL,'Cash','2026-10-10',1,'2026-10-10 18:09:41');
INSERT INTO "financial_transactions" VALUES(24,'Income','Membership Fee',500.0,'Membership Renewal for Rohan Varma (CS-DEMO-MEM-002)','membership_payment',7,NULL,'Cash','2026-10-10',1,'2026-10-10 18:09:41');
INSERT INTO "financial_transactions" VALUES(25,'Income','Ticket Sale',300.0,'Ticket CS-TKT-1-BF6FBFED for AI & Robotics National Hackathon 2026 (Alex Rivera) [Demo Payment]','ticket_sale_demo',12,1,'Demo Payment (Simulated)','2026-10-10',1,'2026-10-10 18:12:44');
INSERT INTO "financial_transactions" VALUES(26,'Income','Merchandise Sale',100.0,'Merchandise Order CS-ORD-19786F78: 1x ClubSphere Enamel Pin & Decal Pack (Free Size) for Live Verifier','merchandise_order',4,NULL,'Cash','2026-10-11',1,'2026-10-10 18:44:06');
INSERT INTO "financial_transactions" VALUES(27,'Income','Membership Fee',500.0,'Membership Fee for maya (CS-MEM-2026-0007)','membership_payment',8,NULL,'UPI','2026-10-11',1,'2026-10-11 01:23:19');
INSERT INTO "financial_transactions" VALUES(28,'Income','Ticket Sale',300.0,'Ticket CS-TKT-1-011F8469 for AI & Robotics National Hackathon 2026 (Kamalika senthilnaathan) [Demo Payment]','ticket_sale_demo',13,1,'Demo Payment (Simulated)','2026-10-11',1,'2026-10-11 01:27:08');
CREATE TABLE gate_checkin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_ref TEXT NOT NULL,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        status TEXT NOT NULL,
        message TEXT,
        verifier_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "gate_checkin_logs" VALUES(1,'CS-TKT-DEMO-001',1,'ALREADY_CHECKED_IN','Duplicate check-in. Previously scanned on 2026-10-09 09:15:00 by Tanvi Deshmukh.',1,'2026-10-10 18:27:55');
INSERT INTO "gate_checkin_logs" VALUES(2,'CS-TKT-INVALID-CODE',1,'INVALID','Ticket reference ''CS-TKT-INVALID-CODE'' was not found in the system.',1,'2026-10-10 18:28:03');
INSERT INTO "gate_checkin_logs" VALUES(3,'CS-TKT-DEMO-004',3,'ALREADY_CHECKED_IN','Duplicate check-in. Previously scanned on 2026-09-30 10:45:00 by Tanvi Deshmukh.',1,'2026-10-11 02:44:15');
INSERT INTO "gate_checkin_logs" VALUES(4,'CS-TKT-DEMO-004',3,'ALREADY_CHECKED_IN','Duplicate check-in. Previously scanned on 2026-09-30 10:45:00 by Tanvi Deshmukh.',1,'2026-10-11 02:44:19');
INSERT INTO "gate_checkin_logs" VALUES(5,'CS-TKT-DEMO-004',3,'ALREADY_CHECKED_IN','Duplicate check-in. Previously scanned on 2026-09-30 10:45:00 by Tanvi Deshmukh.',1,'2026-10-11 02:44:25');
INSERT INTO "gate_checkin_logs" VALUES(6,'CS-TKT-DEMO-004',3,'ALREADY_CHECKED_IN','Duplicate check-in. Previously scanned on 2026-09-30 10:45:00 by Tanvi Deshmukh.',1,'2026-10-11 02:44:28');
INSERT INTO "gate_checkin_logs" VALUES(7,'CS-TKT-DEMO-004',3,'ALREADY_CHECKED_IN','Duplicate check-in. Previously scanned on 2026-09-30 10:45:00 by Tanvi Deshmukh.',1,'2026-10-11 02:44:34');
CREATE TABLE members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
        member_code TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        student_id TEXT,
        department TEXT,
        join_date DATE NOT NULL,
        expiry_date DATE NOT NULL,
        membership_type TEXT NOT NULL DEFAULT 'Annual' CHECK(membership_type IN ('Annual', 'Semester', 'Lifetime')),
        membership_fee REAL NOT NULL DEFAULT 0.0 CHECK(membership_fee >= 0),
        amount_paid REAL NOT NULL DEFAULT 0.0 CHECK(amount_paid >= 0),
        status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Expired', 'Pending', 'Suspended')),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "members" VALUES(1,5,'CS-DEMO-MEM-001','Ananya Sharma','ananya.sharma@example.edu','+91 98765 11001','1NT23CS045','Computer Science','2026-07-12','2027-07-12','Annual',500.0,500.0,'Active','Demo active member with fully paid dues','2026-10-10 07:03:08');
INSERT INTO "members" VALUES(2,14,'CS-DEMO-MEM-002','Rohan Varma','rohan.varma@example.edu','+91 98765 11002','1NT23IS088','Information Science','2026-08-11','invalid-date','Annual',2000.0,1700.0,'Active','Demo member with ₹400 outstanding balance','2026-10-10 07:03:08');
INSERT INTO "members" VALUES(3,NULL,'CS-DEMO-MEM-003','Priya Nair','priya.nair@example.edu','+91 98765 11003','1NT22EC014','Electronics','2025-09-05','2026-09-05','Annual',500.0,500.0,'Expired','Demo expired member eligible for renewal','2026-10-10 07:03:08');
INSERT INTO "members" VALUES(4,NULL,'CS-DEMO-MEM-004','Karthik Reddy','karthik.reddy@example.edu','+91 98765 11004','1NT24ME032','Mechanical Engineering','2026-10-10','2027-10-10','Annual',500.0,0.0,'Pending','Demo newly registered member pending fee payment','2026-10-10 07:03:08');
INSERT INTO "members" VALUES(5,NULL,'CS-MEM-2026-0005','Live Test Member','live.test@example.edu','9876543210','1NT23CS888','Computer Science','2026-10-10','2027-10-10','Annual',500.0,500.0,'Active','','2026-10-10 17:33:51');
INSERT INTO "members" VALUES(6,NULL,'CS-MEM-2026-0006','New Member','new_unique@example.com','','STU999','CS','2026-01-01','2027-01-01','Annual',500.0,500.0,'Active','','2026-10-10 18:08:30');
INSERT INTO "members" VALUES(7,NULL,'CS-MEM-2026-0007','maya','maya@gmail.com','+91123456787','8976654','CSE','2026-10-11','2027-10-11','Annual',500.0,500.0,'Active','club','2026-10-11 01:23:19');
CREATE TABLE membership_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        amount REAL NOT NULL CHECK(amount > 0),
        payment_date DATE NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'Cash' CHECK(payment_method IN ('Cash', 'UPI', 'Card', 'Bank Transfer')),
        reference_no TEXT,
        notes TEXT,
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "membership_payments" VALUES(1,1,500.0,'2026-07-12','UPI','UPI-DEMO-001','Initial registration payment',1,'2026-10-10 07:03:08');
INSERT INTO "membership_payments" VALUES(2,2,600.0,'2026-08-11','Cash','CASH-REC-002','Initial registration payment',1,'2026-10-10 07:03:08');
INSERT INTO "membership_payments" VALUES(3,5,500.0,'2026-10-10','UPI','UPI-LIVE-01','Initial registration payment',1,'2026-10-10 17:33:51');
INSERT INTO "membership_payments" VALUES(4,6,500.0,'2026-01-01','Cash','','Initial registration payment',1,'2026-10-10 18:08:30');
INSERT INTO "membership_payments" VALUES(5,2,100.0,'2026-10-10','Cash','','',1,'2026-10-10 18:09:40');
INSERT INTO "membership_payments" VALUES(6,2,500.0,'2026-10-10','Cash','','Renewal payment (extended to 2028-01-01)',1,'2026-10-10 18:09:41');
INSERT INTO "membership_payments" VALUES(7,2,500.0,'2026-10-10','Cash','','Renewal payment (extended to invalid-date)',1,'2026-10-10 18:09:41');
INSERT INTO "membership_payments" VALUES(8,7,500.0,'2026-10-11','UPI','UPI-24578987346','Initial registration payment',1,'2026-10-11 01:23:19');
CREATE TABLE merchandise_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Apparel',
        description TEXT,
        base_price REAL NOT NULL CHECK(base_price >= 0),
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "merchandise_items" VALUES(1,'Official Club Hoodie 2026','Apparel','Heavyweight fleece hoodie with embroidered ClubSphere crest.',850.0,1,'2026-10-10 07:03:08');
INSERT INTO "merchandise_items" VALUES(2,'ClubSphere Enamel Pin & Decal Pack','Accessories','Metallic finish collectible badge and laptop vinyl stickers.',100.0,1,'2026-10-10 07:03:08');
CREATE TABLE merchandise_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL REFERENCES merchandise_orders(id) ON DELETE CASCADE,
        variant_id INTEGER NOT NULL REFERENCES merchandise_variants(id) ON DELETE RESTRICT,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        unit_price REAL NOT NULL CHECK(unit_price >= 0),
        subtotal REAL NOT NULL CHECK(subtotal >= 0)
    );
INSERT INTO "merchandise_order_items" VALUES(1,1,2,1,850.0,850.0);
INSERT INTO "merchandise_order_items" VALUES(2,2,5,2,100.0,200.0);
INSERT INTO "merchandise_order_items" VALUES(3,3,1,1,850.0,850.0);
INSERT INTO "merchandise_order_items" VALUES(4,4,5,1,100.0,100.0);
CREATE TABLE merchandise_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_ref TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        customer_phone TEXT,
        member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
        total_amount REAL NOT NULL CHECK(total_amount >= 0),
        payment_status TEXT NOT NULL DEFAULT 'Paid' CHECK(payment_status IN ('Paid', 'Pending', 'Cancelled')),
        payment_method TEXT DEFAULT 'Cash',
        notes TEXT,
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "merchandise_orders" VALUES(1,'CS-ORD-DEMO-001','Ananya Sharma','ananya.sharma@example.edu',NULL,1,850.0,'Paid','UPI',NULL,1,'2026-10-10 07:03:34');
INSERT INTO "merchandise_orders" VALUES(2,'CS-ORD-DEMO-002','Rohan Varma','rohan.varma@example.edu',NULL,2,200.0,'Paid','Cash',NULL,1,'2026-10-10 07:03:34');
INSERT INTO "merchandise_orders" VALUES(3,'CS-ORD-1ABEC6E8','Live Customer','live.cust@example.edu','9111222333',NULL,850.0,'Paid','Cash',NULL,1,'2026-10-10 17:33:51');
INSERT INTO "merchandise_orders" VALUES(4,'CS-ORD-19786F78','Live Verifier','verifier@campus.edu','',NULL,100.0,'Paid','Cash',NULL,1,'2026-10-10 18:44:06');
CREATE TABLE merchandise_variants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL REFERENCES merchandise_items(id) ON DELETE CASCADE,
        size TEXT NOT NULL,
        sku TEXT UNIQUE NOT NULL,
        stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK(stock_quantity >= 0),
        price_override REAL,
        low_stock_threshold INTEGER NOT NULL DEFAULT 5 CHECK(low_stock_threshold >= 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(item_id, size)
    );
INSERT INTO "merchandise_variants" VALUES(1,1,'S','HOODIE-S',11,NULL,5,'2026-10-10 07:03:08');
INSERT INTO "merchandise_variants" VALUES(2,1,'M','HOODIE-M',15,NULL,5,'2026-10-10 07:03:08');
INSERT INTO "merchandise_variants" VALUES(3,1,'L','HOODIE-L',3,NULL,5,'2026-10-10 07:03:08');
INSERT INTO "merchandise_variants" VALUES(4,1,'XL','HOODIE-XL',0,NULL,5,'2026-10-10 07:03:08');
INSERT INTO "merchandise_variants" VALUES(5,2,'Free Size','PIN-FS',49,NULL,10,'2026-10-10 07:03:08');
CREATE TABLE student_certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        certificate_ref TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        activity_type TEXT NOT NULL,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        issuing_org TEXT NOT NULL DEFAULT 'ClubSphere — Student Organization',
        recipient_name TEXT NOT NULL,
        issue_date DATE NOT NULL,
        status TEXT NOT NULL DEFAULT 'Issued' CHECK(status IN ('Issued', 'Revoked')),
        issued_by INTEGER REFERENCES users(id),
        qr_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "student_certificates" VALUES(1,'CERT-2026-DEMO-001',5,'AI & Robotics National Hackathon 2026 — Participation Certificate','Event Participation',1,'ClubSphere — Student Organization','Ananya Sharma','2026-10-06','Issued',1,'CLUBSPHERE-CERT:CERT-2026-DEMO-001:Ananya Sharma:2026-10-06','2026-10-11 02:52:06');
INSERT INTO "student_certificates" VALUES(2,'CERT-2026-DEMO-002',14,'Python & AI Workshop — Completion Certificate','Workshop Completion',NULL,'ClubSphere — Student Organization','Rohan Varma','2026-10-01','Issued',1,'CLUBSPHERE-CERT:CERT-2026-DEMO-002:Rohan Varma:2026-10-01','2026-10-11 02:52:06');
CREATE TABLE student_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        feedback_type TEXT NOT NULL CHECK(feedback_type IN ('Event', 'Club Activity', 'Workshop', 'Membership', 'General Suggestion')),
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        rating INTEGER CHECK(rating IS NULL OR (rating >= 1 AND rating <= 5)),
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        is_anonymous INTEGER NOT NULL DEFAULT 0 CHECK(is_anonymous IN (0, 1)),
        status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted', 'Reviewed', 'Actioned', 'Closed')),
        admin_notes TEXT,
        reviewed_by INTEGER REFERENCES users(id),
        reviewed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_ref TEXT UNIQUE NOT NULL,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        purchaser_name TEXT NOT NULL,
        purchaser_email TEXT NOT NULL,
        purchaser_phone TEXT,
        member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
        price_paid REAL NOT NULL DEFAULT 0.0 CHECK(price_paid >= 0),
        is_member_rate INTEGER NOT NULL DEFAULT 0,
        payment_method TEXT DEFAULT 'Cash',
        payment_status TEXT NOT NULL DEFAULT 'Confirmed' CHECK(payment_status IN ('Confirmed', 'Refunded', 'Cancelled')),
        checked_in INTEGER NOT NULL DEFAULT 0 CHECK(checked_in IN (0, 1)),
        check_in_time TIMESTAMP,
        checked_in_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    , payment_ref TEXT, qr_data TEXT);
INSERT INTO "tickets" VALUES(1,'CS-TKT-DEMO-001',1,'Ananya Sharma','ananya.sharma@example.edu',NULL,1,150.0,1,'UPI','Confirmed',1,'2026-10-09 09:15:00',4,'2026-10-10 07:03:08',NULL,NULL);
INSERT INTO "tickets" VALUES(2,'CS-TKT-DEMO-002',1,'Vikram Sen','vikram.sen@external.org',NULL,NULL,300.0,0,'Cash','Confirmed',1,'2026-10-10 17:59:44',1,'2026-10-10 07:03:08',NULL,NULL);
INSERT INTO "tickets" VALUES(3,'CS-TKT-DEMO-003',1,'Deepa Menon','deepa.m@guest.net',NULL,NULL,300.0,0,'Card','Confirmed',0,NULL,NULL,'2026-10-10 07:03:08',NULL,NULL);
INSERT INTO "tickets" VALUES(4,'CS-TKT-DEMO-004',3,'Ananya Sharma','ananya.sharma@example.edu',NULL,1,0.0,1,'Online','Confirmed',1,'2026-09-30 10:45:00',4,'2026-10-10 07:03:08',NULL,NULL);
INSERT INTO "tickets" VALUES(5,'CS-TKT-DEMO-005',3,'Rajiv Nair','rajiv.nair@guest.com',NULL,NULL,100.0,0,'UPI','Confirmed',1,'2026-09-30 10:55:00',4,'2026-10-10 07:03:08',NULL,NULL);
INSERT INTO "tickets" VALUES(6,'CS-TKT-3-5F83EF9C',3,'john','attendee@gmail.com','+91 123456788',NULL,100.0,0,'Cash','Confirmed',0,NULL,NULL,'2026-10-10 11:30:23',NULL,NULL);
INSERT INTO "tickets" VALUES(7,'CS-TKT-1-18523D2F',1,'Aarav Live Demo','aarav.live@example.com','',NULL,300.0,0,'Demo Payment (Simulated)','Confirmed',1,'2026-10-10 18:33:23',1,'2026-10-10 13:03:11','DEMO-TXN-1791637391-1EEE3369','CLUBSPERE:CS-TKT-1-18523D2F:1:fa254c803f30');
INSERT INTO "tickets" VALUES(8,'CS-TKT-1-3B642070',1,'Alex Rivera','kamalikasenthilnaathan@gmail.com','+91123456787',NULL,300.0,0,'Demo Payment (Simulated)','Confirmed',0,NULL,NULL,'2026-10-10 15:25:03','DEMO-TXN-1791645903-213E0124','CLUBSPERE:CS-TKT-1-3B642070:1:ed835728fba5');
INSERT INTO "tickets" VALUES(9,'CS-TKT-1-16E3571C',1,'Alex Rivera','kamalikasenthilnaathan@gmail.com','+91123456787',NULL,300.0,0,'Demo Payment (Simulated)','Confirmed',0,NULL,NULL,'2026-10-10 17:34:33','DEMO-TXN-1791653673-D3D928E1','CLUBSPERE:CS-TKT-1-16E3571C:1:6390c92ca709');
INSERT INTO "tickets" VALUES(10,'CS-TKT-1-A059E88A',1,'Alex Rivera','kamalikasenthilnaathan@gmail.com','+91123456787',NULL,300.0,0,'Demo Payment (Simulated)','Confirmed',0,NULL,NULL,'2026-10-10 17:55:59','DEMO-TXN-1791654959-AECA117C','CLUBSPERE:CS-TKT-1-A059E88A:1:e19a13e7ea11');
INSERT INTO "tickets" VALUES(11,'CS-TKT-1-EE1591F6',1,'Test User','test@example.com','',NULL,300.0,0,'Demo Payment (Simulated)','Confirmed',0,NULL,NULL,'2026-10-10 18:08:29','DEMO-TXN-1791655709-E71AB10C','CLUBSPERE:CS-TKT-1-EE1591F6:1:e88f1283dbca');
INSERT INTO "tickets" VALUES(12,'CS-TKT-1-BF6FBFED',1,'Alex Rivera','kamalikasenthilnaathan@gmail.com','+91123456787',NULL,300.0,0,'Demo Payment (Simulated)','Confirmed',1,'2026-10-10 23:43:01',1,'2026-10-10 18:12:44','DEMO-TXN-1791655964-F5E7428C','CLUBSPERE:CS-TKT-1-BF6FBFED:1:1b1381b0ce87');
INSERT INTO "tickets" VALUES(13,'CS-TKT-1-011F8469',1,'Kamalika senthilnaathan','kamalikasenthilnaathan@gmail.com','+91123456787',NULL,300.0,0,'Demo Payment (Simulated)','Confirmed',0,NULL,NULL,'2026-10-11 01:27:08','DEMO-TXN-1791682028-90F979CD','CLUBSPERE:CS-TKT-1-011F8469:1:9cfbc64755d1');
CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Administrator', 'Treasurer', 'Event Organizer', 'Volunteer', 'Member')),
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    , phone TEXT, department TEXT, academic_year TEXT, student_id TEXT, notification_preferences TEXT DEFAULT '{"email": true, "announcements": true, "events": true}', privacy_settings TEXT DEFAULT '{"show_on_leaderboard": true, "show_badges": true}', bio TEXT);
INSERT INTO "users" VALUES(1,'demo_admin','admin@clubdemo.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','Mahisa','Administrator',1,'2026-10-10 07:03:08',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(2,'demo_treasurer','treasurer@clubdemo.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','Meera Patel','Treasurer',1,'2026-10-10 07:03:08',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(3,'demo_organizer','organizer@clubdemo.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','Siddharth Rao','Event Organizer',1,'2026-10-10 07:03:08',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(4,'demo_volunteer','volunteer@clubdemo.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','Tanvi Deshmukh','Volunteer',1,'2026-10-10 07:03:08',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(5,'demo_member','member@clubdemo.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','Ananya Sharma','Member',1,'2026-10-10 07:03:08',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(6,'admin','admin@clubsphere.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','System Administrator','Administrator',1,'2026-10-10 10:56:31',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(7,'treasurer','treasurer@clubsphere.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','Meera Patel','Treasurer',1,'2026-10-10 10:56:31',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(8,'organizer','organizer@clubsphere.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','Siddharth Rao','Event Organizer',1,'2026-10-10 10:56:31',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(9,'volunteer','volunteer@clubsphere.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','Tanvi Deshmukh','Volunteer',1,'2026-10-10 10:56:31',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(10,'member','member@clubsphere.org','scrypt:32768:8:1$dGQ2uae3KWdOomqB$614cb9c0fc1389ab1c6708e1df58bbfc95956aef984ca82710f34056b6c7bf57d6b0be371c83f22efd8ff4f76981acef264d68e880ac3797f38556868ba40386','Ananya Sharma','Member',1,'2026-10-10 10:56:31',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(11,'kiran_member','kiran.patel@campus.edu','scrypt:32768:8:1$XBN2Za1af0XR0VjT$4a46d99642373c927a7c546536e84627decdc43474ea821a3a7fc6836cc9475d18891c3f3f800d18291b5a2263f5fcfdedbcd410693715a3905effa06d72ecab','Kiran Patel','Member',1,'2026-10-10 11:07:57',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(12,'devika_member','devika.nair@campus.edu','scrypt:32768:8:1$uOKTVk7DGr8imqWL$f01ea98b451d1186aa5e3860c6da799de5b6faac6a9863283dfb149f29b1e7b0da44a514d44a122a08aca899c80a0ee2056d024e90216ff30f4f00011a9696b4','Devika Nair','Member',1,'2026-10-10 11:09:12',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
INSERT INTO "users" VALUES(14,'rohan_member','rohan.varma@example.edu','scrypt:32768:8:1$kilEjtpy6mlvh65K$57356634a0573569f10ea7f5a4047606d6e63b3b21d5ce38d38e0530390cdb4f3e82a083e5867b92c61fab991b56732f4be050e9852396526385709c002bf586','Rohan Varma','Member',1,'2026-10-11 02:52:06',NULL,NULL,NULL,NULL,'{"email": true, "announcements": true, "events": true}','{"show_on_leaderboard": true, "show_badges": true}',NULL);
CREATE TABLE volunteer_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
        priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High', 'Urgent')),
        deadline DATE,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'In Progress', 'Completed', 'Cancelled')),
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "volunteer_tasks" VALUES(1,'Configure Stage Audio & PA Microphones','Perform sound test with 4 wireless mics in Main Auditorium.',1,4,'High','2026-10-23','Completed',3,'2026-10-10 07:03:34','2026-10-10 13:56:47');
INSERT INTO "volunteer_tasks" VALUES(2,'Assemble Attendee Registration Welcome Kits','Pack badges, stickers, and schedule booklets into bags.',1,4,'Urgent','2026-10-24','Completed',3,'2026-10-10 07:03:34','2026-10-10 13:56:46');
INSERT INTO "volunteer_tasks" VALUES(3,'Upload Alumni Summit Photos to Media Gallery','Curate and organize high-resolution event photos for website.',3,4,'Medium','2026-10-02','Completed',3,'2026-10-10 07:03:34','2026-10-10 07:03:34');
INSERT INTO "volunteer_tasks" VALUES(4,'Prepare Participant Registration Desk','Arrange registration materials, attendee lists, badges, and check-in equipment before the hackathon.',1,4,'High','2026-10-23','Pending',3,'2026-10-10 20:05:33','2026-10-10 20:05:33');
INSERT INTO "volunteer_tasks" VALUES(5,'Verify Event Equipment and Supplies','Check microphones, extension cables, stationery, and other required event supplies.',1,4,'High','2026-10-22','Completed',3,'2026-10-10 20:05:33','2026-10-11 06:54:18');
INSERT INTO "volunteer_tasks" VALUES(6,'Prepare Announcement and Event Posters','Organize approved event posters and prepare announcement materials for display.',1,4,'Medium','2026-10-21','In Progress',3,'2026-10-10 20:05:33','2026-10-11 06:54:21');
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_members_code ON members(member_code);
CREATE INDEX idx_members_email ON members(email);
CREATE INDEX idx_members_status ON members(status);
CREATE INDEX idx_tickets_ref ON tickets(ticket_ref);
CREATE INDEX idx_tickets_event ON tickets(event_id);
CREATE INDEX idx_variants_sku ON merchandise_variants(sku);
CREATE INDEX idx_variants_item ON merchandise_variants(item_id);
CREATE INDEX idx_expenses_status ON expense_requests(status);
CREATE INDEX idx_fin_type ON financial_transactions(transaction_type);
CREATE INDEX idx_fin_date ON financial_transactions(transaction_date);
CREATE INDEX idx_tasks_status ON volunteer_tasks(status);
CREATE INDEX idx_tasks_assigned ON volunteer_tasks(assigned_to);
CREATE INDEX idx_gate_logs_event ON gate_checkin_logs(event_id);
CREATE INDEX idx_gate_logs_status ON gate_checkin_logs(status);
CREATE INDEX idx_feedback_user ON student_feedback(user_id);
CREATE INDEX idx_feedback_status ON student_feedback(status);
CREATE INDEX idx_points_user ON achievement_points(user_id);
CREATE INDEX idx_points_source ON achievement_points(source_type, source_id);
CREATE INDEX idx_cert_ref ON student_certificates(certificate_ref);
CREATE INDEX idx_cert_user ON student_certificates(user_id);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('users',14);
INSERT INTO "sqlite_sequence" VALUES('members',7);
INSERT INTO "sqlite_sequence" VALUES('membership_payments',8);
INSERT INTO "sqlite_sequence" VALUES('financial_transactions',28);
INSERT INTO "sqlite_sequence" VALUES('events',3);
INSERT INTO "sqlite_sequence" VALUES('tickets',13);
INSERT INTO "sqlite_sequence" VALUES('merchandise_items',2);
INSERT INTO "sqlite_sequence" VALUES('merchandise_variants',5);
INSERT INTO "sqlite_sequence" VALUES('merchandise_orders',4);
INSERT INTO "sqlite_sequence" VALUES('merchandise_order_items',4);
INSERT INTO "sqlite_sequence" VALUES('expense_requests',3);
INSERT INTO "sqlite_sequence" VALUES('volunteer_tasks',6);
INSERT INTO "sqlite_sequence" VALUES('announcements',4);
INSERT INTO "sqlite_sequence" VALUES('gate_checkin_logs',7);
INSERT INTO "sqlite_sequence" VALUES('student_feedback',2);
INSERT INTO "sqlite_sequence" VALUES('achievement_points',6);
INSERT INTO "sqlite_sequence" VALUES('student_certificates',2);
COMMIT;
