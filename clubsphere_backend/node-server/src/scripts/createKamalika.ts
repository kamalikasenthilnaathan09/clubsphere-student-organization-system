import bcrypt from 'bcryptjs';
import prisma from '../lib/prisma.js';

async function main() {
  const salt = await bcrypt.genSalt(10);
  const passwordHash = await bcrypt.hash('12345678', salt);

  // 1. Create or update user Kamalika with super admin rights
  const user = await prisma.user.upsert({
    where: { email: 'kamalika@skyline.edu' },
    update: {
      fullName: 'Kamalika',
      passwordHash: passwordHash,
      isSuperAdmin: true,
      phone: '+1 (555) 789-0199',
    },
    create: {
      email: 'kamalika@skyline.edu',
      fullName: 'Kamalika',
      passwordHash: passwordHash,
      isSuperAdmin: true,
      phone: '+1 (555) 789-0199',
    },
  });

  console.log(`User created/updated: ${user.fullName} (${user.email}), isSuperAdmin: ${user.isSuperAdmin}`);

  // 2. Link Kamalika to all organizations as CLUB_ADMIN / President
  const organizations = await prisma.organization.findMany();
  for (const org of organizations) {
    const membership = await prisma.organizationMembership.upsert({
      where: {
        userId_organizationId: {
          userId: user.id,
          organizationId: org.id,
        },
      },
      update: {
        role: 'CLUB_ADMIN',
        status: 'ACTIVE',
        tier: 'EXECUTIVE_LEAD',
        studentId: 'STU-KAMALIKA-001',
        department: 'Computer Science & Engineering',
      },
      create: {
        userId: user.id,
        organizationId: org.id,
        role: 'CLUB_ADMIN',
        status: 'ACTIVE',
        tier: 'EXECUTIVE_LEAD',
        studentId: 'STU-KAMALIKA-001',
        department: 'Computer Science & Engineering',
      },
    });
    console.log(`Assigned CLUB_ADMIN role in organization: ${org.name} (${org.slug})`);
  }

  // Also create alias or second user kamalika@campussphere.edu for convenience if needed
  await prisma.user.upsert({
    where: { email: 'kamalika@campussphere.edu' },
    update: {
      fullName: 'Kamalika',
      passwordHash: passwordHash,
      isSuperAdmin: true,
      phone: '+1 (555) 789-0199',
    },
    create: {
      email: 'kamalika@campussphere.edu',
      fullName: 'Kamalika',
      passwordHash: passwordHash,
      isSuperAdmin: true,
      phone: '+1 (555) 789-0199',
    },
  });

  const user2 = await prisma.user.findUnique({ where: { email: 'kamalika@campussphere.edu' } });
  if (user2) {
    for (const org of organizations) {
      await prisma.organizationMembership.upsert({
        where: {
          userId_organizationId: {
            userId: user2.id,
            organizationId: org.id,
          },
        },
        update: {
          role: 'CLUB_ADMIN',
          status: 'ACTIVE',
          tier: 'EXECUTIVE_LEAD',
          studentId: 'STU-KAMALIKA-001',
          department: 'Computer Science & Engineering',
        },
        create: {
          userId: user2.id,
          organizationId: org.id,
          role: 'CLUB_ADMIN',
          status: 'ACTIVE',
          tier: 'EXECUTIVE_LEAD',
          studentId: 'STU-KAMALIKA-001',
          department: 'Computer Science & Engineering',
        },
      });
    }
  }

  console.log('Successfully configured Kamalika as main administrator for both kamalika@skyline.edu and kamalika@campussphere.edu!');
}

main()
  .catch((e) => {
    console.error('Error creating user:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
