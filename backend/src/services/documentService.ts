import { Collection, Document } from '../models/types';

// In-memory catalog seed for demonstration and initial system structure
const mockCollections: Collection[] = [
  {
    id: 'col-agr-01',
    name: 'Agriculture & Farmer Welfare',
    department: 'Department of Agriculture & Farmers Welfare',
    description:
      'Guidelines and circulars for farmer subsidies, crop insurance, and equipment aid.',
    isPublic: true,
    documentCount: 3,
    createdAt: new Date('2024-01-15'),
  },
  {
    id: 'col-soc-02',
    name: 'Social Justice & Senior Citizen Pensions',
    department: 'Ministry of Social Justice & Empowerment',
    description:
      'Eligibility criteria and documentation for disability and old-age pension schemes.',
    isPublic: true,
    documentCount: 2,
    createdAt: new Date('2024-02-10'),
  },
  {
    id: 'col-edu-03',
    name: 'Higher Education Scholarships',
    department: 'Department of Higher Education',
    description:
      'Post-matric and merit scholarship schemes for minority and underprivileged students.',
    isPublic: true,
    documentCount: 4,
    createdAt: new Date('2024-03-01'),
  },
];

const mockDocuments: Document[] = [
  {
    id: 'doc-pmkisan-01',
    collectionId: 'col-agr-01',
    title: 'PM-Kisan Operational Guidelines 2024-25.pdf',
    department: 'Department of Agriculture & Farmers Welfare',
    notificationNumber: 'AGR-NOTIF-2024/09',
    currentVersion: '1.2',
    status: 'ACTIVE',
    createdAt: new Date('2024-01-20'),
  },
  {
    id: 'doc-pension-02',
    collectionId: 'col-soc-02',
    title: 'National Social Assistance Programme Guidelines.pdf',
    department: 'Ministry of Social Justice & Empowerment',
    notificationNumber: 'MSJE-NSAP-2023/14',
    currentVersion: '2.0',
    status: 'ACTIVE',
    createdAt: new Date('2024-02-15'),
  },
];

export class DocumentService {
  public static async getCollections(): Promise<Collection[]> {
    return mockCollections;
  }

  public static async getCollectionById(id: string): Promise<Collection | null> {
    return mockCollections.find(c => c.id === id) || null;
  }

  public static async getDocuments(collectionId?: string): Promise<Document[]> {
    if (collectionId) {
      return mockDocuments.filter(d => d.collectionId === collectionId);
    }
    return mockDocuments;
  }
}
