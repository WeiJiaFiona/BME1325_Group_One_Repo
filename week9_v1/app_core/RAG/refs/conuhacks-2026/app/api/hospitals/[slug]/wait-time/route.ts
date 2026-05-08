import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Hospital from '@/models/Hospital';

/**
 * PATCH /api/hospitals/[slug]/wait-time
 * Update hospital wait time
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: { slug: string } }
) {
  try {
    await connectDB();

    const slug = params.slug;
    const body = await request.json();
    const { currentWait } = body;

    if (currentWait === undefined || currentWait < 0) {
      return NextResponse.json({ 
        error: 'currentWait must be a positive number' 
      }, { status: 400 });
    }

    const hospital = await Hospital.findOne({ slug });
    if (!hospital) {
      return NextResponse.json({ 
        error: 'Hospital not found' 
      }, { status: 404 });
    }

    hospital.currentWait = currentWait;
    await hospital.save();

    console.log(`Updated wait time for ${hospital.name}: ${currentWait} minutes`);

    return NextResponse.json({ 
      success: true,
      message: 'Wait time updated',
      hospital: {
        id: hospital._id,
        name: hospital.name,
        currentWait: hospital.currentWait,
        currentPatients: hospital.currentPatients,
        maxCapacity: hospital.maxCapacity
      }
    });
  } catch (error: any) {
    console.error('Error updating wait time:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to update wait time' 
    }, { status: 500 });
  }
}

/**
 * GET /api/hospitals/[slug]/wait-time
 * Get current wait time for a hospital
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { slug: string } }
) {
  try {
    await connectDB();

    const slug = params.slug;

    const hospital = await Hospital.findOne({ slug }).select('name currentWait currentPatients maxCapacity');
    if (!hospital) {
      return NextResponse.json({ 
        error: 'Hospital not found' 
      }, { status: 404 });
    }

    return NextResponse.json({ 
      success: true,
      hospital: {
        id: hospital._id,
        name: hospital.name,
        currentWait: hospital.currentWait || 45,
        currentPatients: hospital.currentPatients,
        maxCapacity: hospital.maxCapacity,
        utilizationRate: ((hospital.currentPatients / hospital.maxCapacity) * 100).toFixed(1) + '%'
      }
    });
  } catch (error: any) {
    console.error('Error fetching wait time:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to fetch wait time' 
    }, { status: 500 });
  }
}

