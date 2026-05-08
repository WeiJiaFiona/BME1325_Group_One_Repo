import { NextResponse } from 'next/server';
import { getConnectionStatus } from '@/lib/mongodb';
import connectDB from '@/lib/mongodb';
import mongoose from 'mongoose';

/**
 * GET /api/debug/mongodb
 * Debug endpoint to check MongoDB connection status
 */
export async function GET() {
  try {
    const status = getConnectionStatus();
    
    // Try to ping the database if connected
    let pingResult = null;
    if (status.isConnected && mongoose.connection.db) {
      try {
        const pingStart = Date.now();
        await mongoose.connection.db.admin().ping();
        pingResult = {
          success: true,
          latency: Date.now() - pingStart,
        };
      } catch (pingError: any) {
        pingResult = {
          success: false,
          error: pingError.message,
        };
      }
    }

    // Try to force a connection attempt
    let connectionAttempt = null;
    try {
      const connectStart = Date.now();
      await connectDB();
      connectionAttempt = {
        success: true,
        time: Date.now() - connectStart,
      };
    } catch (connectError: any) {
      connectionAttempt = {
        success: false,
        error: connectError.message,
        name: connectError.name,
      };
    }

    return NextResponse.json({
      timestamp: new Date().toISOString(),
      connectionStatus: status,
      ping: pingResult,
      connectionAttempt,
      environment: {
        hasMongoUri: !!process.env.MONGODB_URI,
        mongoUriPreview: process.env.MONGODB_URI
          ? process.env.MONGODB_URI.replace(/:[^:@]+@/, ':****@').split('?')[0]
          : 'not set',
        debugMode: process.env.MONGODB_DEBUG === 'true',
      },
    });
  } catch (error: any) {
    return NextResponse.json({
      error: error.message,
      stack: process.env.NODE_ENV === 'development' ? error.stack : undefined,
    }, { status: 500 });
  }
}

