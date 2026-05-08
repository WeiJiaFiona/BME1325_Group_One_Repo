import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Hospital from '@/models/Hospital';

export async function PATCH(
  request: NextRequest,
  { params }: { params: { slug: string } }
) {
  try {
    await connectDB();

    const { slug } = params;
    const body = await request.json();
    const { currentPatients, isActive } = body;

    const hospital = await Hospital.findOne({ slug });

    if (!hospital) {
      return NextResponse.json({ error: 'Hospital not found' }, { status: 404 });
    }

    if (currentPatients !== undefined) {
      if (currentPatients < 0 || currentPatients > hospital.maxCapacity) {
        return NextResponse.json({ error: 'Invalid patient count' }, { status: 400 });
      }
      hospital.currentPatients = currentPatients;
    }

    if (isActive !== undefined) {
      hospital.isActive = isActive;
    }

    await hospital.save();

    const hospitalWithCapacity = {
      ...hospital.toObject(),
      availableCapacity: Math.max(0, hospital.maxCapacity - hospital.currentPatients),
      capacityPercentage: (hospital.currentPatients / hospital.maxCapacity) * 100,
    };

    return NextResponse.json({ hospital: hospitalWithCapacity });
  } catch (error: any) {
    console.error('Error updating hospital:', error);
    return NextResponse.json({ error: error.message || 'Failed to update hospital' }, { status: 500 });
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { slug: string } }
) {
  try {
    await connectDB();

    const { slug } = params;
    const hospital = await Hospital.findOne({ slug });

    if (!hospital) {
      return NextResponse.json({ error: 'Hospital not found' }, { status: 404 });
    }

    const hospitalWithCapacity = {
      ...hospital.toObject(),
      availableCapacity: Math.max(0, hospital.maxCapacity - hospital.currentPatients),
      capacityPercentage: (hospital.currentPatients / hospital.maxCapacity) * 100,
    };

    return NextResponse.json({ hospital: hospitalWithCapacity });
  } catch (error: any) {
    console.error('Error fetching hospital:', error);
    return NextResponse.json({ error: error.message || 'Failed to fetch hospital' }, { status: 500 });
  }
}

