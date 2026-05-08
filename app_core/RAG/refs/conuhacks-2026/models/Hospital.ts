import mongoose, { Schema, Document } from 'mongoose';

export interface HospitalDocument extends Document {
  name: string;
  slug: string; // URL-friendly version of the hospital name
  address: string;
  city: string;
  phone?: string;
  specialties: string[];
  maxCapacity: number; // Maximum number of patients the hospital can handle
  currentPatients: number; // Current number of patients
  availableCapacity: number; // Calculated: maxCapacity - currentPatients

  currentWait: number; // Current wait time in minutes

  latitude?: number; // Hospital location latitude
  longitude?: number; // Hospital location longitude

  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

const HospitalSchema = new Schema<HospitalDocument>(
  {
    name: { type: String, required: true },
    slug: { type: String, required: true, unique: true },
    address: { type: String, required: true },
    city: { type: String, required: true, default: 'Montreal' },
    phone: String,
    specialties: { type: [String], default: [] },
    maxCapacity: { type: Number, required: true, default: 100 },
    currentPatients: { type: Number, default: 0 },

    currentWait: { type: Number, default: 45 }, // Wait time in minutes, default to 45

    latitude: { type: Number },
    longitude: { type: Number },

    isActive: { type: Boolean, default: true },
  },
  {
    timestamps: true,
  }
);

// Virtual for available capacity
HospitalSchema.virtual('availableCapacity').get(function() {
  return Math.max(0, this.maxCapacity - this.currentPatients);
});

HospitalSchema.set('toJSON', { virtuals: true });

export default mongoose.models.Hospital || mongoose.model<HospitalDocument>('Hospital', HospitalSchema);

