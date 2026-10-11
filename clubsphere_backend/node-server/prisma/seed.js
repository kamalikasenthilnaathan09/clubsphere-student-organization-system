"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.seedDatabase = seedDatabase;
const client_1 = require("@prisma/client");
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const prisma = new client_1.PrismaClient();
async function seedDatabase() {
    console.log('--- Cleaning previous records ---');
    // Delete child relations first
    await prisma.auditLog.deleteMany();
    await prisma.budget.deleteMany();
    await prisma.financialTransaction.deleteMany();
    await prisma.expenseClaim.deleteMany();
    await prisma.taskAssignment.deleteMany();
    await prisma.volunteerTask.deleteMany();
    await prisma.fundraisingCampaign.deleteMany();
    await prisma.payment.deleteMany();
    await prisma.orderItem.deleteMany();
    await prisma.order.deleteMany();
    await prisma.inventoryMovement.deleteMany();
    await prisma.productVariant.deleteMany();
    await prisma.merchandiseProduct.deleteMany();
    await prisma.notification.deleteMany();
    await prisma.announcement.deleteMany();
    await prisma.checkIn.deleteMany();
    await prisma.ticket.deleteMany();
    await prisma.booking.deleteMany();
    await prisma.ticketType.deleteMany();
    await prisma.event.deleteMany();
    await prisma.membershipPayment.deleteMany();
    await prisma.memberSubscription.deleteMany();
    await prisma.membershipPlan.deleteMany();
    await prisma.organizationMembership.deleteMany();
    await prisma.organization.deleteMany();
    await prisma.user.deleteMany();
    console.log('--- Creating Users ---');
    const passwordHash = await bcryptjs_1.default.hash('Skyline@123', 10);
    const adminPasswordHash = await bcryptjs_1.default.hash('Admin@123', 10);
    const superAdmin = await prisma.user.create({
        data: {
            email: 'superadmin@campussphere.edu',
            passwordHash: adminPasswordHash,
            fullName: 'Dr. Harrison Vance',
            phone: '+1 (555) 019-2834',
            isSuperAdmin: true,
            avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150',
        },
    });
    const president = await prisma.user.create({
        data: {
            email: 'president@skyline.edu',
            passwordHash,
            fullName: 'Elena Rostova',
            phone: '+1 (555) 432-8765',
            avatarUrl: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150',
        },
    });
    const treasurer = await prisma.user.create({
        data: {
            email: 'treasurer@skyline.edu',
            passwordHash,
            fullName: 'Marcus Chen',
            phone: '+1 (555) 876-1234',
            avatarUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150',
        },
    });
    const eventManager = await prisma.user.create({
        data: {
            email: 'events@skyline.edu',
            passwordHash,
            fullName: 'Sophia Martinez',
            phone: '+1 (555) 321-9870',
            avatarUrl: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150',
        },
    });
    const volunteer = await prisma.user.create({
        data: {
            email: 'volunteer@skyline.edu',
            passwordHash,
            fullName: 'Liam O’Connor',
            phone: '+1 (555) 654-7890',
            avatarUrl: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150',
        },
    });
    const activeMember = await prisma.user.create({
        data: {
            email: 'member@skyline.edu',
            passwordHash,
            fullName: 'Zara Patel',
            phone: '+1 (555) 234-5678',
            avatarUrl: 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150',
        },
    });
    const studentUser = await prisma.user.create({
        data: {
            email: 'student@skyline.edu',
            passwordHash,
            fullName: 'Alex Rivera',
            phone: '+1 (555) 987-6543',
            avatarUrl: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150',
        },
    });
    console.log('--- Creating Organization: Skyline Student Association ---');
    const org = await prisma.organization.create({
        data: {
            name: 'Skyline Student Association',
            slug: 'skyline-sa',
            description: 'The premier student governance, technology, and leadership council uniting all undergraduate departments at Skyline University.',
            logoUrl: 'https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=200',
            primaryColor: '#8b5cf6',
            currency: 'USD',
        },
    });
    console.log('--- Creating Memberships ---');
    await prisma.organizationMembership.createMany({
        data: [
            {
                userId: superAdmin.id,
                organizationId: org.id,
                role: 'SUPER_ADMIN',
                status: 'ACTIVE',
                tier: 'HONORARY',
                department: 'University Senate',
                studentId: 'FAC-9001',
            },
            {
                userId: president.id,
                organizationId: org.id,
                role: 'CLUB_ADMIN',
                status: 'ACTIVE',
                tier: 'EXECUTIVE',
                department: 'Computer Science',
                studentId: 'SKY-2024-001',
            },
            {
                userId: treasurer.id,
                organizationId: org.id,
                role: 'TREASURER',
                status: 'ACTIVE',
                tier: 'EXECUTIVE',
                department: 'Finance & Economics',
                studentId: 'SKY-2024-002',
            },
            {
                userId: eventManager.id,
                organizationId: org.id,
                role: 'EVENT_MANAGER',
                status: 'ACTIVE',
                tier: 'EXECUTIVE',
                department: 'Media Communications',
                studentId: 'SKY-2024-003',
            },
            {
                userId: volunteer.id,
                organizationId: org.id,
                role: 'VOLUNTEER',
                status: 'ACTIVE',
                tier: 'STANDARD',
                department: 'Mechanical Engineering',
                studentId: 'SKY-2025-045',
            },
            {
                userId: activeMember.id,
                organizationId: org.id,
                role: 'MEMBER',
                status: 'ACTIVE',
                tier: 'VIP_GOLD',
                department: 'Information Technology',
                studentId: 'SKY-2025-108',
                expiryDate: new Date(Date.now() + 180 * 24 * 60 * 60 * 1000), // 180 days in future
            },
            {
                userId: studentUser.id,
                organizationId: org.id,
                role: 'MEMBER',
                status: 'PENDING',
                tier: 'STANDARD',
                department: 'Biotechnology',
                studentId: 'SKY-2026-310',
            },
        ],
    });
    console.log('--- Creating Membership Plans ---');
    const planStandard = await prisma.membershipPlan.create({
        data: {
            organizationId: org.id,
            name: 'Standard Student Membership',
            description: 'Annual access to all society workshops, newsletter, and voting rights in general assembly.',
            price: 25.0,
            durationMonths: 12,
            benefits: JSON.stringify(['Workshop Access', 'General Assembly Voting', 'Member Newsletter', '5% Merch Discount']),
            discountPercentage: 5.0,
            isActive: true,
        },
    });
    const planVIP = await prisma.membershipPlan.create({
        data: {
            organizationId: org.id,
            name: 'VIP Society Gold Pass',
            description: 'Priority seating, 20% discount on all ticketed fests, exclusive merchandise pack, and executive mentorship.',
            price: 60.0,
            durationMonths: 12,
            benefits: JSON.stringify(['Priority Gala Seating', '20% Event Discount', 'Exclusive Merch Pack', 'Executive Mentorship']),
            discountPercentage: 20.0,
            isActive: true,
        },
    });
    // Active subscription for Zara Patel
    const zaraMembership = await prisma.organizationMembership.findFirst({
        where: { userId: activeMember.id, organizationId: org.id },
    });
    if (zaraMembership) {
        const zaraSub = await prisma.memberSubscription.create({
            data: {
                membershipId: zaraMembership.id,
                planId: planVIP.id,
                startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
                endDate: new Date(Date.now() + 335 * 24 * 60 * 60 * 1000),
                status: 'ACTIVE',
            },
        });
        await prisma.membershipPayment.create({
            data: {
                subscriptionId: zaraSub.id,
                amount: 60.0,
                currency: 'USD',
                paymentMethod: 'DEMO_CARD',
                status: 'COMPLETED',
                transactionReference: 'MEM-PAY-2026-0091',
                paidAt: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
            },
        });
    }
    console.log('--- Creating Events and Ticket Types ---');
    const summitEvent = await prisma.event.create({
        data: {
            organizationId: org.id,
            title: 'Skyline Tech & AI Summit 2026',
            description: 'The flagship inter-college tech symposium featuring keynote talks from frontier AI founders, hackathon showcase, and networking reception.',
            category: 'ACADEMIC',
            venue: 'Main Auditorium & Innovation Hall A',
            bannerUrl: 'https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800',
            startDate: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000), // in 14 days
            endDate: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000 + 8 * 60 * 60 * 1000),
            capacity: 150,
            registrationOpensAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
            registrationClosesAt: new Date(Date.now() + 13 * 24 * 60 * 60 * 1000),
            status: 'PUBLISHED',
            budget: 1800.0,
            cancellationPolicy: 'Cancellations allowed up to 48 hours prior to the event for a full refund.',
            organizerInfo: 'Organized by Skyline AI Society & CS Dept.',
        },
    });
    const galaEvent = await prisma.event.create({
        data: {
            organizationId: org.id,
            title: 'Annual Cultural Gala & Awards Night',
            description: 'An evening of live music, theatrical performances, student recognition awards, and a catered formal banquet.',
            category: 'CULTURAL',
            venue: 'Skyline Grand Ballroom & Terraces',
            bannerUrl: 'https://images.unsplash.com/photo-1511578314322-379afb476865?w=800',
            startDate: new Date(Date.now() + 28 * 24 * 60 * 60 * 1000), // in 28 days
            endDate: new Date(Date.now() + 28 * 24 * 60 * 60 * 1000 + 5 * 60 * 60 * 1000),
            capacity: 250,
            registrationOpensAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
            registrationClosesAt: new Date(Date.now() + 26 * 24 * 60 * 60 * 1000),
            status: 'PUBLISHED',
            budget: 3200.0,
            cancellationPolicy: 'Non-refundable within 7 days of event date.',
            organizerInfo: 'Skyline Cultural Committee & Executive Board',
        },
    });
    const pastBootcamp = await prisma.event.create({
        data: {
            organizationId: org.id,
            title: 'Spring Leadership & Volunteer Bootcamp',
            description: 'Intensive workshop on project management, team leadership, and emergency campus response.',
            category: 'WORKSHOP',
            venue: 'Seminar Hall 302',
            bannerUrl: 'https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=800',
            startDate: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000),
            endDate: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000 + 4 * 60 * 60 * 1000),
            capacity: 60,
            registrationOpensAt: new Date(Date.now() - 25 * 24 * 60 * 60 * 1000),
            registrationClosesAt: new Date(Date.now() - 11 * 24 * 60 * 60 * 1000),
            status: 'COMPLETED',
            budget: 450.0,
        },
    });
    const summitTicketGen = await prisma.ticketType.create({
        data: {
            eventId: summitEvent.id,
            name: 'General Admission',
            description: 'Full pass to all talks, lunch, and symposium kit.',
            memberPrice: 10.0,
            nonMemberPrice: 25.0,
            totalQuantity: 100,
            remainingQuantity: 96,
        },
    });
    const summitTicketVIP = await prisma.ticketType.create({
        data: {
            eventId: summitEvent.id,
            name: 'VIP Front-Row & Speaker Dinner Pass',
            description: 'Reserved front-row seating and private dinner with keynote speakers.',
            memberPrice: 35.0,
            nonMemberPrice: 60.0,
            totalQuantity: 50,
            remainingQuantity: 48,
        },
    });
    await prisma.ticketType.create({
        data: {
            eventId: galaEvent.id,
            name: 'Standard Banquet Entry',
            description: 'Entry + Buffet dinner + Gala voting ballot.',
            memberPrice: 15.0,
            nonMemberPrice: 30.0,
            totalQuantity: 200,
            remainingQuantity: 195,
        },
    });
    // Past event ticket type
    const pastTicketType = await prisma.ticketType.create({
        data: {
            eventId: pastBootcamp.id,
            name: 'Participant Pass',
            memberPrice: 0.0,
            nonMemberPrice: 10.0,
            totalQuantity: 60,
            remainingQuantity: 12,
        },
    });
    console.log('--- Creating Sample Bookings and Checked-in Tickets ---');
    // Booking for Zara Patel on Tech Summit
    const zaraBooking = await prisma.booking.create({
        data: {
            eventId: summitEvent.id,
            userId: activeMember.id,
            bookingReference: 'BK-SKY-2026-0042',
            totalAmount: 10.0, // member price
            status: 'CONFIRMED',
            paymentStatus: 'PAID',
        },
    });
    const zaraTicket = await prisma.ticket.create({
        data: {
            bookingId: zaraBooking.id,
            ticketTypeId: summitTicketGen.id,
            eventId: summitEvent.id,
            ticketCode: 'TKT-SKY-SUMMIT-9901',
            qrSecret: 'QRSEC-9901-ZARA-7728',
            attendeeName: 'Zara Patel',
            attendeeEmail: 'member@skyline.edu',
            status: 'VALID',
            isCheckedIn: false,
        },
    });
    await prisma.payment.create({
        data: {
            organizationId: org.id,
            bookingId: zaraBooking.id,
            amount: 10.0,
            currency: 'USD',
            provider: 'DEMO_PAYMENT',
            transactionId: 'TX-PAY-SUMMIT-0042',
            status: 'SETTLED',
            isDemo: true,
        },
    });
    // Past event booking already checked in
    const pastBooking = await prisma.booking.create({
        data: {
            eventId: pastBootcamp.id,
            userId: volunteer.id,
            bookingReference: 'BK-SKY-2026-0011',
            totalAmount: 0.0,
            status: 'CONFIRMED',
            paymentStatus: 'PAID',
        },
    });
    const pastTicket = await prisma.ticket.create({
        data: {
            bookingId: pastBooking.id,
            ticketTypeId: pastTicketType.id,
            eventId: pastBootcamp.id,
            ticketCode: 'TKT-SKY-BOOT-1011',
            qrSecret: 'QRSEC-1011-LIAM-4411',
            attendeeName: 'Liam O’Connor',
            attendeeEmail: 'volunteer@skyline.edu',
            isCheckedIn: true,
            checkedInAt: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000 + 30 * 60 * 1000),
            checkedInByUserId: eventManager.id,
            status: 'USED',
        },
    });
    await prisma.checkIn.create({
        data: {
            ticketId: pastTicket.id,
            eventId: pastBootcamp.id,
            checkedInByUserId: eventManager.id,
            checkedInAt: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000 + 30 * 60 * 1000),
            checkInMethod: 'QR_SCAN',
            notes: 'Verified via campus mobile scanner',
        },
    });
    console.log('--- Creating Merchandise and Inventory ---');
    const hoodie = await prisma.merchandiseProduct.create({
        data: {
            organizationId: org.id,
            name: 'Skyline Midnight Heritage Hoodie',
            description: 'Ultra-soft heavyweight fleece hoodie with embroidered Skyline crest and midnight purple inner hood lining.',
            category: 'APPAREL',
            basePrice: 48.0,
            memberDiscountPercent: 15.0,
            imageUrl: 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=600',
            isActive: true,
        },
    });
    const bottle = await prisma.merchandiseProduct.create({
        data: {
            organizationId: org.id,
            name: 'Skyline Insulated Thermal Bottle (750ml)',
            description: 'Double-wall vacuum insulated stainless steel flask with laser-etched motto and leakproof lid.',
            category: 'DRINKWARE',
            basePrice: 22.0,
            memberDiscountPercent: 10.0,
            imageUrl: 'https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600',
            isActive: true,
        },
    });
    const pin = await prisma.merchandiseProduct.create({
        data: {
            organizationId: org.id,
            name: 'Skyline Founder Enamel Pin (Gold Edition)',
            description: 'Die-cast zinc alloy collectible pin with electroplated gold finish and rubber clutch backing.',
            category: 'ACCESSORIES',
            basePrice: 8.0,
            memberDiscountPercent: 0.0,
            imageUrl: 'https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=600',
            isActive: true,
        },
    });
    // Hoodie variants
    const hoodieS = await prisma.productVariant.create({
        data: { productId: hoodie.id, sku: 'SKY-HD-S', size: 'S', color: 'Midnight Navy', stockQuantity: 12, lowStockThreshold: 5 },
    });
    const hoodieM = await prisma.productVariant.create({
        data: { productId: hoodie.id, sku: 'SKY-HD-M', size: 'M', color: 'Midnight Navy', stockQuantity: 28, lowStockThreshold: 5 },
    });
    const hoodieL = await prisma.productVariant.create({
        data: { productId: hoodie.id, sku: 'SKY-HD-L', size: 'L', color: 'Midnight Navy', stockQuantity: 3, lowStockThreshold: 5 }, // Low stock warning!
    });
    const hoodieXL = await prisma.productVariant.create({
        data: { productId: hoodie.id, sku: 'SKY-HD-XL', size: 'XL', color: 'Midnight Navy', stockQuantity: 18, lowStockThreshold: 5 },
    });
    // Bottle variant
    const bottleVar = await prisma.productVariant.create({
        data: { productId: bottle.id, sku: 'SKY-BTL-750', size: 'One-Size', color: 'Matte Slate', stockQuantity: 42, lowStockThreshold: 8 },
    });
    // Pin variant
    const pinVar = await prisma.productVariant.create({
        data: { productId: pin.id, sku: 'SKY-PIN-GOLD', size: 'Standard', color: 'Gold', stockQuantity: 85, lowStockThreshold: 10 },
    });
    // Log inventory movement
    await prisma.inventoryMovement.createMany({
        data: [
            { variantId: hoodieS.id, quantityChange: 15, previousStock: 0, newStock: 15, reason: 'INITIAL', reference: 'PO-2026-001' },
            { variantId: hoodieM.id, quantityChange: 30, previousStock: 0, newStock: 30, reason: 'INITIAL', reference: 'PO-2026-001' },
            { variantId: hoodieL.id, quantityChange: 10, previousStock: 0, newStock: 10, reason: 'INITIAL', reference: 'PO-2026-001' },
            { variantId: hoodieL.id, quantityChange: -7, previousStock: 10, newStock: 3, reason: 'SALE', reference: 'PRE-SEMESTER-FAIR' },
            { variantId: bottleVar.id, quantityChange: 50, previousStock: 0, newStock: 50, reason: 'INITIAL', reference: 'PO-2026-002' },
            { variantId: pinVar.id, quantityChange: 100, previousStock: 0, newStock: 100, reason: 'INITIAL', reference: 'PO-2026-003' },
        ],
    });
    // Sample Completed Order
    const sampleOrder = await prisma.order.create({
        data: {
            organizationId: org.id,
            userId: activeMember.id,
            orderNumber: 'ORD-SKY-2026-8801',
            subtotal: 48.0,
            discount: 7.2, // 15% discount for active VIP member
            totalAmount: 40.8,
            status: 'PAID',
            paymentStatus: 'PAID',
        },
    });
    await prisma.orderItem.create({
        data: {
            orderId: sampleOrder.id,
            productId: hoodie.id,
            variantId: hoodieM.id,
            quantity: 1,
            unitPrice: 48.0,
            totalPrice: 40.8,
        },
    });
    await prisma.payment.create({
        data: {
            organizationId: org.id,
            orderId: sampleOrder.id,
            amount: 40.8,
            currency: 'USD',
            provider: 'DEMO_PAYMENT',
            transactionId: 'TX-PAY-ORD-8801',
            status: 'SETTLED',
            isDemo: true,
        },
    });
    console.log('--- Creating Announcements ---');
    await prisma.announcement.createMany({
        data: [
            {
                organizationId: org.id,
                authorId: president.id,
                title: 'Welcome to Spring Semester 2026: Official President Welcome Address',
                content: 'Fellow students and society members, welcome back! This semester we have an extraordinary lineup including our Tech & AI Summit, our Annual Gala, and expanded grant funding for student initiatives.',
                category: 'GENERAL',
                targetAudience: 'ALL_MEMBERS',
                status: 'PUBLISHED',
                publishedAt: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000),
                emailSent: true,
                emailRecipientCount: 380,
            },
            {
                organizationId: org.id,
                authorId: eventManager.id,
                title: 'Call for Student Tech Speakers: AI Summit Keynotes',
                content: 'Submissions for lightning talks and research posters at the Tech & AI Summit are officially open until Friday at 11:59 PM. Undergraduate and graduate papers are both eligible.',
                category: 'EVENT',
                targetAudience: 'ALL_MEMBERS',
                status: 'PUBLISHED',
                publishedAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000),
                emailSent: true,
                emailRecipientCount: 380,
            },
            {
                organizationId: org.id,
                authorId: treasurer.id,
                title: 'Spring Budget Allocation & Reimbursement Guidelines',
                content: 'All committee leads must review the updated reimbursement handbook. Receipt submission deadlines are strictly within 14 calendar days of incurring expenses.',
                category: 'URGENT',
                targetAudience: 'EXECUTIVES',
                status: 'PUBLISHED',
                publishedAt: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000),
                emailSent: false,
            },
        ],
    });
    console.log('--- Creating Fundraising Campaign ---');
    const campaign = await prisma.fundraisingCampaign.create({
        data: {
            organizationId: org.id,
            coordinatorId: president.id,
            title: 'Campus Innovation Lab Hardware & Student Grants 2026',
            description: 'Fundraising campaign to equip the student communal workspace with edge AI development boards, 3D printers, and micro-scholarships for hackathon travel.',
            goalAmount: 5000.0,
            currentAmount: 3250.0,
            startDate: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000),
            endDate: new Date(Date.now() + 40 * 24 * 60 * 60 * 1000),
            status: 'ACTIVE',
        },
    });
    console.log('--- Creating Volunteer Tasks ---');
    const task1 = await prisma.volunteerTask.create({
        data: {
            organizationId: org.id,
            title: 'Distribute AI Summit Promotional Posters across Engineering Quad',
            description: 'Hang official laminated posters on all designated notice boards in Hall 1, 2, and the Library.',
            priority: 'HIGH',
            status: 'COMPLETED',
            dueDate: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000),
            createdByUserId: eventManager.id,
        },
    });
    const task2 = await prisma.volunteerTask.create({
        data: {
            organizationId: org.id,
            title: 'Assemble Speaker Welcome Gift Kits and Name Badges',
            description: 'Package hoodies, customized mugs, and lanyard name badges for 12 visiting keynote speakers.',
            priority: 'HIGH',
            status: 'IN_PROGRESS',
            dueDate: new Date(Date.now() + 4 * 24 * 60 * 60 * 1000),
            createdByUserId: eventManager.id,
        },
    });
    const task3 = await prisma.volunteerTask.create({
        data: {
            organizationId: org.id,
            title: 'Review and Catalog Audio/Visual Equipment for Ballroom Gala',
            description: 'Test wireless lapel microphones, mixer channels, and projector latency in the Grand Ballroom.',
            priority: 'MEDIUM',
            status: 'TODO',
            dueDate: new Date(Date.now() + 12 * 24 * 60 * 60 * 1000),
            createdByUserId: eventManager.id,
        },
    });
    await prisma.taskAssignment.createMany({
        data: [
            { taskId: task1.id, userId: volunteer.id },
            { taskId: task2.id, userId: volunteer.id },
            { taskId: task3.id, userId: volunteer.id },
        ],
    });
    console.log('--- Creating Expense Claims & Financial Transactions ---');
    // Approved expense claim submitted by volunteer
    const claimApproved = await prisma.expenseClaim.create({
        data: {
            organizationId: org.id,
            claimantId: volunteer.id,
            title: 'Poster Lamination and Printing Supplies',
            description: 'Lamination film rolls and heavy cardstock purchased from University Print Shop for summit posters.',
            amount: 45.5,
            category: 'PRINTING',
            receiptUrl: 'https://example.com/receipts/rec-00455.pdf',
            status: 'APPROVED',
            reviewedByUserId: treasurer.id,
            reviewedAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
            reviewNotes: 'Verified against receipt invoice #9921.',
        },
    });
    // Pending expense claim submitted by volunteer
    await prisma.expenseClaim.create({
        data: {
            organizationId: org.id,
            claimantId: volunteer.id,
            title: 'Refreshments for Volunteer Orientation Meet',
            description: 'Bottled juices, donuts, and paper napkins for 25 student volunteers at the orientation workshop.',
            amount: 68.25,
            category: 'REFRESHMENTS',
            receiptUrl: 'https://example.com/receipts/rec-00682.pdf',
            status: 'PENDING',
        },
    });
    // Financial Ledger Transactions (Decimal safe float storage, mathematically reconciled)
    await prisma.financialTransaction.createMany({
        data: [
            // Income: Membership dues
            {
                organizationId: org.id,
                type: 'INCOME',
                category: 'MEMBERSHIP_DUES',
                amount: 1450.0,
                currency: 'USD',
                status: 'SETTLED',
                description: 'Semester Membership dues collected from 58 registered students',
                reference: 'DUES-BATCH-2026-A',
                createdByUserId: treasurer.id,
                transactionDate: new Date(Date.now() - 25 * 24 * 60 * 60 * 1000),
            },
            // Income: Event ticket sales
            {
                organizationId: org.id,
                type: 'INCOME',
                category: 'EVENT_TICKETS',
                amount: 860.0,
                currency: 'USD',
                status: 'SETTLED',
                description: 'Ticket pre-sales for Skyline Tech & AI Summit 2026',
                reference: 'TKT-REV-SUMMIT-1',
                eventId: summitEvent.id,
                createdByUserId: eventManager.id,
                transactionDate: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000),
            },
            // Income: Merchandise sales
            {
                organizationId: org.id,
                type: 'INCOME',
                category: 'MERCHANDISE',
                amount: 412.5,
                currency: 'USD',
                status: 'SETTLED',
                description: 'Merchandise store online & campus booth sales',
                reference: 'MERCH-SETTLE-JAN',
                createdByUserId: treasurer.id,
                transactionDate: new Date(Date.now() - 4 * 24 * 60 * 60 * 1000),
            },
            // Income: Fundraising campaign donations
            {
                organizationId: org.id,
                type: 'INCOME',
                category: 'FUNDRAISING',
                amount: 3250.0,
                currency: 'USD',
                status: 'SETTLED',
                description: 'Alumni and departmental corporate match contributions for Tech Lab',
                reference: 'DON-CAMP-2026-TL',
                campaignId: campaign.id,
                createdByUserId: president.id,
                transactionDate: new Date(Date.now() - 15 * 24 * 60 * 60 * 1000),
            },
            // Expense: Event venue deposit
            {
                organizationId: org.id,
                type: 'EXPENSE',
                category: 'EVENT_EXPENSES',
                amount: 500.0,
                currency: 'USD',
                status: 'SETTLED',
                description: 'Advance booking deposit for Grand Ballroom Gala venue',
                reference: 'VEN-DEP-GALA-01',
                eventId: galaEvent.id,
                createdByUserId: treasurer.id,
                transactionDate: new Date(Date.now() - 12 * 24 * 60 * 60 * 1000),
            },
            // Expense: Merchandise manufacturing bulk inventory
            {
                organizationId: org.id,
                type: 'EXPENSE',
                category: 'MERCH_COSTS',
                amount: 720.0,
                currency: 'USD',
                status: 'SETTLED',
                description: 'Wholesale production invoice for 60 embroidered hoodies and pins',
                reference: 'INV-MFR-4819',
                createdByUserId: treasurer.id,
                transactionDate: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000),
            },
            // Expense: Volunteer reimbursement for approved printing
            {
                organizationId: org.id,
                type: 'EXPENSE',
                category: 'VOLUNTEER_REIMBURSEMENT',
                amount: 45.5,
                currency: 'USD',
                status: 'SETTLED',
                description: 'Reimbursement to Liam O’Connor for Poster Lamination and Printing Supplies',
                reference: 'REIMB-CLAIM-455',
                expenseClaimId: claimApproved.id,
                createdByUserId: treasurer.id,
                transactionDate: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
            },
            // Expense: Operating website hosting & domain
            {
                organizationId: org.id,
                type: 'EXPENSE',
                category: 'OPERATING_EXPENSES',
                amount: 85.0,
                currency: 'USD',
                status: 'SETTLED',
                description: 'Annual domain renewal and SSL certificate hosting',
                reference: 'HOST-RENEW-2026',
                createdByUserId: treasurer.id,
                transactionDate: new Date(Date.now() - 18 * 24 * 60 * 60 * 1000),
            },
        ],
    });
    console.log('--- Creating Budgets ---');
    await prisma.budget.createMany({
        data: [
            { organizationId: org.id, category: 'EVENT_EXPENSES', allocatedAmount: 4000.0, fiscalYear: 2026, period: 'ANNUAL' },
            { organizationId: org.id, category: 'MERCH_COSTS', allocatedAmount: 1200.0, fiscalYear: 2026, period: 'ANNUAL' },
            { organizationId: org.id, category: 'VOLUNTEER_REIMBURSEMENT', allocatedAmount: 600.0, fiscalYear: 2026, period: 'ANNUAL' },
            { organizationId: org.id, category: 'OPERATING_EXPENSES', allocatedAmount: 800.0, fiscalYear: 2026, period: 'ANNUAL' },
        ],
    });
    console.log('--- Creating Audit Logs ---');
    await prisma.auditLog.createMany({
        data: [
            {
                organizationId: org.id,
                actorUserId: superAdmin.id,
                action: 'ORGANIZATION_PROVISIONED',
                entityType: 'Organization',
                entityId: org.id,
                details: JSON.stringify({ name: 'Skyline Student Association', slug: 'skyline-sa' }),
            },
            {
                organizationId: org.id,
                actorUserId: president.id,
                action: 'EVENT_CREATED',
                entityType: 'Event',
                entityId: summitEvent.id,
                details: JSON.stringify({ title: 'Skyline Tech & AI Summit 2026', capacity: 150 }),
            },
            {
                organizationId: org.id,
                actorUserId: treasurer.id,
                action: 'EXPENSE_APPROVED',
                entityType: 'ExpenseClaim',
                entityId: claimApproved.id,
                details: JSON.stringify({ amount: 45.5, claimant: 'Liam O’Connor' }),
            },
            {
                organizationId: org.id,
                actorUserId: eventManager.id,
                action: 'TICKET_CHECKED_IN',
                entityType: 'Ticket',
                entityId: pastTicket.id,
                details: JSON.stringify({ attendee: 'Liam O’Connor', event: 'Spring Leadership & Volunteer Bootcamp' }),
            },
        ],
    });
    console.log('--- Creating Sample Notifications ---');
    await prisma.notification.createMany({
        data: [
            {
                userId: activeMember.id,
                title: 'Ticket Confirmed: Tech & AI Summit 2026',
                message: 'Your booking BK-SKY-2026-0042 is confirmed. Your QR ticket is ready in your wallet.',
                type: 'SUCCESS',
                linkUrl: '/events',
            },
            {
                userId: volunteer.id,
                title: 'New Volunteer Task Assigned',
                message: 'You have been assigned to: Assemble Speaker Welcome Gift Kits and Name Badges.',
                type: 'INFO',
                linkUrl: '/tasks',
            },
            {
                userId: treasurer.id,
                title: 'New Reimbursement Claim Awaiting Review',
                message: 'Liam O’Connor submitted a claim for $68.25 (Volunteer Orientation Refreshments).',
                type: 'WARNING',
                linkUrl: '/finance',
            },
        ],
    });
    console.log('=== SEED COMPLETE: Skyline Student Association successfully initialized! ===');
}
// Execute if run directly
if (process.argv[1]?.endsWith('seed.ts')) {
    seedDatabase()
        .catch((e) => {
        console.error('Seed error:', e);
        process.exit(1);
    })
        .finally(async () => {
        await prisma.$disconnect();
    });
}
