interface Props {
  label: string
  value: number  // 0–10
}

export default function RatingBar({ label, value }: Props) {
  const pct = (value / 10) * 100
  const color = value >= 7 ? '#22c55e' : value >= 4 ? '#f97316' : '#ef4444'

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-600 w-32 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-2 rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-sm font-semibold w-8 text-right" style={{ color }}>
        {value.toFixed(1)}
      </span>
    </div>
  )
}
