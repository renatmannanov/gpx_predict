import { useState, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { uploadGPX } from '../../api/gpx'

interface Props {
  onUploaded: (gpxId: string) => void
}

export default function GPXUpload({ onUploaded }: Props) {
  const [dragActive, setDragActive] = useState(false)

  const uploadMutation = useMutation({
    mutationFn: uploadGPX,
    onSuccess: (data) => {
      onUploaded(data.gpx_id)
    },
  })

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files?.[0]) {
      uploadMutation.mutate(e.dataTransfer.files[0])
    }
  }, [uploadMutation])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      uploadMutation.mutate(e.target.files[0])
    }
  }

  return (
    <div className="space-y-4">
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition ${
          dragActive
            ? 'border-primary-500 bg-primary-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".gpx"
          onChange={handleChange}
          className="hidden"
          id="gpx-input"
        />

        <label
          htmlFor="gpx-input"
          className="cursor-pointer"
        >
          <div className="text-4xl mb-2">📍</div>
          <p className="text-gray-600">
            Drop your GPX file here or{' '}
            <span className="text-primary-600 underline">browse</span>
          </p>
          <p className="text-sm text-gray-400 mt-1">
            Max file size: 20MB
          </p>
        </label>
      </div>

      {uploadMutation.isPending && (
        <div className="text-center text-gray-500">
          Uploading...
        </div>
      )}

      {uploadMutation.isError && (
        <div className="bg-red-50 text-red-600 p-3 rounded-lg">
          {uploadMutation.error instanceof Error
            ? uploadMutation.error.message
            : 'Upload failed'}
        </div>
      )}
    </div>
  )
}
