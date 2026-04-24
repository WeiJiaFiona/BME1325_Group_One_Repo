import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';

/**
 * POST /api/cases/[id]/upload-media
 * Upload images and save additional comments for a case
 */
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const caseId = params.id;
    const body = await request.json();
    const { images, additionalComments } = body;

    if (!images && !additionalComments) {
      return NextResponse.json({ 
        error: 'At least one of images or additionalComments must be provided' 
      }, { status: 400 });
    }

    const caseDoc = await Case.findById(caseId);
    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Update images if provided
    if (images && Array.isArray(images)) {
      // Validate images are base64 strings
      const validImages = images.filter(img => {
        if (typeof img !== 'string') return false;
        // Check if it's a data URL or base64 string
        return img.startsWith('data:image/') || /^[A-Za-z0-9+/=]+$/.test(img);
      });

      if (!caseDoc.intake.uploadedImages) {
        caseDoc.intake.uploadedImages = [];
      }
      
      // Add new images (avoid duplicates)
      validImages.forEach(img => {
        if (!caseDoc.intake.uploadedImages!.includes(img)) {
          caseDoc.intake.uploadedImages!.push(img);
        }
      });
    }

    // Update comments if provided
    if (additionalComments !== undefined) {
      caseDoc.intake.additionalComments = additionalComments;
    }

    await caseDoc.save();

    console.log(`Media uploaded for case ${caseId}: ${images?.length || 0} images, comments: ${!!additionalComments}`);

    return NextResponse.json({
      success: true,
      message: 'Media and comments saved successfully',
      case: {
        _id: caseDoc._id,
        uploadedImages: caseDoc.intake.uploadedImages,
        additionalComments: caseDoc.intake.additionalComments
      }
    });
  } catch (error: any) {
    console.error('Error uploading media:', error);
    return NextResponse.json({
      error: error.message || 'Failed to upload media'
    }, { status: 500 });
  }
}

/**
 * GET /api/cases/[id]/upload-media
 * Get uploaded images and comments for a case
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const caseId = params.id;

    const caseDoc = await Case.findById(caseId).select('intake.uploadedImages intake.additionalComments');
    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    return NextResponse.json({
      success: true,
      uploadedImages: caseDoc.intake.uploadedImages || [],
      additionalComments: caseDoc.intake.additionalComments || ''
    });
  } catch (error: any) {
    console.error('Error fetching media:', error);
    return NextResponse.json({
      error: error.message || 'Failed to fetch media'
    }, { status: 500 });
  }
}

