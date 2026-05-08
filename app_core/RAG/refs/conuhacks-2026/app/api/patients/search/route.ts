import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Patient from '@/models/Patient';

// Mark route as dynamic since it uses searchParams
export const dynamic = 'force-dynamic';

/**
 * GET /api/patients/search
 * Search for patients by various criteria
 * Query parameters:
 * - name: Search by patient name (partial match)
 * - healthCardNumber: Exact health card number match
 * - dateOfBirth: Search by date of birth
 * - recent: Get recent patients (number of days)
 * - limit: Number of results to return (default 20, max 100)
 */
export async function GET(request: NextRequest) {
  try {
    await connectDB();

    const searchParams = request.nextUrl.searchParams;
    const name = searchParams.get('name');
    const healthCardNumber = searchParams.get('healthCardNumber');
    const dateOfBirth = searchParams.get('dateOfBirth');
    const phone = searchParams.get('phone');
    const recent = searchParams.get('recent');
    const limit = Math.min(parseInt(searchParams.get('limit') || '20'), 100);

    let query: any = { isActive: true };

    // Build search query
    if (name) {
      query['demographics.name'] = { $regex: name, $options: 'i' };
    }

    if (healthCardNumber) {
      query.healthCardNumber = healthCardNumber.toUpperCase().trim();
    }

    if (dateOfBirth) {
      query['demographics.dateOfBirth'] = dateOfBirth;
    }

    if (phone) {
      // Search for phone number (partial match, removing common formatting)
      const cleanPhone = phone.replace(/[\s\-\(\)\.]/g, '');
      query['contactInfo.phone'] = { $regex: cleanPhone, $options: 'i' };
    }

    if (recent) {
      const daysAgo = parseInt(recent);
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - daysAgo);
      query.lastVisit = { $gte: cutoffDate };
    }

    // Execute search
    const patients = await Patient.find(query)
      .sort({ lastVisit: -1 })
      .limit(limit)
      .select('-__v'); // Exclude version field

    // Return formatted results
    const results = patients.map(patient => ({
      id: patient._id,
      name: patient.demographics.name,
      dateOfBirth: patient.demographics.dateOfBirth,
      age: patient.demographics.age,
      sex: patient.demographics.sex,
      healthCardNumber: patient.demographics.healthCardNumber,
      phone: patient.contactInfo?.phone,
      email: patient.contactInfo?.email,
      totalVisits: patient.totalVisits,
      firstVisit: patient.firstVisit,
      lastVisit: patient.lastVisit,
      hasAllergies: patient.medicalHistory.allergies.length > 0,
      conditions: patient.medicalHistory.conditions,
      allergies: patient.medicalHistory.allergies,
    }));

    return NextResponse.json({ 
      success: true,
      count: results.length,
      patients: results,
      query: {
        name: name || undefined,
        healthCardNumber: healthCardNumber || undefined,
        dateOfBirth: dateOfBirth || undefined,
        recent: recent || undefined,
      }
    });
  } catch (error: any) {
    console.error('Error searching patients:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to search patients' 
    }, { status: 500 });
  }
}

