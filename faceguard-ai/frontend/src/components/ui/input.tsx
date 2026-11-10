import { Eye, EyeOff } from 'lucide-react'
import { useId, useState, type InputHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'
import { useT } from '@/i18n'

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: string
}

export function Field({ label, error, hint, type = 'text', className, ...props }: FieldProps) {
  const id = useId()
  const [shown, setShown] = useState(false)
  const { t } = useT()
  const isPassword = type === 'password'
  const describedBy = error ? `${id}-err` : hint ? `${id}-hint` : undefined
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">{label}</label>
      <div className="relative">
        <input
          id={id}
          type={isPassword && shown ? 'text' : type}
          aria-invalid={!!error}
          aria-describedby={describedBy}
          className={cn(
            'h-10 w-full rounded-lg border bg-bg px-3 text-sm placeholder:text-muted/60 transition-colors',
            error ? 'border-danger/60' : 'border-border hover:border-muted/40',
            isPassword && 'pr-10', className,
          )}
          {...props}
        />
        {isPassword && (
          <button type="button" onClick={() => setShown((s) => !s)} aria-label={shown ? t('Hide password') : t('Show password')}
            className="absolute right-1.5 top-1.5 grid size-7 cursor-pointer place-items-center rounded-md text-muted hover:text-fg">
            {shown ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        )}
      </div>
      {error ? <p id={`${id}-err`} role="alert" className="mt-1.5 text-xs text-danger">{error}</p>
        : hint ? <p id={`${id}-hint`} className="mt-1.5 text-xs text-muted">{hint}</p> : null}
    </div>
  )
}
