import axios from 'axios'
import type { SearchResponse, SearchOptions } from '../types'

const client = axios.create({ baseURL: '/api' })

export async function searchByText(
  query: string,
  options?: SearchOptions
): Promise<SearchResponse> {
  const { data } = await client.post<SearchResponse>('/search/text', {
    query,
    ...(options?.category && { category: options.category }),
    ...(options?.max_price != null && { max_price: options.max_price }),
  })
  return data
}

export async function searchByImage(
  file: File,
  options?: SearchOptions
): Promise<SearchResponse> {
  const form = new FormData()
  form.append('file', file)
  if (options?.category) form.append('category', options.category)
  if (options?.max_price != null)
    form.append('max_price', String(options.max_price))

  const { data } = await client.post<SearchResponse>('/search/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function searchMultimodal(
  query: string,
  file: File,
  options?: SearchOptions
): Promise<SearchResponse> {
  const form = new FormData()
  form.append('query', query)
  form.append('file', file)
  if (options?.category) form.append('category', options.category)
  if (options?.max_price != null)
    form.append('max_price', String(options.max_price))

  const { data } = await client.post<SearchResponse>(
    '/search/multimodal',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return data
}

export async function fetchCategories(): Promise<string[]> {
  const { data } = await client.get<{ categories: string[] }>('/categories')
  return data.categories
}

export interface AddProductPayload {
  name: string
  description: string
  category: string
  price: number
  image_url?: string
  image?: File
}

export interface AddProductResult {
  id: string
  name: string
  category: string
  price: number
  image_url: string
}

export async function addProduct(payload: AddProductPayload): Promise<AddProductResult> {
  const form = new FormData()
  form.append('name', payload.name)
  form.append('description', payload.description)
  form.append('category', payload.category)
  form.append('price', String(payload.price))
  form.append('image_url', payload.image_url ?? '')
  if (payload.image) form.append('image', payload.image)

  const { data } = await client.post<AddProductResult>('/products', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
