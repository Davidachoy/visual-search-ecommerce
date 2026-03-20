import { useState } from 'react'
import type { ProductResult } from '../types'

interface Props {
  product: ProductResult
}

const FALLBACK =
  'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgZmlsbD0iIzFhMjAzMCIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSI0OCIgZmlsbD0iIzJhMzU1MCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSI+8J+RqDwvdGV4dD48L3N2Zz4='

function scoreLabel(score: number) {
  if (score >= 0.9) return 'Exact'
  if (score >= 0.75) return 'Very similar'
  if (score >= 0.6) return 'Similar'
  return 'Related'
}

function scoreColor(score: number) {
  if (score >= 0.9) return '#00ffc8'
  if (score >= 0.75) return '#4da6ff'
  if (score >= 0.6) return '#a78bfa'
  return '#94a3b8'
}

export default function ProductCard({ product }: Props) {
  const [imgSrc, setImgSrc] = useState(product.image_url || FALLBACK)

  return (
    <article className="product-card">
      <div className="card-image-wrap">
        <img
          src={imgSrc}
          alt={product.name}
          className="card-image"
          onError={() => setImgSrc(FALLBACK)}
          loading="lazy"
        />
        <div
          className="card-score"
          style={{ '--score-color': scoreColor(product.similarity_score) } as React.CSSProperties}
        >
          {scoreLabel(product.similarity_score)}
        </div>
        <div className="card-category">{product.category}</div>
      </div>
      <div className="card-body">
        <h3 className="card-name">{product.name}</h3>
        <p className="card-description">{product.description}</p>
        <div className="card-footer">
          <span className="card-price">
            ${product.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
          <span
            className="card-score-pct"
            style={{ color: scoreColor(product.similarity_score) }}
          >
            {Math.round(product.similarity_score * 100)}%
          </span>
        </div>
      </div>
    </article>
  )
}
