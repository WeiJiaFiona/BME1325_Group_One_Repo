import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Patient from '@/models/Patient';
import Case from '@/models/Case';

// Mark route as dynamic since it uses searchParams
export const dynamic = 'force-dynamic';

/**
 * GET /api/patients/stats
 * Get system-wide patient statistics for administrative dashboards
 */
export async function GET(request: NextRequest) {
  try {
    await connectDB();

    const searchParams = request.nextUrl.searchParams;
    const period = searchParams.get('period') || '30'; // days
    const daysAgo = parseInt(period);
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - daysAgo);

    // Total patients
    const totalPatients = await Patient.countDocuments({ isActive: true });

    // New patients in period
    const newPatients = await Patient.countDocuments({
      isActive: true,
      createdAt: { $gte: cutoffDate }
    });

    // Patients with recent visits
    const recentVisits = await Patient.countDocuments({
      isActive: true,
      lastVisit: { $gte: cutoffDate }
    });

    // Total visits across all patients
    const allPatients = await Patient.find({ isActive: true });
    const totalVisits = allPatients.reduce((sum, p) => sum + p.totalVisits, 0);

    // Average visits per patient
    const avgVisitsPerPatient = totalPatients > 0 
      ? parseFloat((totalVisits / totalPatients).toFixed(2))
      : 0;

    // Patients with allergies
    const patientsWithAllergies = await Patient.countDocuments({
      isActive: true,
      'medicalHistory.allergies.0': { $exists: true }
    });

    // Patients with chronic conditions
    const patientsWithConditions = await Patient.countDocuments({
      isActive: true,
      'medicalHistory.conditions.0': { $exists: true }
    });

    // Most common conditions (top 10)
    const conditionsAggregation = await Patient.aggregate([
      { $match: { isActive: true } },
      { $unwind: '$medicalHistory.conditions' },
      { $group: { 
        _id: '$medicalHistory.conditions', 
        count: { $sum: 1 } 
      }},
      { $sort: { count: -1 } },
      { $limit: 10 }
    ]);

    // Most common allergies (top 10)
    const allergiesAggregation = await Patient.aggregate([
      { $match: { isActive: true } },
      { $unwind: '$medicalHistory.allergies' },
      { $group: { 
        _id: '$medicalHistory.allergies', 
        count: { $sum: 1 } 
      }},
      { $sort: { count: -1 } },
      { $limit: 10 }
    ]);

    // Demographics breakdown
    const sexDistribution = await Patient.aggregate([
      { $match: { isActive: true } },
      { $group: { 
        _id: '$demographics.sex', 
        count: { $sum: 1 } 
      }}
    ]);

    // Age distribution (by decade)
    const ageDistribution = await Patient.aggregate([
      { $match: { isActive: true, 'demographics.age': { $exists: true } } },
      { $bucket: {
        groupBy: '$demographics.age',
        boundaries: [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120],
        default: 'Unknown',
        output: { count: { $sum: 1 } }
      }}
    ]);

    // Recent case statistics (for context)
    const recentCases = await Case.countDocuments({
      createdAt: { $gte: cutoffDate }
    });

    const casesWithPatients = await Case.countDocuments({
      'user.patientId': { $exists: true, $ne: null },
      createdAt: { $gte: cutoffDate }
    });

    const patientLinkageRate = recentCases > 0
      ? parseFloat(((casesWithPatients / recentCases) * 100).toFixed(1))
      : 0;

    // Top returning patients
    const topReturningPatients = await Patient.find({ 
      isActive: true,
      totalVisits: { $gt: 1 }
    })
    .sort({ totalVisits: -1 })
    .limit(10)
    .select('demographics.name demographics.age totalVisits lastVisit');

    // Build response
    const stats = {
      overview: {
        totalPatients,
        newPatients: {
          count: newPatients,
          period: `${period} days`
        },
        recentVisits: {
          count: recentVisits,
          period: `${period} days`
        },
        totalVisits,
        avgVisitsPerPatient
      },

      medicalData: {
        patientsWithAllergies,
        patientsWithConditions,
        allergyRate: totalPatients > 0 
          ? ((patientsWithAllergies / totalPatients) * 100).toFixed(1) + '%'
          : '0%',
        chronicConditionRate: totalPatients > 0
          ? ((patientsWithConditions / totalPatients) * 100).toFixed(1) + '%'
          : '0%'
      },

      topConditions: conditionsAggregation.map(c => ({
        condition: c._id,
        count: c.count,
        percentage: totalPatients > 0 
          ? ((c.count / totalPatients) * 100).toFixed(1) + '%'
          : '0%'
      })),

      topAllergies: allergiesAggregation.map(a => ({
        allergy: a._id,
        count: a.count,
        percentage: totalPatients > 0
          ? ((a.count / totalPatients) * 100).toFixed(1) + '%'
          : '0%'
      })),

      demographics: {
        sexDistribution: sexDistribution.map(s => ({
          sex: s._id || 'Unknown',
          count: s.count,
          percentage: totalPatients > 0
            ? ((s.count / totalPatients) * 100).toFixed(1) + '%'
            : '0%'
        })),
        ageDistribution: ageDistribution.map(a => ({
          ageRange: a._id === 'Unknown' ? 'Unknown' : `${a._id}-${a._id + 9}`,
          count: a.count,
          percentage: totalPatients > 0
            ? ((a.count / totalPatients) * 100).toFixed(1) + '%'
            : '0%'
        }))
      },

      systemHealth: {
        recentCases,
        casesWithPatients,
        patientLinkageRate: patientLinkageRate.toFixed(1) + '%',
        message: patientLinkageRate > 80 
          ? 'Excellent patient tracking'
          : patientLinkageRate > 50
          ? 'Good patient tracking'
          : 'Consider improving patient identification'
      },

      topReturningPatients: topReturningPatients.map(p => ({
        id: p._id,
        name: p.demographics.name,
        age: p.demographics.age,
        totalVisits: p.totalVisits,
        lastVisit: p.lastVisit
      })),

      periodAnalyzed: {
        days: daysAgo,
        from: cutoffDate,
        to: new Date()
      }
    };

    return NextResponse.json({ 
      success: true,
      stats
    });
  } catch (error: any) {
    console.error('Error fetching patient statistics:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to fetch statistics' 
    }, { status: 500 });
  }
}

