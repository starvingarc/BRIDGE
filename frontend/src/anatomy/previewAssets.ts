export const stages = {
  CS14: { file: new URL('../../private_assets/hdbr/cs14_A386.glb', import.meta.url).href, days: 34, specimen: 'A386' },
  CS15: { file: new URL('../../private_assets/hdbr/N340.glb', import.meta.url).href, days: 36, specimen: 'N340' },
} as const;
export type Stage = keyof typeof stages;
