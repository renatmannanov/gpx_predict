import { useState } from 'react'
import { Link } from 'react-router-dom'
import GPXUpload from '../components/features/GPXUpload'
import HikerProfile from '../components/features/HikerProfile'
import PredictionResult from '../components/features/PredictionResult'

type Step = 'upload' | 'profile' | 'result'

export default function PredictPage() {
  const [step, setStep] = useState<Step>('upload')
  const [gpxId, setGpxId] = useState<string | null>(null)
  const [prediction, setPrediction] = useState<any>(null)

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <Link
        to="/"
        className="text-primary-600 hover:text-primary-700 mb-6 inline-block"
      >
        &larr; Back
      </Link>

      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        Hike Time Prediction
      </h1>

      {/* Progress */}
      <div className="flex items-center mb-8">
        <StepIndicator
          number={1}
          label="Upload GPX"
          active={step === 'upload'}
          completed={step !== 'upload'}
        />
        <div className="flex-1 h-1 bg-gray-200 mx-2" />
        <StepIndicator
          number={2}
          label="Your Profile"
          active={step === 'profile'}
          completed={step === 'result'}
        />
        <div className="flex-1 h-1 bg-gray-200 mx-2" />
        <StepIndicator
          number={3}
          label="Result"
          active={step === 'result'}
          completed={false}
        />
      </div>

      {/* Content */}
      {step === 'upload' && (
        <GPXUpload
          onUploaded={(id) => {
            setGpxId(id)
            setStep('profile')
          }}
        />
      )}

      {step === 'profile' && gpxId && (
        <HikerProfile
          gpxId={gpxId}
          onPredicted={(result) => {
            setPrediction(result)
            setStep('result')
          }}
          onBack={() => setStep('upload')}
        />
      )}

      {step === 'result' && prediction && (
        <PredictionResult
          prediction={prediction}
          onReset={() => {
            setStep('upload')
            setGpxId(null)
            setPrediction(null)
          }}
        />
      )}
    </div>
  )
}

function StepIndicator({
  number,
  label,
  active,
  completed,
}: {
  number: number
  label: string
  active: boolean
  completed: boolean
}) {
  return (
    <div className="flex flex-col items-center">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
          completed
            ? 'bg-primary-600 text-white'
            : active
            ? 'bg-primary-100 text-primary-600 border-2 border-primary-600'
            : 'bg-gray-200 text-gray-500'
        }`}
      >
        {completed ? '✓' : number}
      </div>
      <span className="text-xs text-gray-500 mt-1">{label}</span>
    </div>
  )
}
