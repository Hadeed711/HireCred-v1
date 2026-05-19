import { AlertTriangle } from 'lucide-react'

interface Props {
  warnings: string[]
}

export default function ValidationWarningBanner({ warnings }: Props) {
  if (warnings.length === 0) return null

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 mb-4">
      <p className="text-sm font-semibold mb-1 text-amber-700">
        <AlertTriangle className="inline-block h-4 w-4 mr-1 -mt-0.5" />
        Profile notes — review before sharing with hirers
      </p>
      <ul className="text-sm space-y-0.5 list-disc list-inside text-amber-600">
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </div>
  )
}
