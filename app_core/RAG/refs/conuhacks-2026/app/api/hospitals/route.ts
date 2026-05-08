import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Hospital from '@/models/Hospital';

// Helper function to generate URL-friendly slug from hospital name
function generateSlug(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD') // Decompose accented characters
    .replace(/[\u0300-\u036f]/g, '') // Remove diacritics
    .replace(/[^a-z0-9]+/g, '-') // Replace non-alphanumeric chars with hyphens
    .replace(/^-+|-+$/g, ''); // Remove leading/trailing hyphens
}

// Calculate distance between two coordinates (Haversine formula)
function calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = 
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

export async function GET(request: NextRequest) {
  try {
    await connectDB();

    const { searchParams } = new URL(request.url);
    const activeOnly = searchParams.get('activeOnly') === 'true';
    const slug = searchParams.get('slug');
    const latitude = searchParams.get('latitude');
    const longitude = searchParams.get('longitude');
    const triageLevel = searchParams.get('triageLevel');

    const query: any = {};
    if (activeOnly) {
      query.isActive = true;
    }
    if (slug) {
      query.slug = slug;
    }

    const hospitals = await Hospital.find(query)
      .sort({ name: 1 })
      .lean();

    console.log(`Found ${hospitals.length} hospitals`);
    console.log(`User location: lat=${latitude}, lon=${longitude}`);

    // Calculate available capacity and distance for each hospital
    let hospitalsWithData = hospitals.map((h: any) => {
      const hospitalData: any = {
        _id: h._id.toString(),
        id: h._id.toString(), // Keep for backward compatibility
        name: h.name,
        slug: h.slug || '', // Include slug for routing
        address: h.address,
        phone: h.phone || '',
        specialties: h.specialties || [], // Include specialties array
        latitude: h.latitude || null,
        longitude: h.longitude || null,
        currentWait: h.currentWait || 45, // Default wait time
        maxCapacity: h.maxCapacity || 100,
        currentPatients: h.currentPatients || 0,
        isActive: h.isActive !== undefined ? h.isActive : true,
        capacity: `${h.currentPatients || 0}/${h.maxCapacity || 100}`,
        availableCapacity: Math.max(0, (h.maxCapacity || 100) - (h.currentPatients || 0)),
        capacityPercentage: ((h.currentPatients || 0) / (h.maxCapacity || 100)) * 100,
      };

      console.log(`Hospital ${h.name}: lat=${h.latitude}, lon=${h.longitude}`);

      // Calculate distance if both user and hospital coordinates are available
      if (latitude && longitude && h.latitude != null && h.longitude != null && 
          !isNaN(parseFloat(latitude)) && !isNaN(parseFloat(longitude)) &&
          !isNaN(parseFloat(h.latitude)) && !isNaN(parseFloat(h.longitude))) {
        try {
          const dist = calculateDistance(
            parseFloat(latitude),
            parseFloat(longitude),
            parseFloat(h.latitude),
            parseFloat(h.longitude)
          );
          hospitalData.distance = Math.round(dist * 10) / 10; // Round to 1 decimal place
          console.log(`Distance to ${h.name}: ${hospitalData.distance} km`);
        } catch (err) {
          console.error(`Error calculating distance for ${h.name}:`, err);
          hospitalData.distance = null;
        }
      } else {
        hospitalData.distance = null;
        if (!latitude || !longitude) {
          console.log(`No user location provided for ${h.name}`);
        } else {
          console.log(`Hospital ${h.name} missing coordinates`);
        }
      }

      return hospitalData;
    });

    // Sort by distance if coordinates provided
    if (latitude && longitude) {
      // Separate hospitals with and without distance
      const withDistance = hospitalsWithData.filter(h => h.distance !== null);
      const withoutDistance = hospitalsWithData.filter(h => h.distance === null);
      
      // Sort those with distance by distance
      withDistance.sort((a, b) => (a.distance || 0) - (b.distance || 0));
      
      // Combine: hospitals with distance first (sorted), then those without
      hospitalsWithData = [...withDistance, ...withoutDistance].slice(0, 5);
    } else {
      // If no coordinates, just return all hospitals (limit to 10)
      hospitalsWithData = hospitalsWithData.slice(0, 10);
    }

    console.log(`Returning ${hospitalsWithData.length} hospitals`);
    return NextResponse.json({ hospitals: hospitalsWithData });
  } catch (error: any) {
    console.error('Error fetching hospitals:', error);
    return NextResponse.json({ error: error.message || 'Failed to fetch hospitals' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    await connectDB();

    const body = await request.json();
    const { name, address, city, phone, specialties, maxCapacity } = body;

    if (!name || !address || !maxCapacity) {
      return NextResponse.json({ error: 'Name, address, and maxCapacity are required' }, { status: 400 });
    }

    const slug = generateSlug(name);

    const hospital = new Hospital({
      name,
      slug,
      address,
      city: city || 'Montreal',
      phone,
      specialties: specialties || [],
      maxCapacity,
      currentPatients: 0,
      isActive: true,
    });

    await hospital.save();

    return NextResponse.json({ hospital }, { status: 201 });
  } catch (error: any) {
    console.error('Error creating hospital:', error);
    return NextResponse.json({ error: error.message || 'Failed to create hospital' }, { status: 500 });
  }
}
