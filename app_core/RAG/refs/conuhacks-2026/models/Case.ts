import mongoose, { Schema, Document } from 'mongoose';

export interface QuestionAsked {
  id: string;
  question: string;
  answer: string | null;
  timestamp: Date;
}

export interface HealthCardScan {
  scanned: boolean;
  ageSet: boolean;
  dateOfBirth?: string;
  name?: string;
  sex?: string;
  healthCardNumber?: string;
  versionCode?: string;
  expiryDate?: string;
  confidence?: 'high' | 'medium' | 'low';
  scannedAt?: Date;
  fieldsExtracted?: {
    name: boolean;
    dateOfBirth: boolean;
    sex: boolean;
    expiryDate: boolean;
    healthCardNumber: boolean;
    versionCode: boolean;
  };
}

export interface UserInfo {
  anonymousId: string;
  patientId?: string; // Link to Patient document
  age?: number;
  pregnant?: boolean | 'unknown';
  phone?: string; // Patient phone number
  healthCardScan?: HealthCardScan;
}

export interface RedFlags {
  any: boolean | 'unknown';
  details: string[];
}

export interface History {
  conditions: string[];
  meds: string[];
  allergies: string[];
}

export interface Vitals {
  tempC?: number | 'unknown';
  hr?: number | 'unknown';
  spo2?: number | 'unknown';
}

export interface Intake {
  chiefComplaint?: string;
  symptoms: string[];
  severity?: number | 'unknown';
  onset?: string;
  pattern?: string;
  redFlags: RedFlags;
  history: History;
  vitals: Vitals;
  uploadedImages?: string[]; // Base64 encoded images or URLs
  additionalComments?: string; // Patient's additional notes/comments
}

export interface Assistant {
  triageLevel?: 'EMERGENCY' | 'URGENT' | 'NON_URGENT' | 'SELF_CARE' | 'UNCERTAIN';
  confidence?: number;
  reasons: string[];
  nextSteps: string[];
  monitoringPlan: string[];
  escalationTriggers: string[];
  questionsAsked: QuestionAsked[];
  intakeSummary?: string;
  disclaimerShown: boolean;
}

export interface AdminReview {
  reviewed: boolean;
  reviewedAt?: Date;
  reviewedBy?: string; // Admin/doctor identifier
  adminTriageLevel?: 'EMERGENCY' | 'URGENT' | 'NON_URGENT' | 'SELF_CARE' | 'UNCERTAIN';
  adminNotes?: string;
  onWatchList?: boolean;
  watchListReason?: string;
}

export interface HospitalRouting {
  hospitalId?: string;
  hospitalSlug?: string; // URL-friendly identifier for the hospital
  hospitalName?: string;
  hospitalAddress?: string;
  routedAt?: Date;
  routedBy?: string;
  patientConfirmedRoute?: boolean;
  patientConfirmedAt?: Date;
  estimatedArrival?: Date;
  checkedInAt?: Date;
  checkedInBy?: string;
}

export type WorkflowStatus = 'pending_review' | 'confirmed_hospital' | 'watching' | 'on_route' | 'checked_in' | 'discharged';

export interface HealthCheck {
  timestamp: Date;
  symptomsWorsened: boolean;
  newSymptoms: string[];
  painLevel?: number; // 1-10 scale
  notes?: string;
}

export interface PatientNotification {
  id: string;
  type: 'hospital_assigned' | 'status_update' | 'review_complete' | 'routing_update';
  message: string;
  timestamp: Date;
  read: boolean;
  metadata?: {
    hospitalName?: string;
    hospitalAddress?: string;
    workflowStatus?: WorkflowStatus;
    [key: string]: any;
  };
}

export interface CaseDocument extends Document {
  createdAt: Date;
  updatedAt: Date;
  status: 'in_progress' | 'completed' | 'escalated';
  workflowStatus?: WorkflowStatus;
  hospitalRouting?: HospitalRouting;
  assessmentType: 'in_hospital' | 'remote';
  location?: {
    latitude?: number;
    longitude?: number;
  };
  user: UserInfo;
  intake: Intake;
  assistant: Assistant;
  adminReview?: AdminReview;
  healthChecks?: HealthCheck[]; // Periodic check-ins while waiting
  notifications?: PatientNotification[]; // Patient notifications
}

const QuestionAskedSchema = new Schema<QuestionAsked>({
  id: { type: String, required: true },
  question: { type: String, required: true },
  answer: { type: Schema.Types.Mixed, default: null },
  timestamp: { type: Date, default: Date.now },
});

const HealthCardScanSchema = new Schema<HealthCardScan>({
  scanned: { type: Boolean, default: false },
  ageSet: { type: Boolean, default: false },
  dateOfBirth: { type: String },
  name: { type: String },
  sex: { type: String },
  healthCardNumber: { type: String },
  versionCode: { type: String },
  expiryDate: { type: String },
  confidence: { type: String, enum: ['high', 'medium', 'low'] },
  scannedAt: { type: Date },
  fieldsExtracted: {
    type: {
      name: { type: Boolean },
      dateOfBirth: { type: Boolean },
      sex: { type: Boolean },
      expiryDate: { type: Boolean },
      healthCardNumber: { type: Boolean },
      versionCode: { type: Boolean },
    }
  },
});

const UserInfoSchema = new Schema<UserInfo>({
  anonymousId: { type: String, required: true },
  patientId: { type: String, index: true }, // Reference to Patient document
  age: { type: Number },
  pregnant: { type: Schema.Types.Mixed },
  phone: { type: String, trim: true },
  healthCardScan: { type: HealthCardScanSchema },
});

const RedFlagsSchema = new Schema<RedFlags>({
  any: { type: Schema.Types.Mixed, default: 'unknown' },
  details: { type: [String], default: [] },
});

const HistorySchema = new Schema<History>({
  conditions: { type: [String], default: [] },
  meds: { type: [String], default: [] },
  allergies: { type: [String], default: [] },
});

const VitalsSchema = new Schema<Vitals>({
  tempC: { type: Schema.Types.Mixed },
  hr: { type: Schema.Types.Mixed },
  spo2: { type: Schema.Types.Mixed },
});

const IntakeSchema = new Schema<Intake>({
  chiefComplaint: String,
  symptoms: { type: [String], default: [] },
  severity: { type: Schema.Types.Mixed },
  onset: String,
  pattern: String,
  redFlags: { type: RedFlagsSchema, default: () => ({ any: 'unknown', details: [] }) },
  history: { type: HistorySchema, default: () => ({ conditions: [], meds: [], allergies: [] }) },
  vitals: { type: VitalsSchema, default: () => ({}) },
  uploadedImages: { type: [String], default: [] },
  additionalComments: String,
});

const AssistantSchema = new Schema<Assistant>({
  triageLevel: { type: String, enum: ['EMERGENCY', 'URGENT', 'NON_URGENT', 'SELF_CARE', 'UNCERTAIN'] },
  confidence: Number,
  reasons: { type: [String], default: [] },
  nextSteps: { type: [String], default: [] },
  monitoringPlan: { type: [String], default: [] },
  escalationTriggers: { type: [String], default: [] },
  questionsAsked: { type: [QuestionAskedSchema], default: [] },
  intakeSummary: String,
  disclaimerShown: { type: Boolean, default: false },
});

const AdminReviewSchema = new Schema<AdminReview>({
  reviewed: { type: Boolean, default: false },
  reviewedAt: Date,
  reviewedBy: String,
  adminTriageLevel: { type: String, enum: ['EMERGENCY', 'URGENT', 'NON_URGENT', 'SELF_CARE', 'UNCERTAIN'] },
  adminNotes: String,
  onWatchList: { type: Boolean, default: false },
  watchListReason: String,
});

const HospitalRoutingSchema = new Schema<HospitalRouting>({
  hospitalId: String,
  hospitalSlug: String, // URL-friendly identifier for the hospital
  hospitalName: String,
  hospitalAddress: String,
  routedAt: Date,
  routedBy: String,
  patientConfirmedRoute: { type: Boolean, default: false },
  patientConfirmedAt: Date,
  estimatedArrival: Date,
  checkedInAt: Date,
  checkedInBy: String,
});

const HealthCheckSchema = new Schema<HealthCheck>({
  timestamp: { type: Date, default: Date.now },
  symptomsWorsened: { type: Boolean, default: false },
  newSymptoms: { type: [String], default: [] },
  painLevel: { type: Number, min: 1, max: 10 },
  notes: String,
});

const PatientNotificationSchema = new Schema<PatientNotification>({
  id: { type: String, required: true },
  type: { 
    type: String, 
    enum: ['hospital_assigned', 'status_update', 'review_complete', 'routing_update'],
    required: true 
  },
  message: { type: String, required: true },
  timestamp: { type: Date, default: Date.now },
  read: { type: Boolean, default: false },
  metadata: { type: Schema.Types.Mixed },
});

const CaseSchema = new Schema<CaseDocument>(
  {
    status: {
      type: String,
      enum: ['in_progress', 'completed', 'escalated'],
      default: 'in_progress',
    },
    workflowStatus: {
      type: String,
      enum: ['pending_review', 'confirmed_hospital', 'watching', 'on_route', 'checked_in', 'discharged'],
      default: 'pending_review',
    },
    hospitalRouting: { type: HospitalRoutingSchema },
    assessmentType: {
      type: String,
      enum: ['in_hospital', 'remote'],
      default: 'remote',
    },
    location: {
      latitude: { type: Number },
      longitude: { type: Number },
    },
    user: { type: UserInfoSchema, required: true },
    intake: { type: IntakeSchema, default: () => ({ symptoms: [], redFlags: { any: 'unknown', details: [] }, history: { conditions: [], meds: [], allergies: [] }, vitals: {} }) },
    assistant: { type: AssistantSchema, default: () => ({ reasons: [], nextSteps: [], monitoringPlan: [], escalationTriggers: [], questionsAsked: [], disclaimerShown: false }) },
    adminReview: { type: AdminReviewSchema, default: () => ({ reviewed: false }) },
    healthChecks: { type: [HealthCheckSchema], default: [] },
    notifications: { type: [PatientNotificationSchema], default: [] },
  },
  {
    timestamps: true,
  }
);

export default mongoose.models.Case || mongoose.model<CaseDocument>('Case', CaseSchema);

