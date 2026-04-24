import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import Hospital from '@/models/Hospital';
import { v4 as uuidv4 } from 'uuid';

export async function POST(request: NextRequest) {
  try {
    // Check if request was aborted before starting
    if (request.signal?.aborted) {
      return NextResponse.json({ error: 'Request aborted' }, { status: 499 });
    }

    const connectStart = Date.now();
    await connectDB();
    const connectTime = Date.now() - connectStart;
    
    // Log if connection took a long time (might indicate paused cluster)
    if (connectTime > 5000) {
      console.log(`⚠️  MongoDB connection took ${connectTime}ms (cluster may have been paused)`);
    }

    // Check if request was aborted after connection
    if (request.signal?.aborted) {
      return NextResponse.json({ error: 'Request aborted' }, { status: 499 });
    }

    const body = await request.json();
    const { anonymousId, assessmentType, location, hospitalId, hospitalSlug } = body;

    if (!anonymousId) {
      return NextResponse.json({ error: 'anonymousId is required' }, { status: 400 });
    }

    // Prepare hospital routing if hospital is specified
    let hospitalRouting = undefined;
    if (hospitalId || hospitalSlug) {
      const hospital = hospitalId 
        ? await Hospital.findById(hospitalId)
        : await Hospital.findOne({ slug: hospitalSlug });

      if (hospital) {
        hospitalRouting = {
          hospitalId: hospital._id.toString(),
          hospitalSlug: hospital.slug,
          hospitalName: hospital.name,
          hospitalAddress: hospital.address,
          routedAt: new Date(),
          routedBy: 'qr-code-intake',
        };
      }
    }

    // CRITICAL: If hospital is specified, automatically set assessmentType to in_hospital
    const finalAssessmentType = (hospitalId || hospitalSlug) ? 'in_hospital' : (assessmentType || 'remote');

    const newCase = new Case({
      status: 'in_progress',
      workflowStatus: hospitalRouting ? 'confirmed_hospital' : 'pending_review',
      assessmentType: finalAssessmentType,
      location: location || undefined,
      hospitalRouting,
      user: {
        anonymousId,
      },
      intake: {
        symptoms: [],
        redFlags: { any: 'unknown', details: [] },
        history: { conditions: [], meds: [], allergies: [] },
        vitals: {},
      },
      assistant: {
        reasons: [],
        nextSteps: [],
        monitoringPlan: [],
        escalationTriggers: [],
        questionsAsked: [],
        disclaimerShown: false,
      },
    });

    await newCase.save();

    return NextResponse.json({ case: newCase }, { status: 201 });
  } catch (error: any) {
    // Handle client disconnection gracefully
    if (error.code === 'ECONNRESET' || error.message === 'aborted' || error.message?.includes('aborted')) {
      console.log('⚠️  Client disconnected before request completed (this is usually OK if operation succeeded)');
      // Don't return error - the operation may have succeeded
      // Return a 499 (Client Closed Request) status
      return NextResponse.json({ 
        error: 'Client disconnected',
        note: 'Operation may have completed successfully. Please check your case list.'
      }, { status: 499 });
    }
    
    console.error('Error creating case:', error);
    return NextResponse.json({ error: error.message || 'Failed to create case' }, { status: 500 });
  }
}

