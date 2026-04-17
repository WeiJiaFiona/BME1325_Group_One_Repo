/**
 * Pre-populated list of hospitals in the downtown area
 * Used for routing patients to appropriate facilities
 */

export interface Hospital {
  id: string;
  name: string;
  address: string;
  phone?: string;
  specialties?: string[];
  distance?: string; // Distance from downtown
}

export const DOWNTOWN_HOSPITALS: Hospital[] = [
  {
    id: 'general-downtown',
    name: 'General Hospital Downtown',
    address: '123 Main Street, Downtown, City',
    phone: '(555) 123-4567',
    specialties: ['Emergency', 'General Medicine', 'Surgery'],
    distance: '0.5 miles',
  },
  {
    id: 'emergency-center',
    name: 'Downtown Emergency Medical Center',
    address: '456 Emergency Way, Downtown, City',
    phone: '(555) 234-5678',
    specialties: ['Emergency', 'Trauma', 'Critical Care'],
    distance: '0.8 miles',
  },
  {
    id: 'city-medical',
    name: 'City Medical Center',
    address: '789 Health Boulevard, Downtown, City',
    phone: '(555) 345-6789',
    specialties: ['Emergency', 'Cardiology', 'Neurology'],
    distance: '1.2 miles',
  },
  {
    id: 'metro-hospital',
    name: 'Metro General Hospital',
    address: '321 Metro Avenue, Downtown, City',
    phone: '(555) 456-7890',
    specialties: ['Emergency', 'Pediatrics', 'Maternity'],
    distance: '1.5 miles',
  },
  {
    id: 'university-medical',
    name: 'University Medical Center',
    address: '654 University Drive, Downtown, City',
    phone: '(555) 567-8901',
    specialties: ['Emergency', 'Teaching Hospital', 'Research'],
    distance: '2.0 miles',
  },
  {
    id: 'community-health',
    name: 'Community Health Hospital',
    address: '987 Community Street, Downtown, City',
    phone: '(555) 678-9012',
    specialties: ['Emergency', 'Family Medicine', 'Urgent Care'],
    distance: '2.3 miles',
  },
];

export function getHospitalById(id: string): Hospital | undefined {
  return DOWNTOWN_HOSPITALS.find(h => h.id === id);
}

export function getHospitalByName(name: string): Hospital | undefined {
  return DOWNTOWN_HOSPITALS.find(h => h.name === name);
}

