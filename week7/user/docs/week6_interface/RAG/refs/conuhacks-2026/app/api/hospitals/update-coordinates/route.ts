import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Hospital from '@/models/Hospital';

// Hospital coordinates mapping
const hospitalCoordinates: { [key: string]: { latitude: number; longitude: number } } = {
  'Montreal General Hospital': { latitude: 45.4972, longitude: -73.5794 },
  'Royal Victoria Hospital': { latitude: 45.4969, longitude: -73.5790 },
  'Jewish General Hospital': { latitude: 45.4958, longitude: -73.6281 },
  'CHU Sainte-Justine': { latitude: 45.4950, longitude: -73.6250 },
  'Hôpital Notre-Dame': { latitude: 45.5200, longitude: -73.5600 },
  'Hôpital du Sacré-Cœur de Montréal': { latitude: 45.5500, longitude: -73.6500 },
  "St. Mary's Hospital": { latitude: 45.4950, longitude: -73.6250 },
  'Montreal Chest Institute': { latitude: 45.5100, longitude: -73.5700 },
};

export async function POST(request: NextRequest) {
  try {
    await connectDB();

    const hospitals = await Hospital.find({});
    console.log(`Found ${hospitals.length} hospitals to update`);

    let updated = 0;
    let skipped = 0;
    const results: string[] = [];

    for (const hospital of hospitals) {
      const coords = hospitalCoordinates[hospital.name];
      
      if (coords) {
        if (hospital.latitude !== coords.latitude || hospital.longitude !== coords.longitude) {
          hospital.latitude = coords.latitude;
          hospital.longitude = coords.longitude;
          await hospital.save();
          results.push(`✅ Updated coordinates for ${hospital.name}`);
          updated++;
        } else {
          results.push(`⏭️  ${hospital.name} already has correct coordinates`);
          skipped++;
        }
      } else {
        results.push(`⚠️  No coordinates found for ${hospital.name}`);
        skipped++;
      }
    }

    return NextResponse.json({ 
      success: true,
      message: `Update complete! Updated: ${updated}, Skipped: ${skipped}`,
      updated,
      skipped,
      results
    });
  } catch (error: any) {
    console.error('Error updating hospital coordinates:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to update hospital coordinates' 
    }, { status: 500 });
  }
}

