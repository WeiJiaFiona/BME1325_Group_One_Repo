import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case, { PatientNotification } from '@/models/Case';
import { v4 as uuidv4 } from 'uuid';

/**
 * Get all notifications for a case
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    const notifications = caseDoc.notifications || [];
    
    // Sort by timestamp, newest first
    const sortedNotifications = [...notifications].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );

    return NextResponse.json({ 
      notifications: sortedNotifications,
      unreadCount: notifications.filter((n: PatientNotification) => !n.read).length
    });
  } catch (error: any) {
    console.error('Error fetching notifications:', error);
    return NextResponse.json({ error: error.message || 'Failed to fetch notifications' }, { status: 500 });
  }
}

/**
 * Mark notifications as read
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const body = await request.json();
    const { notificationIds, markAllRead } = body;

    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    if (!caseDoc.notifications) {
      caseDoc.notifications = [];
    }

    if (markAllRead) {
      // Mark all as read
      caseDoc.notifications.forEach((notification: PatientNotification) => {
        notification.read = true;
      });
    } else if (notificationIds && Array.isArray(notificationIds)) {
      // Mark specific notifications as read
      notificationIds.forEach((notificationId: string) => {
        const notification = caseDoc.notifications?.find((n: PatientNotification) => n.id === notificationId);
        if (notification) {
          notification.read = true;
        }
      });
    }

    await caseDoc.save();

    return NextResponse.json({ 
      success: true,
      unreadCount: caseDoc.notifications.filter((n: PatientNotification) => !n.read).length
    });
  } catch (error: any) {
    console.error('Error updating notifications:', error);
    return NextResponse.json({ error: error.message || 'Failed to update notifications' }, { status: 500 });
  }
}

/**
 * Helper function to create a notification (used by other endpoints)
 * Note: This is not exported as Next.js route handlers can only export HTTP methods
 * If needed elsewhere, move this to a separate utility file
 */
async function createNotification(
  caseId: string,
  type: 'hospital_assigned' | 'status_update' | 'review_complete' | 'routing_update',
  message: string,
  metadata?: any
) {
  try {
    await connectDB();
    const caseDoc = await Case.findById(caseId);
    
    if (!caseDoc) {
      return;
    }

    if (!caseDoc.notifications) {
      caseDoc.notifications = [];
    }

    const notification = {
      id: uuidv4(),
      type,
      message,
      timestamp: new Date(),
      read: false,
      metadata: metadata || {},
    };

    caseDoc.notifications.push(notification);
    await caseDoc.save();
  } catch (error) {
    console.error('Error creating notification:', error);
  }
}

