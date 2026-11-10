/** Strings translated through a variable (t(label)) are invisible to the literal scan; list them here. */
import { describe, expect, it } from 'vitest'
import { mn } from './mn'

const INDIRECT = [
  // nav groups and items
  'Record with camera', 'Monitor', 'Dashboard', 'Reports', 'Verify', 'Live verification', 'Liveness challenge', 'Upload', 'History', 'AI workspace', 'Models',
  'Datasets', 'Account', 'Profile & settings', 'Administration',
  // AuthShell points, password rules, health pill
  'Liveness is its own check', 'Metadata, not faces', 'Built for human review', 'At least 10 characters', 'A letter', 'A number',
  'Checking API', 'API offline', 'API degraded', 'API online',
  // statuses, roles, modes, spoof types
  'Real', 'Fake', 'Uncertain', 'No face', 'Multiple faces', 'Processing', 'Error', 'Administrator', 'Researcher', 'Operator', 'Viewer',
  'Live camera', 'Image upload', 'Video upload', 'Printed photo', 'Phone screen', 'Computer screen', 'Replay video', 'Other',
  // tables / stat lists / tabs
  'Images', 'Identities', 'Unlabeled', 'No identity', 'Epochs', 'Batch size', 'Learning rate', 'Image size (px)',
  'Evaluated', 'Samples', 'Threshold', 'Identity-disjoint', 'Accuracy', 'Precision', 'Recall', 'Camera', 'Faces in view', 'Detection time',
  'Detector', 'Liveness model', 'API', 'Database', 'Model loaded', 'Model trained', 'Users', 'Audit log', 'Time', 'Event', 'User', 'IP', 'Details',
  'Dark', 'Light', 'Manages users, models and datasets', 'Datasets and models', 'Runs verifications', 'Read-only',
  'Challenge passed', 'Challenge failed', 'Challenge timed out', 'Challenge finished', 'passed', 'failed', 'timed out', 'pending', 'in progress',
  'Place your face inside the frame', 'Slowly turn your head to the right', 'Slowly turn your head to the left',
  'Move a little closer to the camera', 'Keep your face still', 'Mask',
  'Per day, last {n} days (UTC)', 'Per week, last {n} days (UTC)', 'Per month, last {n} days (UTC)',
]

describe('indirect translations', () => {
  it('exist', () => expect(INDIRECT.filter((k) => !(k in mn))).toEqual([]))
})
