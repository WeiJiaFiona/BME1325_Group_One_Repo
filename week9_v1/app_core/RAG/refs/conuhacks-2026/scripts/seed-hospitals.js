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

// Helper function to generate URL-friendly slug from hospital name
function generateSlug(name) {
  return name
    .toLowerCase()
    .normalize('NFD') // Decompose accented characters
    .replace(/[\u0300-\u036f]/g, '') // Remove diacritics
    .replace(/[^a-z0-9]+/g, '-') // Replace non-alphanumeric chars with hyphens
    .replace(/^-+|-+$/g, ''); // Remove leading/trailing hyphens
}

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
  isActive: { type: Boolean, default: true },
}, {
  timestamps: true,
});

const Hospital = mongoose.models.Hospital || mongoose.model('Hospital', HospitalSchema);



// Montreal Hospitals Data with coordinates
const montrealHospitalsData = [

  {
    name: 'Montreal General Hospital',
    address: '1650 Cedar Avenue, Montreal, QC H3G 1A4',
    city: 'Montreal',
    phone: '(514) 934-1934',
    specialties: ['Emergency', 'Trauma', 'Surgery', 'Cardiology', 'Neurology'],
    maxCapacity: 150,
    currentPatients: 0,
    latitude: 45.4972,
    longitude: -73.5794,
    isActive: true,
  },
  {
    name: 'Royal Victoria Hospital',
    address: '1001 Decarie Boulevard, Montreal, QC H4A 3J1',
    city: 'Montreal',
    phone: '(514) 934-1934',
    specialties: ['Emergency', 'Maternity', 'Pediatrics', 'Oncology'],
    maxCapacity: 120,
    currentPatients: 0,
    latitude: 45.4969,
    longitude: -73.5790,
    isActive: true,
  },
  {
    name: 'Jewish General Hospital',
    address: '3755 Cote-Sainte-Catherine Road, Montreal, QC H3T 1E2',
    city: 'Montreal',
    phone: '(514) 340-8222',
    specialties: ['Emergency', 'General Medicine', 'Geriatrics', 'Psychiatry'],
    maxCapacity: 180,
    currentPatients: 0,
    latitude: 45.4958,
    longitude: -73.6281,
    isActive: true,
  },
  {
    name: 'CHU Sainte-Justine',
    address: '3175 Cote-Sainte-Catherine Road, Montreal, QC H3T 1C5',
    city: 'Montreal',
    phone: '(514) 345-4931',
    specialties: ['Pediatrics', 'Maternity', 'Emergency', 'Surgery'],
    maxCapacity: 100,
    currentPatients: 0,
    latitude: 45.4950,
    longitude: -73.6250,
    isActive: true,
  },
  {
    name: 'Hôpital Notre-Dame',
    address: '1560 Sherbrooke Street East, Montreal, QC H2L 4M1',
    city: 'Montreal',
    phone: '(514) 890-8000',
    specialties: ['Emergency', 'Trauma', 'Orthopedics', 'General Medicine'],
    maxCapacity: 130,
    currentPatients: 0,
    latitude: 45.5200,
    longitude: -73.5600,
    isActive: true,
  },
  {
    name: 'Hôpital du Sacré-Cœur de Montréal',
    address: '5400 Gouin Boulevard West, Montreal, QC H4J 1C5',
    city: 'Montreal',
    phone: '(514) 338-2222',
    specialties: ['Emergency', 'Cardiology', 'Respiratory', 'Intensive Care'],
    maxCapacity: 110,
    currentPatients: 0,
    latitude: 45.5500,
    longitude: -73.6500,
    isActive: true,
  },
  {
    name: 'St. Mary\'s Hospital',
    address: '3830 Lacombe Avenue, Montreal, QC H3T 1M5',
    city: 'Montreal',
    phone: '(514) 345-3511',
    specialties: ['Emergency', 'Family Medicine', 'Geriatrics', 'Rehabilitation'],
    maxCapacity: 90,
    currentPatients: 0,
    latitude: 45.4950,
    longitude: -73.6250,
    isActive: true,
  },
  {
    name: 'Montreal Chest Institute',
    address: '3650 St. Urbain Street, Montreal, QC H2X 2P4',
    city: 'Montreal',
    phone: '(514) 934-1934',
    specialties: ['Respiratory', 'Emergency', 'Pulmonology', 'Critical Care'],
    maxCapacity: 80,
    currentPatients: 0,
    latitude: 45.5100,
    longitude: -73.5700,
    isActive: true,
  },
];

// Add slugs to all hospitals
const montrealHospitals = montrealHospitalsData.map(hospital => ({
  ...hospital,
  slug: generateSlug(hospital.name)
}));

async function seedHospitals() {
  try {
    console.log('🔌 Connecting to MongoDB...');
    await mongoose.connect(MONGODB_URI);
    console.log('✅ Connected to MongoDB');

    // Clear existing hospitals
    console.log('🗑️  Clearing existing hospitals...');
    await Hospital.deleteMany({});
    console.log('✅ Cleared existing hospitals');

    // Insert new hospitals
    console.log('📝 Inserting Montreal hospitals...');
    const inserted = await Hospital.insertMany(montrealHospitals);
    console.log(`✅ Successfully inserted ${inserted.length} hospitals`);

    console.log('\n📋 Hospitals in database:');
    inserted.forEach((h, idx) => {
      console.log(`${idx + 1}. ${h.name} - Capacity: ${h.maxCapacity} (Available: ${h.maxCapacity - h.currentPatients})`);
    });

    console.log('\n✨ Seeding complete!');
    process.exit(0);
  } catch (error) {
    console.error('❌ Error seeding hospitals:', error);
    process.exit(1);
  }
}

seedHospitals();

