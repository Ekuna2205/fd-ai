import type { Role } from '@/types/auth'
import type { VerificationStatus } from '@/types/dashboard'
import { translate } from './index'

const STATUS: Record<string, string> = {
  REAL: 'Real', FAKE: 'Fake', UNCERTAIN: 'Uncertain', NO_FACE: 'No face', MULTIPLE_FACES: 'Multiple faces',
  PROCESSING: 'Processing', ERROR: 'Error',
}
const ROLE: Record<Role, string> = { administrator: 'Administrator', researcher: 'Researcher', operator: 'Operator', viewer: 'Viewer' }

/** Display name of a verification status, in the current language. */
export const statusLabel = (s: VerificationStatus | string) => translate(STATUS[s] ?? s)
export const roleLabel = (r: Role | string) => translate(ROLE[r as Role] ?? r)

const SPOOF: Record<string, string> = {
  PRINTED_PHOTO: 'Printed photo', PHONE_SCREEN: 'Phone screen', COMPUTER_SCREEN: 'Computer screen', REPLAY_VIDEO: 'Replay video', MASK: 'Mask', OTHER: 'Other',
}
export const spoofLabel = (s: string | null | undefined) => (s ? translate(SPOOF[s] ?? s) : '—')
