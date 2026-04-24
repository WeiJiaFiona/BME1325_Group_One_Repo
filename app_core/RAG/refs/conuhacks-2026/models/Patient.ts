import mongoose, { Schema, Document } from 'mongoose';

export interface PatientContactInfo {
  email?: string;
  phone?: string;
  emergencyContact?: {
    name: string;
    phone: string;
    relationship: string;
  };
}

export interface PatientDemographics {
  name?: string;
  dateOfBirth?: string;
  age?: number; // Calculated field
  sex?: string;
  healthCardNumber?: string;
  versionCode?: string;
  expiryDate?: string;
}

export interface PatientMedicalHistory {
  conditions: string[];
  medications: string[];
  allergies: string[];
  lastUpdated: Date;
}

export interface PatientVisit {
  caseId: mongoose.Types.ObjectId;
  visitDate: Date;
  chiefComplaint?: string;
  triageLevel?: string;
  hospitalId?: string;
  hospitalName?: string;
  outcome?: string;
}

export interface PatientDocument extends Document {
  // Unique identifiers
  healthCardNumber: string; // Primary identifier
  anonymousIds: string[]; // Track all anonymous sessions linked to this patient
  
  // Demographics
  demographics: PatientDemographics;
  
  // Contact Information
  contactInfo?: PatientContactInfo;
  
  // Medical History (aggregated across all visits)
  medicalHistory: PatientMedicalHistory;
  
  // Visit History
  visits: PatientVisit[];
  
  // Metadata
  firstVisit: Date;
  lastVisit: Date;
  totalVisits: number;
  
  // Consent and Privacy
  consentGiven: boolean;
  consentDate?: Date;
  dataRetentionExpiry?: Date; // For GDPR/privacy compliance
  
  // Flags
  isActive: boolean;
  notes?: string; // For internal use
  
  createdAt: Date;
  updatedAt: Date;
}

const PatientContactInfoSchema = new Schema<PatientContactInfo>({
  email: { type: String, lowercase: true, trim: true },
  phone: { type: String, trim: true },
  emergencyContact: {
    name: { type: String },
    phone: { type: String },
    relationship: { type: String },
  },
});

const PatientDemographicsSchema = new Schema<PatientDemographics>({
  name: { type: String, trim: true },
  dateOfBirth: { type: String },
  age: { type: Number },
  sex: { type: String },
  healthCardNumber: { type: String, trim: true, uppercase: true },
  versionCode: { type: String, trim: true },
  expiryDate: { type: String },
});

const PatientMedicalHistorySchema = new Schema<PatientMedicalHistory>({
  conditions: { type: [String], default: [] },
  medications: { type: [String], default: [] },
  allergies: { type: [String], default: [] },
  lastUpdated: { type: Date, default: Date.now },
});

const PatientVisitSchema = new Schema<PatientVisit>({
  caseId: { type: Schema.Types.ObjectId, ref: 'Case', required: true },
  visitDate: { type: Date, required: true },
  chiefComplaint: { type: String },
  triageLevel: { type: String },
  hospitalId: { type: String },
  hospitalName: { type: String },
  outcome: { type: String },
});

const PatientSchema = new Schema<PatientDocument>(
  {
    healthCardNumber: {
      type: String,
      required: true,
      unique: true,
      trim: true,
      uppercase: true,
      index: true,
    },
    anonymousIds: {
      type: [String],
      default: [],
      index: true,
    },
    demographics: {
      type: PatientDemographicsSchema,
      required: true,
    },
    contactInfo: {
      type: PatientContactInfoSchema,
    },
    medicalHistory: {
      type: PatientMedicalHistorySchema,
      default: () => ({
        conditions: [],
        medications: [],
        allergies: [],
        lastUpdated: new Date(),
      }),
    },
    visits: {
      type: [PatientVisitSchema],
      default: [],
    },
    firstVisit: {
      type: Date,
      default: Date.now,
    },
    lastVisit: {
      type: Date,
      default: Date.now,
    },
    totalVisits: {
      type: Number,
      default: 0,
    },
    consentGiven: {
      type: Boolean,
      default: false,
    },
    consentDate: {
      type: Date,
    },
    dataRetentionExpiry: {
      type: Date,
    },
    isActive: {
      type: Boolean,
      default: true,
    },
    notes: {
      type: String,
    },
  },
  {
    timestamps: true,
  }
);

// Indexes for efficient querying
PatientSchema.index({ healthCardNumber: 1 });
PatientSchema.index({ 'demographics.name': 1 });
PatientSchema.index({ 'demographics.dateOfBirth': 1 });
PatientSchema.index({ anonymousIds: 1 });
PatientSchema.index({ lastVisit: -1 });

// Virtual to calculate age from date of birth
PatientSchema.pre('save', function(next) {
  if (this.demographics.dateOfBirth) {
    try {
      const dob = new Date(this.demographics.dateOfBirth);
      const today = new Date();
      let age = today.getFullYear() - dob.getFullYear();
      const monthDiff = today.getMonth() - dob.getMonth();
      
      if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
        age--;
      }
      
      this.demographics.age = age;
    } catch (err) {
      console.error('Error calculating age:', err);
    }
  }
  next();
});

export default mongoose.models.Patient || mongoose.model<PatientDocument>('Patient', PatientSchema);

