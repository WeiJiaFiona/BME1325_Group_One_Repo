const mongoose = require('mongoose');
const fs = require('fs');
const path = require('path');

// Read .env.local file
function getEnvVar(key) {
  const envPath = path.join(__dirname, '..', '.env.local');
  if (fs.existsSync(envPath)) {
    const content = fs.readFileSync(envPath, 'utf-8');
    const lines = content.split('\n');
    for (const line of lines) {
      const match = line.match(new RegExp(`^${key}=(.*)$`));
      if (match) {
        return match[1].trim();
      }
    }
  }
  return null;
}

const MONGODB_URI = getEnvVar('MONGODB_URI') || process.env.MONGODB_URI;

if (!MONGODB_URI) {
  console.error('❌ MONGODB_URI not found in .env.local or environment variables');
  process.exit(1);
}

// Hospital coordinates mapping
const hospitalCoordinates = {
  'Montreal General Hospital': { latitude: 45.4972, longitude: -73.5794 },
  'Royal Victoria Hospital': { latitude: 45.4969, longitude: -73.5790 },
  'Jewish General Hospital': { latitude: 45.4958, longitude: -73.6281 },
  'CHU Sainte-Justine': { latitude: 45.4950, longitude: -73.6250 },
  'Hôpital Notre-Dame': { latitude: 45.5200, longitude: -73.5600 },
  'Hôpital du Sacré-Cœur de Montréal': { latitude: 45.5500, longitude: -73.6500 },
  "St. Mary's Hospital": { latitude: 45.4950, longitude: -73.6250 },
  'Montreal Chest Institute': { latitude: 45.5100, longitude: -73.5700 },
};

// Hospital Schema
const HospitalSchema = new mongoose.Schema({
  name: { type: String, required: true },
  slug: { type: String, required: true, unique: true },
  address: { type: String, required: true },
  city: { type: String, required: true, default: 'Montreal' },
  phone: String,
  specialties: { type: [String], default: [] },
  maxCapacity: { type: Number, required: true, default: 100 },
  currentPatients: { type: Number, default: 0 },
  latitude: Number,
  longitude: Number,
  currentWait: { type: Number, default: 45 },
  isActive: { type: Boolean, default: true },
}, {
  timestamps: true,
});

const Hospital = mongoose.models.Hospital || mongoose.model('Hospital', HospitalSchema);

async function updateHospitalCoordinates() {
  try {
    console.log('🔌 Connecting to MongoDB...');
    await mongoose.connect(MONGODB_URI);
    console.log('✅ Connected to MongoDB');

    const hospitals = await Hospital.find({});
    console.log(`📋 Found ${hospitals.length} hospitals`);

    let updated = 0;
    let skipped = 0;

    for (const hospital of hospitals) {
      const coords = hospitalCoordinates[hospital.name];
      
      if (coords) {
        if (hospital.latitude !== coords.latitude || hospital.longitude !== coords.longitude) {
          hospital.latitude = coords.latitude;
          hospital.longitude = coords.longitude;
          await hospital.save();
          console.log(`✅ Updated coordinates for ${hospital.name}`);
          updated++;
        } else {
          console.log(`⏭️  ${hospital.name} already has correct coordinates`);
          skipped++;
        }
      } else {
        console.log(`⚠️  No coordinates found for ${hospital.name}`);
        skipped++;
      }
    }

    console.log(`\n✨ Update complete! Updated: ${updated}, Skipped: ${skipped}`);
    process.exit(0);
  } catch (error) {
    console.error('❌ Error updating hospital coordinates:', error);
    process.exit(1);
  }
}

updateHospitalCoordinates();

