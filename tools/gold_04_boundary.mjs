// GOLD-04: pure classification of Bitcoin/satoshi mentions found in the rendered dashboard.
// Invariant: Bitcoin-related COPY may be visible; Bitcoin/satoshi DATA (values, series, charts, controls) may not.
// No DOM access here, so the rules can be unit-tested (tests/test_gold_04_boundary_logic.py).

export const BTC_TERMS = /bitcoin|\bbtc\b|satoshi|\bsats?\b/i;

// The only approved Bitcoin copy: the "not yet available" note rendered by frontend/src/main.tsx
// (<p class="muted"> inside <header>), e.g. "Nog niet beschikbaar: reële EUR en Bitcoin."
// It must be plain text without digits (a number next to Bitcoin would be a value, not copy).
export const ALLOWED_NOTE = /^Nog niet beschikbaar: [^\d]*\.$/;

// leaf: {tag, cls, ancestors: ['MAIN','HEADER',...], text, inControl, inSvg}
export function classifyMention(leaf) {
  const isNote = leaf.tag === 'P' && /\bmuted\b/.test(leaf.cls || '') && (leaf.ancestors || []).includes('HEADER')
    && !leaf.inControl && !leaf.inSvg && ALLOWED_NOTE.test((leaf.text || '').trim());
  return isNote ? 'allowed-copy' : 'violation';
}

// controls: [{kind, label}] for buttons, tabs, options, inputs, links, aria-label/title/alt attributes
export function controlViolations(controls) {
  return controls.filter(c => BTC_TERMS.test(c.label || ''));
}

// svgTexts: text content of every chart svg (axis ticks, legend, tooltip, annotations)
export function chartViolations(svgTexts) {
  return svgTexts.filter(t => BTC_TERMS.test(t || ''));
}

export function scan({leaves = [], controls = [], svgTexts = []}) {
  const mentions = leaves.map(l => ({leaf: l, verdict: classifyMention(l)}));
  const violations = [
    ...mentions.filter(m => m.verdict === 'violation').map(m => `text: ${m.leaf.tag}.${m.leaf.cls} "${(m.leaf.text || '').slice(0, 80)}"`),
    ...controlViolations(controls).map(c => `control: ${c.kind} "${c.label}"`),
    ...chartViolations(svgTexts).map(t => `chart: "${t.slice(0, 80)}"`),
  ];
  return {allowed: mentions.filter(m => m.verdict === 'allowed-copy').map(m => m.leaf.text.trim()), violations};
}
