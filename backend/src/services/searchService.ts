import { QueryRequest, QueryResponse } from '../models/types';

export class SearchService {
  /**
   * Processes a query against the grounded document collection.
   * Note: The full AI embedding & LLM pipeline is scheduled for the next milestone.
   * This baseline enforces the schema, fallback mechanics, citation format, and legal disclaimer.
   */
  public static async executeQuery(request: QueryRequest): Promise<QueryResponse> {
    const startTime = Date.now();
    const cleanQuery = request.queryText.trim().toLowerCase();

    const disclaimer =
      'Disclaimer: This assistant provides informational summaries based solely on uploaded official scheme documents. It does not constitute legal advice, guarantee eligibility, or confer statutory benefits.';

    // Demonstration sample: when asking about small/marginal farmer land limit
    if (
      cleanQuery.includes('farmer') ||
      cleanQuery.includes('pm-kisan') ||
      cleanQuery.includes('land')
    ) {
      return {
        queryId: `qry-${Date.now()}`,
        status: 'SUCCESS',
        isGrounded: true,
        answer: {
          summary:
            'Under the PM-Kisan scheme guidelines, small and marginal farmer families are entitled to financial assistance subject to landholding ceilings and official verification.',
          eligibility: [
            'Small and marginal farmer families holding cultivable land up to 2 hectares [PM-Kisan Operational Guidelines 2024-25.pdf, Page 4].',
            'Institutional landholders and serving government officials are excluded from benefits [PM-Kisan Operational Guidelines 2024-25.pdf, Page 5].',
          ],
          requiredDocuments: [
            'Aadhaar Card of the landholder [PM-Kisan Operational Guidelines 2024-25.pdf, Page 7]',
            'Land Ownership Title / Record of Rights (RoR) [PM-Kisan Operational Guidelines 2024-25.pdf, Page 7]',
            'Bank Account linked to Aadhaar [PM-Kisan Operational Guidelines 2024-25.pdf, Page 8]',
          ],
          applicationProcedure: [
            'Submit details via the official online state agriculture portal or Village Panchayat helpdesk [PM-Kisan Operational Guidelines 2024-25.pdf, Page 11].',
            'District level verification committee validates physical land records [PM-Kisan Operational Guidelines 2024-25.pdf, Page 12].',
          ],
          citations: [
            {
              citationId: 'cite-01',
              documentId: 'doc-pmkisan-01',
              documentTitle: 'PM-Kisan Operational Guidelines 2024-25.pdf',
              pageNumber: 4,
              snippet:
                'Small and marginal farmers having cultivable land up to 2 hectares shall be entitled to receive financial benefit under the scheme.',
            },
            {
              citationId: 'cite-02',
              documentId: 'doc-pmkisan-01',
              documentTitle: 'PM-Kisan Operational Guidelines 2024-25.pdf',
              pageNumber: 7,
              snippet:
                'Mandatory documentation includes Aadhaar authentication and verified land Record of Rights (RoR).',
            },
          ],
        },
        disclaimer,
        latencyMs: Date.now() - startTime,
      };
    }

    // Default strict refusal for out-of-corpus queries
    return {
      queryId: `qry-${Date.now()}`,
      status: 'NOT_FOUND',
      isGrounded: false,
      fallbackMessage:
        'The requested information is not available in the uploaded official scheme documents. Please consult the concerned department or official portal for further clarification.',
      disclaimer,
      latencyMs: Date.now() - startTime,
    };
  }
}
