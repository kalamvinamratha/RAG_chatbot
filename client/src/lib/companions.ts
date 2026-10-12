export type CompanionKind = 'cardiology' | 'gynaecology' | 'general_medicine' | 'neurology';

export interface CompanionProfile {
  kind: CompanionKind;
  name: string;
  personality: string;
  introduction: string;
  greeting: string;
  prompts: readonly string[];
}

const companions: Record<CompanionKind, CompanionProfile> = {
  cardiology: {
    kind: 'cardiology',
    name: 'Pip',
    personality: 'A little heart. A lot of curiosity.',
    introduction: 'Let’s explore heart-related findings in your records.',
    greeting: 'Let’s get to the heart of your records.',
    prompts: [
      'Summarize the heart-related findings in my documents.',
      'What cardiovascular medications are recorded in these sources?',
      'Compare the cardiac test results across my records.',
    ],
  },
  gynaecology: {
    kind: 'gynaecology',
    name: 'Bloom',
    personality: 'Gentle company for important questions.',
    introduction: 'I help you explore reproductive health and pregnancy-related documents.',
    greeting: 'A little space for your important questions.',
    prompts: [
      'Summarize the reproductive health findings in my documents.',
      'What pregnancy-related results are recorded in these sources?',
      'Help me understand the terminology in my selected reports.',
    ],
  },
  general_medicine: {
    kind: 'general_medicine',
    name: 'Sage',
    personality: 'The details, and the bigger picture.',
    introduction: 'Let’s connect the bigger picture across your reports.',
    greeting: 'Let’s put the pieces together.',
    prompts: [
      'Summarize the key findings across my selected documents.',
      'Are any medication interactions recorded in these sources?',
      'Compare the lab results and highlight changes over time.',
    ],
  },
  neurology: {
    kind: 'neurology',
    name: 'Lumi',
    personality: 'A bright little guide to complex records.',
    introduction: 'I help you explore brain and nervous-system findings.',
    greeting: 'A little light on the complex details.',
    prompts: [
      'Summarize the neurological findings in my documents.',
      'What do my sources say about the imaging results?',
      'Compare the symptoms and findings recorded over time.',
    ],
  },
};

export function getCompanion(domainKey: string | undefined): CompanionProfile {
  return companions[domainKey as CompanionKind] || companions.general_medicine;
}
