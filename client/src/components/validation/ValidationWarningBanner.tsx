interface Props {
  warnings: string[]
  warningCount: number
}

export default function ValidationWarningBanner({ warnings, warningCount }: Props) {
  if (warnings.length === 0) return null

  const isSecond = warningCount >= 2
  const bg = isSecond ? 'bg-red-50 border-red-300' : 'bg-amber-50 border-amber-300'
  const icon = isSecond ? '🚫' : '⚠️'
  const heading = isSecond
    ? 'Please fix the issues below before saving'
    : 'Your profile has authenticity issues — please review'

  return (
    <div className={`rounded-xl border px-4 py-3 mb-4 ${bg}`}>
      <p className={`text-sm font-semibold mb-1 ${isSecond ? 'text-red-700' : 'text-amber-700'}`}>
        {icon} {heading}
      </p>
      <ul className={`text-sm space-y-0.5 list-disc list-inside ${isSecond ? 'text-red-600' : 'text-amber-600'}`}>
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
      {isSecond && (
        <p className="text-xs text-red-500 mt-2">
          Save is disabled until all issues are resolved. HireCred requires authentic, real information.
        </p>
      )}
    </div>
  )
}
