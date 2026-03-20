import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'

interface Props {
  onImageSelect: (file: File) => void
  preview: string | null
  onClear: () => void
}

export default function ImageDropzone({ onImageSelect, preview, onClear }: Props) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) onImageSelect(accepted[0])
    },
    [onImageSelect]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [] },
    maxFiles: 1,
    disabled: !!preview,
  })

  if (preview) {
    return (
      <div className="dropzone dropzone--preview">
        <img src={preview} alt="Vista previa" className="dropzone-preview-img" />
        <button
          className="dropzone-clear"
          onClick={(e) => {
            e.stopPropagation()
            onClear()
          }}
          aria-label="Quitar imagen"
        >
          ✕
        </button>
        <div className="dropzone-preview-label">Imagen cargada</div>
      </div>
    )
  }

  return (
    <div
      {...getRootProps()}
      className={`dropzone${isDragActive ? ' dropzone--active' : ''}`}
    >
      <input {...getInputProps()} />
      <div className="dropzone-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="3" y="3" width="18" height="18" rx="3" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <path d="m21 15-5-5L5 21" />
        </svg>
      </div>
      <p className="dropzone-text">
        {isDragActive ? 'Soltá la imagen acá' : 'Arrastrá una imagen'}
      </p>
      <p className="dropzone-subtext">o hacé click para seleccionar</p>
    </div>
  )
}
