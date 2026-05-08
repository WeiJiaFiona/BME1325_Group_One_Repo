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

async function addSlugsToHospitals() {
  try {
    console.log('🔌 Connecting to MongoDB...');
    await mongoose.connect(MONGODB_URI);
    console.log('✅ Connected to MongoDB');

    // Find all hospitals without slugs or with empty slugs
    const hospitals = await Hospital.find({
      $or: [
        { slug: { $exists: false } },
        { slug: null },
        { slug: '' }
      ]
    });

    console.log(`📋 Found ${hospitals.length} hospitals without slugs`);

    if (hospitals.length === 0) {
      console.log('✅ All hospitals already have slugs!');
      process.exit(0);
    }

    // Add slugs to each hospital
    let updated = 0;
    let errors = 0;

    for (const hospital of hospitals) {
      try {
        const slug = generateSlug(hospital.name);
        
        // Check if slug already exists
        const existing = await Hospital.findOne({ slug });
        if (existing && existing._id.toString() !== hospital._id.toString()) {
          // If slug exists for another hospital, append a number
          let uniqueSlug = slug;
          let counter = 1;
          while (await Hospital.findOne({ slug: uniqueSlug })) {
            uniqueSlug = `${slug}-${counter}`;
            counter++;
          }
          hospital.slug = uniqueSlug;
          console.log(`  ⚠️  "${hospital.name}" -> "${uniqueSlug}" (slug conflict resolved)`);
        } else {
          hospital.slug = slug;
          console.log(`  ✓ "${hospital.name}" -> "${slug}"`);
        }
        
        await hospital.save();
        updated++;
      } catch (error) {
        console.error(`  ❌ Error updating "${hospital.name}":`, error.message);
        errors++;
      }
    }

    console.log(`\n✅ Successfully updated ${updated} hospitals`);
    if (errors > 0) {
      console.log(`⚠️  ${errors} hospitals had errors`);
    }

    console.log('\n✨ Migration complete!');
    process.exit(0);
  } catch (error) {
    console.error('❌ Error adding slugs to hospitals:', error);
    process.exit(1);
  }
}

addSlugsToHospitals();
