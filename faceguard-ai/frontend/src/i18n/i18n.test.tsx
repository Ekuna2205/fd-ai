import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { LanguageSwitch } from '@/components/LanguageSwitch'
import { getLang, LanguageProvider, translate, translateServer, useT } from '.'

function Probe() {
  const { t } = useT()
  return <p>{t('Sign in')} · {t('Welcome back, {name}.', { name: 'Ada' })}</p>
}

afterEach(() => { try { localStorage.clear() } catch { /* ignore */ } })

describe('i18n', () => {
  it('switches the whole tree between English and Mongolian and remembers the choice', async () => {
    render(<LanguageProvider><LanguageSwitch /><Probe /></LanguageProvider>)
    expect(screen.getByText('Sign in · Welcome back, Ada.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'МН' }))
    expect(screen.getByText('Нэвтрэх · Тавтай морил, Ada.')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('mn')
    expect(localStorage.getItem('faceguard.lang')).toBe('mn')
    expect(getLang()).toBe('mn')
    await userEvent.click(screen.getByRole('button', { name: 'EN' }))
    expect(screen.getByText('Sign in · Welcome back, Ada.')).toBeInTheDocument()
  })

  it('falls back to English for unknown text and fills placeholders', () => {
    expect(translate('Not a known sentence', undefined, 'mn')).toBe('Not a known sentence')
    expect(translate('Last {n} days', { n: 7 }, 'mn')).toBe('Сүүлийн 7 хоног')
  })

  it('translates known server sentences and patterns, leaves others alone', () => {
    expect(translateServer('Request failed (500).', 'mn')).toBe('Хүсэлт амжилтгүй боллоо (500).')
    expect(translateServer('Some new server text.', 'mn')).toBe('Some new server text.')
    expect(translateServer('Request failed (500).', 'en')).toBe('Request failed (500).')
  })
})
