import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import Hospital from '@/models/Hospital';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const caseDoc = await Case.findById(id).lean();

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    return NextResponse.json({ case: caseDoc });
  } catch (error: any) {
    console.error('Error fetching case:', error);
    return NextResponse.json({ error: error.message || 'Failed to fetch case' }, { status: 500 });
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const body = await request.json();
    const { phone, hospitalRouting } = body;

    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Update phone number
    if (phone !== undefined) {
      caseDoc.user.phone = phone;
    }

    // Update hospital routing
    if (hospitalRouting !== undefined) {
      if (!caseDoc.hospitalRouting) {
        caseDoc.hospitalRouting = {};
      }
      if (hospitalRouting.hospitalId) {
        caseDoc.hospitalRouting.hospitalId = hospitalRouting.hospitalId;
        // If hospitalId is provided but slug is not, look it up
        if (!hospitalRouting.hospitalSlug) {
          const hospital = await Hospital.findById(hospitalRouting.hospitalId);
          if (hospital) {
            caseDoc.hospitalRouting.hospitalSlug = hospital.slug;
          }
        }
      }
      if (hospitalRouting.hospitalSlug) {
        caseDoc.hospitalRouting.hospitalSlug = hospitalRouting.hospitalSlug;
      }
      if (hospitalRouting.hospitalName) {
        caseDoc.hospitalRouting.hospitalName = hospitalRouting.hospitalName;
      }
      if (hospitalRouting.hospitalAddress) {
        caseDoc.hospitalRouting.hospitalAddress = hospitalRouting.hospitalAddress;
      }
      if (hospitalRouting.routedAt) {
        caseDoc.hospitalRouting.routedAt = new Date(hospitalRouting.routedAt);
      }
      if (hospitalRouting.routedBy) {
        caseDoc.hospitalRouting.routedBy = hospitalRouting.routedBy;
      }
    }

    await caseDoc.save();

    return NextResponse.json({ case: caseDoc });
  } catch (error: any) {
    console.error('Error updating case:', error);
    return NextResponse.json({ error: error.message || 'Failed to update case' }, { status: 500 });
  }
}
