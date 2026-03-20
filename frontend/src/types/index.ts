export interface ProductResult {
  id: string
  name: string
  description: string
  category: string
  price: number
  image_url: string
  similarity_score: number
}

export interface SearchResponse {
  results: ProductResult[]
  query_time_ms: number
  total_found: number
}

export interface SearchOptions {
  category?: string
  max_price?: number
}

export type SearchMode = 'text' | 'image' | 'multimodal' | null
