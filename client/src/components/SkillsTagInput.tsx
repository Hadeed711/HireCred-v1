import { useState, KeyboardEvent, useRef } from 'react'

interface Props {
  skills: string[]
  onChange: (skills: string[]) => void
  disabled?: boolean
}

export default function SkillsTagInput({ skills, onChange, disabled }: Props) {
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  function addSkill(raw: string) {
    const skill = raw.trim().toLowerCase()
    if (!skill || skills.includes(skill)) {
      setInput('')
      return
    }
    onChange([...skills, skill])
    setInput('')
  }

  function removeSkill(skill: string) {
    onChange(skills.filter((s) => s !== skill))
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addSkill(input)
    } else if (e.key === 'Backspace' && input === '' && skills.length > 0) {
      removeSkill(skills[skills.length - 1])
    }
  }

  return (
    <div
      className={`flex flex-wrap gap-2 min-h-[42px] w-full px-3 py-2 border border-gray-300 rounded-lg bg-white focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent cursor-text ${disabled ? 'opacity-60' : ''}`}
      onClick={() => inputRef.current?.focus()}
    >
      {skills.map((skill) => (
        <span
          key={skill}
          className="inline-flex items-center gap-1 px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-md text-sm font-medium"
        >
          {skill}
          {!disabled && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); removeSkill(skill) }}
              className="text-indigo-400 hover:text-indigo-700 leading-none"
            >
              ×
            </button>
          )}
        </span>
      ))}
      {!disabled && (
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => input.trim() && addSkill(input)}
          placeholder={skills.length === 0 ? 'Type a skill and press Enter…' : ''}
          className="flex-1 min-w-[120px] outline-none text-sm bg-transparent"
        />
      )}
    </div>
  )
}
