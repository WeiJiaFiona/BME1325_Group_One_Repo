const mongoose = require('mongoose');

// Get MongoDB URI from command line argument or environment variable
const MONGODB_URI = process.argv[2] || process.env.MONGODB_URI;

if (!MONGODB_URI) {
  console.error('❌ MONGODB_URI not provided');
  console.error('');
  console.error('Usage:');
  console.error('  node scripts/add-wait-times.js "your-mongodb-uri"');
  console.error('  OR');
  console.error('  MONGODB_URI="your-uri" node scripts/add-wait-times.js');
  console.error('');
  process.exit(1);
}

const HospitalSchema = new mongoose.Schema({
  name: String,
  slug: String,
  address: String,
  city: String,
  phone: String,
  specialties: [String],
  maxCapacity: Number,
  currentPatients: Number,
  currentWait: Number,
  isActive: Boolean,
}, { timestamps: true });

const Hospital = mongoose.models.Hospital || mongoose.model('Hospital', HospitalSchema);

async function addWaitTimes() {
  try {
    console.log('🔗 Connecting to MongoDB...');
    await mongoose.connect(MONGODB_URI);
    console.log('✅ Connected to MongoDB\n');

    // Find all hospitals without currentWait field
    const hospitals = await Hospital.find({
      $or: [
        { currentWait: { $exists: false } },
        { currentWait: null }
      ]
    });

    console.log(`Found ${hospitals.length} hospital(s) without wait times\n`);

    if (hospitals.length === 0) {
      console.log('✅ All hospitals already have wait times set');
      return;
    }

    // Update each hospital with a realistic wait time
    let updated = 0;
    for (const hospital of hospitals) {
      // Generate a realistic wait time based on capacity utilization
      const utilizationRate = hospital.currentPatients / hospital.maxCapacity;
      let waitTime;
      
      if (utilizationRate < 0.5) {
        // Low capacity: 20-40 minutes
        waitTime = Math.floor(Math.random() * 21) + 20;
      } else if (utilizationRate < 0.75) {
        // Medium capacity: 40-70 minutes
        waitTime = Math.floor(Math.random() * 31) + 40;
      } else {
        // High capacity: 70-120 minutes
        waitTime = Math.floor(Math.random() * 51) + 70;
      }

      hospital.currentWait = waitTime;
      await hospital.save();
      
      console.log(`✅ ${hospital.name}`);
      console.log(`   Wait time: ${waitTime} minutes`);
      console.log(`   Capacity: ${hospital.currentPatients}/${hospital.maxCapacity} (${(utilizationRate * 100).toFixed(0)}%)\n`);
      updated++;
    }

    console.log('═══════════════════════════════════════');
    console.log(`✅ Successfully updated ${updated} hospital(s)`);
    console.log('═══════════════════════════════════════');

  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await mongoose.connection.close();
    console.log('\n👋 Database connection closed');
  }
}

// Run the script
addWaitTimes();

