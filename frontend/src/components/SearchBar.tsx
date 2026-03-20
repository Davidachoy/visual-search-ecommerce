interface Props {
  value: string
  onChange: (query: string) => void
  onSubmit: () => void
  loading: boolean
}

export default function SearchBar({ value, onChange, onSubmit, loading }: Props) {
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
          placeholder="Describe what you're looking for..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSubmit()}
          disabled={loading}
        />
        {value && (
          <button
            className="clear-btn"
            onClick={() => onChange('')}
            aria-label="Clear"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  )
}
