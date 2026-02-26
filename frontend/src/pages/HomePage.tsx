import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <h1 className="text-4xl font-bold text-gray-900 mb-4">
        GPX Predict
      </h1>

      <p className="text-lg text-gray-600 mb-8">
        Predict hiking and running times with elevation awareness.
        Upload your GPX file and get accurate time estimates.
      </p>

      <div className="space-y-4">
        <Link
          to="/predict"
          className="block w-full bg-primary-600 text-white text-center py-3 px-6 rounded-lg font-medium hover:bg-primary-700 transition"
        >
          Start Prediction
        </Link>

        <div className="grid grid-cols-2 gap-4 mt-8">
          <div className="bg-white p-4 rounded-lg shadow-sm">
            <h3 className="font-semibold text-gray-900">For Hikers</h3>
            <p className="text-sm text-gray-500 mt-1">
              Naismith's rule with profile adjustments
            </p>
          </div>

          <div className="bg-white p-4 rounded-lg shadow-sm">
            <h3 className="font-semibold text-gray-900">For Groups</h3>
            <p className="text-sm text-gray-500 mt-1">
              Recommendations for splitting and meeting points
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
