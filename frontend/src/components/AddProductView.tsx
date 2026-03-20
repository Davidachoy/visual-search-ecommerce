import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { addProduct } from '../api/search'
import type { AddProductResult } from '../api/search'

interface Props {
  onBack: () => void
}

const CATEGORIES = ['footwear', 'outerwear', 'bags', 'dresses', 'tops', 'bottoms', 'accessories']

function ImageUploadArea({
  preview,
  onSelect,
  onClear,
}: {
  preview: string | null
  onSelect: (file: File) => void
  onClear: () => void
}) {
  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) onSelect(accepted[0])
  }, [onSelect])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [] },
    maxFiles: 1,
    disabled: !!preview,
  })

  if (preview) {
    return (
      <div className="upload-preview-wrap">
        <img src={preview} alt="Preview" className="upload-preview-img" />
        <button className="upload-clear" onClick={onClear} type="button">
          ✕ Remove image
        </button>
      </div>
    )
  }

  return (
    <div {...getRootProps()} className={`upload-dropzone${isDragActive ? ' upload-dropzone--active' : ''}`}>
      <input {...getInputProps()} />
      <div className="upload-drop-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
      </div>
      <p className="upload-drop-text">
        {isDragActive ? 'Drop the image here' : 'Drag an image or click to select'}
      </p>
      <p className="upload-drop-sub">PNG, JPG, WEBP — opcional</p>
    </div>
  )
}

export default function AddProductView({ onBack }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('')
  const [price, setPrice] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<AddProductResult | null>(null)

  const handleImageSelect = (file: File) => {
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
  }

  const handleImageClear = () => {
    if (imagePreview) URL.revokeObjectURL(imagePreview)
    setImageFile(null)
    setImagePreview(null)
  }

  const handleReset = () => {
    setName('')
    setDescription('')
    setCategory('')
    setPrice('')
    setImageUrl('')
    handleImageClear()
    setError(null)
    setSuccess(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !description || !category || !price) return

    setLoading(true)
    setError(null)

    try {
      const result = await addProduct({
        name: name.trim(),
        description: description.trim(),
        category,
        price: parseFloat(price),
        image_url: imageUrl.trim(),
        image: imageFile ?? undefined,
      })
      setSuccess(result)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to add product'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const canSubmit = name.trim() && description.trim() && category && parseFloat(price) > 0 && !loading

  return (
    <div className="add-product-view">
      <div className="add-product-header">
        <button className="back-btn" onClick={onBack} type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m15 18-6-6 6-6" />
          </svg>
          Back to search
        </button>
        <div>
          <h2 className="add-product-title">Add product</h2>
          <p className="add-product-sub">The product will be indexed with Gemini embeddings</p>
        </div>
      </div>

      {success ? (
        <div className="add-success">
          <div className="success-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <h3 className="success-title">Product indexed</h3>
          <div className="success-details">
            <span className="success-id">{success.id}</span>
            <span className="success-name">{success.name}</span>
            <span className="success-cat">{success.category}</span>
            <span className="success-price">${success.price.toFixed(2)}</span>
          </div>
          <div className="success-actions">
            <button className="btn-add-another" onClick={handleReset}>
              Add another
            </button>
            <button className="btn-go-search" onClick={onBack}>
              Go to search
            </button>
          </div>
        </div>
      ) : (
        <form className="add-product-form" onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-left">
              <div className="field">
                <label className="field-label">Name *</label>
                <input
                  className="field-input"
                  type="text"
                  placeholder="E.g. Classic white sneakers"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={200}
                  disabled={loading}
                />
              </div>

              <div className="field">
                <label className="field-label">Description *</label>
                <textarea
                  className="field-input field-textarea"
                  placeholder="Detailed product description..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  maxLength={2000}
                  rows={4}
                  disabled={loading}
                />
              </div>

              <div className="field-row">
                <div className="field">
                  <label className="field-label">Category *</label>
                  <select
                    className="field-input field-select"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    disabled={loading}
                  >
                    <option value="">Select a category</option>
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c.charAt(0).toUpperCase() + c.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label className="field-label">Price (USD) *</label>
                  <input
                    className="field-input"
                    type="number"
                    placeholder="0.00"
                    min="0.01"
                    step="0.01"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="field">
                <label className="field-label">Image URL (optional)</label>
                <input
                  className="field-input"
                  type="url"
                  placeholder="https://..."
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  disabled={loading || !!imageFile}
                />
                {imageFile && (
                  <p className="field-hint">Uploaded image will be used</p>
                )}
              </div>
            </div>

            <div className="form-right">
              <label className="field-label">Product image</label>
              <p className="field-hint field-hint--top">
                Uploading an image improves embedding quality (multimodal)
              </p>
              <ImageUploadArea
                preview={imagePreview}
                onSelect={handleImageSelect}
                onClear={handleImageClear}
              />
            </div>
          </div>

          {error && (
            <div className="error-banner">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
              {error}
            </div>
          )}

          <div className="form-actions">
            <button type="submit" className="btn-submit" disabled={!canSubmit}>
              {loading ? (
                <>
                  <span className="btn-spinner" />
                  Indexing...
                </>
              ) : (
                <>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="btn-icon">
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                  Add product
                </>
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
