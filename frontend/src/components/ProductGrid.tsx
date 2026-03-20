
import ProductCard from './ProductCard'
import type { ProductResult } from '../types'

interface Props {
  results: ProductResult[]
  loading: boolean
  queryTimeMs: number | null
}

function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skeleton skeleton-img" />
      <div className="skeleton-body">
        <div className="skeleton skeleton-title" />
        <div className="skeleton skeleton-text" />
        <div className="skeleton skeleton-text skeleton-text--short" />
        <div className="skeleton skeleton-price" />
      </div>
    </div>
  )
}

export default function ProductGrid({ results, loading, queryTimeMs }: Props) {
  if (loading) {
    return (
      <div className="product-grid">
        {Array.from({ length: 8 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  if (!loading && results.length === 0 && queryTimeMs !== null) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
            <path d="M8 11h6M11 8v6" />
          </svg>
        </div>
        <p className="empty-title">No se encontraron productos</p>
        <p className="empty-sub">Intentá con otros términos o una imagen diferente</p>
      </div>
    )
  }

  if (results.length === 0) return null

  return (
    <>
      {queryTimeMs !== null && (
        <p className="query-meta">
          {results.length} resultado{results.length !== 1 ? 's' : ''} en{' '}
          <strong>{queryTimeMs.toFixed(0)} ms</strong>
        </p>
      )}
      <div className="product-grid">
        {results.map((p) => (
          <ProductCard key={p.id} product={p} />
        ))}
      </div>
    </>
  )
}
