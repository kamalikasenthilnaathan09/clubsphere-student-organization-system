import { seedDatabase } from '../src/lib/seed.js';
import prisma from '../src/lib/prisma.js';

seedDatabase()
  .catch((e) => {
    console.error('Seed error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
