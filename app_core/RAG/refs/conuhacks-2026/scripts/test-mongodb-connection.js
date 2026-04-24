/**
 * Test MongoDB connection script
 * Run with: node scripts/test-mongodb-connection.js
 */

require('dotenv').config({ path: '.env.local' });
const mongoose = require('mongoose');

const MONGODB_URI = process.env.MONGODB_URI;

if (!MONGODB_URI) {
  console.error('❌ MONGODB_URI not found in .env.local');
  process.exit(1);
}

console.log('🔍 Testing MongoDB Connection...');
console.log('Connection string:', MONGODB_URI.replace(/:[^:@]+@/, ':****@'));
console.log('');

const opts = {
  serverSelectionTimeoutMS: 30000,
  socketTimeoutMS: 45000,
  connectTimeoutMS: 30000,
};

const startTime = Date.now();

mongoose.connect(MONGODB_URI, opts)
  .then(() => {
    const connectTime = Date.now() - startTime;
    console.log(`✅ Connected successfully! (${connectTime}ms)`);
    console.log('Host:', mongoose.connection.host);
    console.log('Database:', mongoose.connection.name);
    console.log('Ready State:', mongoose.connection.readyState);
    console.log('');
    
    // Test ping
    return mongoose.connection.db.admin().ping();
  })
  .then(() => {
    console.log('✅ Ping successful!');
    console.log('');
    console.log('Connection is working properly.');
    process.exit(0);
  })
  .catch((error) => {
    const connectTime = Date.now() - startTime;
    console.error(`❌ Connection failed after ${connectTime}ms`);
    console.error('Error:', error.message);
    console.error('Error name:', error.name);
    console.error('');
    console.error('Troubleshooting:');
    console.error('1. Check if MongoDB Atlas cluster is running');
    console.error('2. Verify your IP is whitelisted');
    console.error('3. Check if cluster is paused (free tier)');
    console.error('4. Verify connection string is correct');
    process.exit(1);
  });

