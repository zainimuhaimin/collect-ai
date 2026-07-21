import {
  modelConfigResponseSchema,
  modelOperationalLogResponseSchema,
  type ModelConfig,
  type ModelLogEntry,
  type WeightParameter,
} from '../../domains/ai-intelligence/aiIntelligence.schema';

export const modelConfigFixture: ModelConfig = {
  modelInfo: {
    name: 'Recovery-v4.2-Stable',
    weightingSumLabel: 'Sum of weights: 100%',
  },
  weightingParameters: [
    { label: 'Risk Weight', weight: 45, description: 'Impact of historical delinquency and credit bureau scores on prioritization.' },
    { label: 'Propensity Weight', weight: 30, description: 'Probability of payment based on recent engagement and communication responsiveness.' },
    { label: 'Settlement Velocity', weight: 25, description: 'Average time to resolution for similar portfolio segments.' },
  ],
  riskThresholds: {
    criticalLevel: '15000000',
    escalationTrigger: '5000000',
    note: 'Thresholds determine automatic task generation for human collectors.',
  },
  modelHealth: {
    status: 'Optimized',
    accuracyLabel: '88% Prediction Accuracy across 12.4k cases.',
    progress: 88,
  },
  systemPrompt: {
    version: 'Version: 02.11.A',
    content: `# COLLECTAI SYSTEM PROMPT v4.2
Anda adalah asisten pemulihan hutang yang empatik namun tegas.
Tujuan utama: Mencapai kesepakatan pembayaran tanpa merusak hubungan nasabah.

PARAMETER OPERASIONAL:
- Selalu gunakan Bahasa Indonesia yang formal (EYD).
- Tekankan keuntungan penyelesaian cepat (Diskon bunga, Skor kredit).
- Jangan gunakan nada mengancam.
- Gunakan data history Rp [Balance] sebagai referensi.`,
    affectedChannelsNote: 'Changes to this prompt affect all automated WhatsApp and Email templates.',
  },
};

export const modelOperationalLogFixture: ModelLogEntry[] = [
  { timestamp: '2023-10-24 14:22:10', action: 'Risk Weight Adjustment', user: 'admin_irwan', status: 'Success' },
  { timestamp: '2023-10-24 12:05:45', action: 'System Prompt Deployment', user: 'system_auto', status: 'Success' },
  { timestamp: '2023-10-23 09:12:00', action: 'Model Retraining Start', user: 'data_sci_team', status: 'In Progress' },
];

if (import.meta.env.DEV) {
  modelConfigResponseSchema.parse(modelConfigFixture);
  modelOperationalLogResponseSchema.parse(modelOperationalLogFixture);
}

// Mutable in-memory store so the PUT handler can persist edits across refetches within
// a dev session, and so a new audit-log row shows up after a save (mirrors what a real
// backend would do). Resets on page reload — that's fine for a mock.
export function applyWeightingParametersUpdate(next: WeightParameter[]): WeightParameter[] {
  modelConfigFixture.weightingParameters = next;
  modelOperationalLogFixture.unshift({
    timestamp: new Date().toISOString(),
    action: 'Risk Weight Adjustment',
    user: 'you (mock session)',
    status: 'Success',
  });
  return next;
}
