/** Mongolian translations, keyed by the English source text. Split by area to keep the files reviewable. */
import { admin } from './mn/admin'
import { auth } from './mn/auth'
import { collect } from './mn/collect'
import { common } from './mn/common'
import { data } from './mn/data'
import { verify } from './mn/verify'

export const mn: Record<string, string> = { ...common, ...auth, ...verify, ...data, ...admin, ...collect }
