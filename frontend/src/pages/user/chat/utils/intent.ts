// Presentation intent detection utility
// Detects if a user message expresses desire to create/generate a PPT / presentation.
// Simple regex heuristic; can be replaced or augmented later by backend classification.

const positivePatterns: RegExp[] = [
  /(\bPPT\b|ppt)/i,
  /(프리젠테이션|프레젠테이션)/i,
  /(발표\s?자료)/i,
  /(슬라이드)/i,
  /(발표.*(만들|작성|생성))/i,
  /(슬라이드.*(만들|작성|생성))/i,
  /(PPT.*(만들|작성|생성))/i,
  /(presentation)/i
];

// If user explicitly negates wanting a PPT
const negativePatterns: RegExp[] = [
  /(말고|빼고|제외|원치|원하지)/i,
  /(PPT.*하지마)/i,
  /(슬라이드.*필요없)/i
];

export function detectPresentationIntent(userText: string | undefined | null): boolean {
  if (!userText) return false;
  const text = userText.trim();
  if (!text) return false;

  // Any positive?
  const positive = positivePatterns.some(r => r.test(text));
  if (!positive) return false;
  // Any negative overrides
  const negative = negativePatterns.some(r => r.test(text));
  if (negative) return false;
  return true;
}

// Infer intent for an assistant message by looking at the preceding user message.
// We perform this outside to keep MessageList logic simple.
export function annotateMessagesWithPresentationIntent(messages: any[]): any[] {
  // We produce a shallow cloned array with intent flags on assistant messages.
  const result = messages.map(m => ({ ...m }));
  for (let i = 0; i < result.length; i++) {
    const msg = result[i];
    if (msg.role === 'assistant') {
      // Find nearest previous user message
      for (let j = i - 1; j >= 0; j--) {
        if (result[j].role === 'user') {
          msg.presentation_intent = detectPresentationIntent(result[j].content);
          break;
        }
      }
    }
  }
  return result;
}
