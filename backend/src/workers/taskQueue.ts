export interface IngestionJobPayload {
  versionId: string;
  documentId: string;
  storagePath: string;
  collectionId: string;
}

export interface TaskJob<T> {
  id: string;
  type: 'DOCUMENT_INGESTION' | 'VECTOR_INDEXING' | 'OCR_EXTRACTION';
  payload: T;
  retryCount: number;
  maxRetries: number;
  createdAt: Date;
}

export class TaskQueue {
  private static queue: TaskJob<unknown>[] = [];

  public static async enqueue<T>(
    type: TaskJob<T>['type'],
    payload: T,
    maxRetries = 3
  ): Promise<string> {
    const jobId = `job-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const job: TaskJob<T> = {
      id: jobId,
      type,
      payload,
      retryCount: 0,
      maxRetries,
      createdAt: new Date(),
    };

    this.queue.push(job as TaskJob<unknown>);
    return jobId;
  }

  public static async getQueueLength(): Promise<number> {
    return this.queue.length;
  }
}
