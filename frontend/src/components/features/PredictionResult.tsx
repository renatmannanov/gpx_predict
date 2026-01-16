interface Warning {
  level: 'info' | 'warning' | 'danger'
  message: string
}

interface Prediction {
  estimated_time_hours: number
  safe_time_hours: number
  recommended_start: string
  warnings: Warning[]
  total_multiplier: number
}

interface Props {
  prediction: Prediction
  onReset: () => void
}

export default function PredictionResult({ prediction, onReset }: Props) {
  const formatTime = (hours: number) => {
    const h = Math.floor(hours)
    const m = Math.round((hours - h) * 60)
    return `${h}:${m.toString().padStart(2, '0')}`
  }

  return (
    <div className="space-y-6">
      {/* Main result */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="text-center">
          <div className="text-sm text-gray-500 mb-1">Estimated time</div>
          <div className="text-5xl font-bold text-gray-900">
            {formatTime(prediction.estimated_time_hours)}
          </div>
          <div className="text-gray-500 mt-1">hours</div>
        </div>

        <div className="mt-6 pt-6 border-t grid grid-cols-2 gap-4 text-center">
          <div>
            <div className="text-sm text-gray-500">Safe time (+20%)</div>
            <div className="text-xl font-semibold text-gray-700">
              {formatTime(prediction.safe_time_hours)}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Start by</div>
            <div className="text-xl font-semibold text-primary-600">
              {prediction.recommended_start}
            </div>
          </div>
        </div>
      </div>

      {/* Warnings */}
      {prediction.warnings.length > 0 && (
        <div className="space-y-2">
          {prediction.warnings.map((warning, i) => (
            <div
              key={i}
              className={`p-4 rounded-lg ${
                warning.level === 'danger'
                  ? 'bg-red-50 text-red-700'
                  : warning.level === 'warning'
                  ? 'bg-yellow-50 text-yellow-700'
                  : 'bg-blue-50 text-blue-700'
              }`}
            >
              <span className="mr-2">
                {warning.level === 'danger' ? '⚠️' : warning.level === 'warning' ? '⚡' : 'ℹ️'}
              </span>
              {warning.message}
            </div>
          ))}
        </div>
      )}

      {/* Multiplier info */}
      <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
        <div className="font-medium text-gray-700 mb-1">How we calculated this</div>
        <p>
          Base Naismith time adjusted by {prediction.total_multiplier}x
          based on your experience, backpack, and group size.
        </p>
      </div>

      {/* Actions */}
      <div className="flex gap-4">
        <button
          onClick={onReset}
          className="flex-1 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
        >
          New Prediction
        </button>
        <button
          onClick={() => {
            // TODO: Share functionality
            alert('Share feature coming soon!')
          }}
          className="flex-1 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          Share
        </button>
      </div>
    </div>
  )
}
