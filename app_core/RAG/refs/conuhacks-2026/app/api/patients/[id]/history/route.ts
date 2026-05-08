import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Patient from '@/models/Patient';
import Case from '@/models/Case';

/**
 * GET /api/patients/[id]/history
 * Fetch comprehensive patient medical history including all cases
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const patientId = params.id;

    const patient = await Patient.findById(patientId);
    if (!patient) {
      return NextResponse.json({ 
        error: 'Patient not found' 
      }, { status: 404 });
    }

    // Fetch all cases linked to this patient
    const cases = await Case.find({ 
      'user.patientId': patientId 
    }).sort({ createdAt: -1 });

    // Build comprehensive medical history
    const medicalHistory = {
      patient: {
        id: patient._id,
        name: patient.demographics.name,
        dateOfBirth: patient.demographics.dateOfBirth,
        age: patient.demographics.age,
        sex: patient.demographics.sex,
        healthCardNumber: patient.demographics.healthCardNumber,
      },
      
      medicalHistory: {
        conditions: patient.medicalHistory.conditions,
        medications: patient.medicalHistory.medications,
        allergies: patient.medicalHistory.allergies,
        lastUpdated: patient.medicalHistory.lastUpdated,
      },
      
      visitHistory: patient.visits.map((visit: any) => ({
        caseId: visit.caseId,
        visitDate: visit.visitDate,
        chiefComplaint: visit.chiefComplaint,
        triageLevel: visit.triageLevel,
        hospitalName: visit.hospitalName,
        outcome: visit.outcome,
      })),
      
      detailedCases: cases.map(caseDoc => ({
        id: caseDoc._id,
        createdAt: caseDoc.createdAt,
        status: caseDoc.status,
        workflowStatus: caseDoc.workflowStatus,
        assessmentType: caseDoc.assessmentType,
        
        intake: {
          chiefComplaint: caseDoc.intake.chiefComplaint,
          symptoms: caseDoc.intake.symptoms,
          severity: caseDoc.intake.severity,
          onset: caseDoc.intake.onset,
          redFlags: caseDoc.intake.redFlags,
          vitals: caseDoc.intake.vitals,
        },
        
        triage: {
          level: caseDoc.assistant.triageLevel,
          confidence: caseDoc.assistant.confidence,
          reasons: caseDoc.assistant.reasons,
          nextSteps: caseDoc.assistant.nextSteps,
        },
        
        hospital: caseDoc.hospitalRouting ? {
          hospitalName: caseDoc.hospitalRouting.hospitalName,
          routedAt: caseDoc.hospitalRouting.routedAt,
          checkedInAt: caseDoc.hospitalRouting.checkedInAt,
        } : null,
        
        adminReview: caseDoc.adminReview ? {
          reviewed: caseDoc.adminReview.reviewed,
          adminTriageLevel: caseDoc.adminReview.adminTriageLevel,
          adminNotes: caseDoc.adminReview.adminNotes,
          onWatchList: caseDoc.adminReview.onWatchList,
        } : null,
      })),
      
      statistics: {
        totalVisits: patient.totalVisits,
        firstVisit: patient.firstVisit,
        lastVisit: patient.lastVisit,
        emergencyVisits: cases.filter(c => c.assistant.triageLevel === 'EMERGENCY').length,
        urgentVisits: cases.filter(c => c.assistant.triageLevel === 'URGENT').length,
        routineVisits: cases.filter(c => c.assistant.triageLevel === 'NON_URGENT' || c.assistant.triageLevel === 'SELF_CARE').length,
      },
    };

    return NextResponse.json({ 
      success: true,
      medicalHistory 
    });
  } catch (error: any) {
    console.error('Error fetching patient history:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to fetch patient history' 
    }, { status: 500 });
  }
}

