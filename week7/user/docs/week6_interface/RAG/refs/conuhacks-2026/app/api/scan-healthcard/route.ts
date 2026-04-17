import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import { GoogleGenerativeAI } from '@google/generative-ai';

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

async function extractHealthCardData(imageBase64: string) {
  if (!GEMINI_API_KEY) {
    throw new Error('GEMINI_API_KEY is not configured');
  }

  const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
  const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash' });

  // Remove data URL prefix if present
  const base64Data = imageBase64.includes(',') 
    ? imageBase64.split(',')[1] 
    : imageBase64;

  const prompt = `You are analyzing a health card image. Extract the following information if visible and return it as JSON:

{
  "name": "Full name if visible, or null",
  "dateOfBirth": "Date of birth in YYYY-MM-DD format if visible, or null",
  "healthCardNumber": "Health card number if visible, or null",
  "versionCode": "Version code if visible, or null",
  "expiryDate": "Expiry date in YYYY-MM-DD format if visible, or null",
  "sex": "Sex/gender if visible (M/F), or null",
  "confidence": "high/medium/low based on image quality"
}

IMPORTANT: 
- Only extract clearly visible text
- Return null for any field that's not clearly readable
- Be conservative - if unsure, return null
- Return ONLY valid JSON, no additional text
- Dates must be in YYYY-MM-DD format`;

  try {
    const result = await model.generateContent([
      prompt,
      {
        inlineData: {
          data: base64Data,
          mimeType: 'image/jpeg'
        }
      }
    ]);

    const response = result.response;
    const text = response.text();
    
    // Extract JSON from response
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const extractedData = JSON.parse(jsonMatch[0]);
      return extractedData;
    }
    
    throw new Error('Could not parse health card data');
  } catch (error) {
    console.error('Error with Gemini OCR:', error);
    throw error;
  }
}

export async function POST(request: NextRequest) {
  try {
    await connectDB();

    const body = await request.json();
    const { caseId, image } = body;

    if (!caseId || !image) {
      return NextResponse.json({ error: 'caseId and image are required' }, { status: 400 });
    }

    // Extract data from health card using Gemini Vision
    let extractedData;
    try {
      extractedData = await extractHealthCardData(image);
    } catch (ocrError: any) {
      console.error('OCR failed:', ocrError);
      return NextResponse.json({ 
        success: false,
        error: 'Could not read health card. Please enter information manually.',
        extractedData: null
      }, { status: 200 }); // Still 200 so UI can handle gracefully
    }

    // Calculate actual age from date of birth for preview
    let actualAge = undefined;
    if (extractedData.dateOfBirth) {
      try {
        const dob = new Date(extractedData.dateOfBirth);
        const today = new Date();
        let age = today.getFullYear() - dob.getFullYear();
        const monthDiff = today.getMonth() - dob.getMonth();
        
        // Adjust age if birthday hasn't occurred yet this year
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
          age--;
        }
        
        actualAge = age;
      } catch (err) {
        console.error('Error calculating age:', err);
      }
    }

    console.log('Health card scanned successfully for case:', caseId);
    console.log('Extracted data confidence:', extractedData.confidence);

    // Return extracted data for verification - don't save to database yet
    return NextResponse.json({ 
      success: true,
      message: 'Health card scanned successfully',
      extractedData: {
        ageSet: !!extractedData.dateOfBirth,
        age: actualAge,
        dateOfBirthCaptured: !!extractedData.dateOfBirth,
        confidence: extractedData.confidence,
        fieldsExtracted: {
          name: !!extractedData.name,
          dateOfBirth: !!extractedData.dateOfBirth,
          sex: !!extractedData.sex,
          healthCardNumber: !!extractedData.healthCardNumber,
          versionCode: !!extractedData.versionCode,
          expiryDate: !!extractedData.expiryDate
        }
      },
      rawData: {
        name: extractedData.name || null,
        healthCardNumber: extractedData.healthCardNumber || null,
        versionCode: extractedData.versionCode || null,
        dateOfBirth: extractedData.dateOfBirth || null,
        sex: extractedData.sex || null,
        expiryDate: extractedData.expiryDate || null
      }
    });
  } catch (error: any) {
    console.error('Error processing health card:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to process health card' 
    }, { status: 500 });
  }
}

