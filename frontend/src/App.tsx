import { useState, useEffect, useCallback } from 'react'
import SearchBar from './components/SearchBar'
import ImageDropzone from './components/ImageDropzone'
import ProductGrid from './components/ProductGrid'
import AddProductView from './components/AddProductView'
import {
  searchByText,
  searchByImage,
  searchMultimodal,
  fetchCategories,
} from './api/search'
import type { ProductResult, SearchMode } from './types'
import './App.css'

type View = 'search' | 'add'

const MODE_LABELS: Record<NonNullable<SearchMode>, string> = {
  text: 'Text search',
  image: 'Image search',
  multimodal: 'Multimodal search',
}

const MODE_COLORS: Record<NonNullable<SearchMode>, string> = {
  text: 'badge--text',
  image: 'badge--image',
  multimodal: 'badge--multimodal',
}

export default function App() {
  const [view, setView] = useState<View>('search')
  const [query, setQuery] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [results, setResults] = useState<ProductResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [queryTimeMs, setQueryTimeMs] = useState<number | null>(null)
  const [searchMode, setSearchMode] = useState<SearchMode>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [maxPrice, setMaxPrice] = useState<number>(500)
  const [categories, setCategories] = useState<string[]>([])

  useEffect(() => {
    fetchCategories()
      .then(setCategories)
      .catch(() => {})
  }, [])

  const handleImageSelect = useCallback((file: File) => {
    setImageFile(file)
    const url = URL.createObjectURL(file)
    setImagePreview(url)
  }, [])

  const handleClearImage = useCallback(() => {
    if (imagePreview) URL.revokeObjectURL(imagePreview)
    setImageFile(null)
    setImagePreview(null)
  }, [imagePreview])

  const handleSearch = async () => {
    const trimmed = query.trim()
    if (!trimmed && !imageFile) return

    setLoading(true)
    setError(null)
    setResults([])
    setQueryTimeMs(null)

    const opts = {
      category: selectedCategory ?? undefined,
      max_price: filtersOpen && maxPrice < 500 ? maxPrice : undefined,
    }

    try {
      let response
      if (trimmed && imageFile) {
        setSearchMode('multimodal')
        response = await searchMultimodal(trimmed, imageFile, opts)
      } else if (imageFile) {
        setSearchMode('image')
        response = await searchByImage(imageFile, opts)
      } else {
        setSearchMode('text')
        response = await searchByText(trimmed, opts)
      }
      setResults(response.results)
      setQueryTimeMs(response.query_time_ms)
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to connect to the server'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const canSearch = !loading && (query.trim().length > 0 || imageFile !== null)

  return (
    <div className="app">
      <div className="bg-grid" aria-hidden="true" />
      <div className="bg-glow bg-glow--1" aria-hidden="true" />
      <div className="bg-glow bg-glow--2" aria-hidden="true" />

      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-mark">VS</span>
            <div>
              <h1 className="logo-title">Visual Search</h1>
              <p className="logo-sub">Find what you're looking for with text or image</p>
            </div>
          </div>
          <nav className="header-nav">
            <button
              className={`nav-btn${view === 'search' ? ' nav-btn--active' : ''}`}
              onClick={() => setView('search')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
              </svg>
              Search
            </button>
            <button
              className={`nav-btn${view === 'add' ? ' nav-btn--active' : ''}`}
              onClick={() => setView('add')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 5v14M5 12h14" />
              </svg>
              Add product
            </button>
          </nav>
        </div>
      </header>

      <main className="main">
        {view === 'add' && <AddProductView onBack={() => setView('search')} />}

        {view === 'search' && (
        <section className="search-section">
          <div className="search-panel">
            <div className="search-inputs">
              <div className="search-text-area">
                <SearchBar
                  value={query}
                  onChange={setQuery}
                  onSubmit={handleSearch}
                  loading={loading}
                />
              </div>
              <div className="search-image-area">
                <ImageDropzone
                  onImageSelect={handleImageSelect}
                  preview={imagePreview}
                  onClear={handleClearImage}
                />
              </div>
            </div>

            <div className="search-actions">
              <button
                className="btn-search"
                onClick={handleSearch}
                disabled={!canSearch}
              >
                {loading ? (
                  <span className="btn-spinner" />
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="btn-icon">
                    <circle cx="11" cy="11" r="8" />
                    <path d="m21 21-4.35-4.35" />
                  </svg>
                )}
                {loading ? 'Searching...' : 'Search'}
              </button>

              <button
                className={`btn-filters${filtersOpen ? ' btn-filters--active' : ''}`}
                onClick={() => setFiltersOpen((o) => !o)}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" />
                </svg>
                Filters
                {filtersOpen && <span className="filter-dot" />}
              </button>
            </div>

            {filtersOpen && (
              <div className="filters-panel">
                <div className="filter-group">
                  <label className="filter-label">Category</label>
                  <select
                    className="filter-select"
                    value={selectedCategory ?? ''}
                    onChange={(e) => setSelectedCategory(e.target.value || null)}
                  >
                    <option value="">All categories</option>
                    {categories.map((c) => (
                      <option key={c} value={c}>
                        {c.charAt(0).toUpperCase() + c.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="filter-group">
                  <label className="filter-label">
                    Max price:{' '}
                    <strong className="filter-value">
                      ${maxPrice === 500 ? '500+' : maxPrice}
                    </strong>
                  </label>
                  <input
                    type="range"
                    className="filter-range"
                    min={0}
                    max={500}
                    step={10}
                    value={maxPrice}
                    onChange={(e) => setMaxPrice(Number(e.target.value))}
                  />
                  <div className="range-labels">
                    <span>$0</span>
                    <span>$500+</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
        )}

        {view === 'search' && (
        <section className="results-section">
          {error && (
            <div className="error-banner">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
              {error}
            </div>
          )}

          {(results.length > 0 || (queryTimeMs !== null && !loading)) && searchMode && (
            <div className="results-header">
              <span className={`mode-badge ${MODE_COLORS[searchMode]}`}>
                {MODE_LABELS[searchMode]}
              </span>
            </div>
          )}

          <ProductGrid
            results={results}
            loading={loading}
            queryTimeMs={queryTimeMs}
          />
        </section>
        )}
      </main>

      <footer className="footer">
        <p>Powered by Google Gemini · Qdrant</p>
      </footer>
    </div>
  )
}
