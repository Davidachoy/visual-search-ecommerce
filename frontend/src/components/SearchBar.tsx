import { useState } from 'react'

interface Props {
  onSearch: (query: string) => void
  loading: boolean
}

export default function SearchBar({ onSearch, loading }: Props) {
  const [value, setValue] = useState('')

  const handleSubmit = () => {
    if (!loading) onSearch(value.trim())
  }

  return (
    <div className="search-bar">
      <div className="search-input-wrap">
        <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
        <input
          type="text"
          className="search-input"
          placeholder="Describí lo que buscás..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          disabled={loading}
        />
        {value && (
          <button
            className="clear-btn"
            onClick={() => setValue('')}
            aria-label="Limpiar"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  )
}
