import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { predictHike } from '../../api/predict'

interface Props {
  gpxId: string
  onPredicted: (result: any) => void
  onBack: () => void
}

export default function HikerProfile({ gpxId, onPredicted, onBack }: Props) {
  const [experience, setExperience] = useState('casual')
  const [backpack, setBackpack] = useState('medium')
  const [groupSize, setGroupSize] = useState(1)
  const [hasChildren, setHasChildren] = useState(false)
  const [isRoundTrip, setIsRoundTrip] = useState(true)

  const predictMutation = useMutation({
    mutationFn: predictHike,
    onSuccess: (data) => {
      onPredicted(data)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    predictMutation.mutate({
      gpx_id: gpxId,
      experience,
      backpack,
      group_size: groupSize,
      has_children: hasChildren,
      has_elderly: false,
      is_round_trip: isRoundTrip,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Experience */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Your hiking experience
        </label>
        <div className="grid grid-cols-2 gap-2">
          {[
            { value: 'beginner', label: 'Beginner', desc: 'Rarely hike' },
            { value: 'casual', label: 'Casual', desc: 'Few times a year' },
            { value: 'regular', label: 'Regular', desc: 'Every weekend' },
            { value: 'experienced', label: 'Experienced', desc: 'Multi-day trips' },
          ].map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setExperience(opt.value)}
              className={`p-3 rounded-lg border text-left ${
                experience === opt.value
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="font-medium">{opt.label}</div>
              <div className="text-xs text-gray-500">{opt.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Backpack */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Backpack weight
        </label>
        <div className="grid grid-cols-3 gap-2">
          {[
            { value: 'light', label: 'Light', desc: '<5 kg' },
            { value: 'medium', label: 'Medium', desc: '5-10 kg' },
            { value: 'heavy', label: 'Heavy', desc: '>10 kg' },
          ].map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setBackpack(opt.value)}
              className={`p-3 rounded-lg border text-center ${
                backpack === opt.value
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="font-medium">{opt.label}</div>
              <div className="text-xs text-gray-500">{opt.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Group size */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Group size
        </label>
        <input
          type="number"
          min={1}
          max={50}
          value={groupSize}
          onChange={(e) => setGroupSize(parseInt(e.target.value) || 1)}
          className="w-full p-3 border border-gray-200 rounded-lg"
        />
      </div>

      {/* Checkboxes */}
      <div className="space-y-2">
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={hasChildren}
            onChange={(e) => setHasChildren(e.target.checked)}
            className="mr-2"
          />
          <span className="text-sm">Hiking with children</span>
        </label>

        <label className="flex items-center">
          <input
            type="checkbox"
            checked={isRoundTrip}
            onChange={(e) => setIsRoundTrip(e.target.checked)}
            className="mr-2"
          />
          <span className="text-sm">Round trip (same route back)</span>
        </label>
      </div>

      {/* Buttons */}
      <div className="flex gap-4">
        <button
          type="button"
          onClick={onBack}
          className="flex-1 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
        >
          Back
        </button>
        <button
          type="submit"
          disabled={predictMutation.isPending}
          className="flex-1 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {predictMutation.isPending ? 'Calculating...' : 'Calculate'}
        </button>
      </div>

      {predictMutation.isError && (
        <div className="bg-red-50 text-red-600 p-3 rounded-lg">
          Prediction failed. Please try again.
        </div>
      )}
    </form>
  )
}
