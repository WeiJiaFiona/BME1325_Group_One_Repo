import type { VercelRequest, VercelResponse } from '@vercel/node';

// Same checkRedFlags function as in message.ts
function checkRedFlags(text: string): Array<{ condition: string; evidence: string; action: string; ats: number }> {
  const lowerText = text.toLowerCase();
  const flags: Array<{ condition: string; evidence: string; action: string; ats: number }> = [];

  const patterns = [
    // ATS 2 - Emergency
    { pattern: /chest pain|chest tightness|chest pressure|crushing.*chest|radiating.*arm|heart attack|having.*heart attack|think.*heart attack|mi\b|myocardial/, condition: 'Chest pain', action: 'Immediate ECG and cardiac workup', ats: 2 },
    { pattern: /can.?t type|cannot type|unable to type|hard to type|can.?t communicate|cannot communicate/, condition: 'Communication impairment', action: 'Patient unable to communicate - call 000 immediately', ats: 2 },
  ];

  for (const { pattern, condition, action, ats } of patterns) {
    if (pattern.test(lowerText)) {
      const match = lowerText.match(pattern);
      flags.push({
        condition,
        evidence: match ? match[0] : 'keyword detected',
        action,
        ats,
      });
    }
  }

  return flags;
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader('Access-Control-Allow-Origin', '*');

  const message = req.query.message as string || req.body?.message || 'I am having a heart attack and cannot type';
  const redFlags = checkRedFlags(message);

  return res.json({
    message,
    lowerMessage: message.toLowerCase(),
    redFlags,
    hasRedFlags: redFlags.length > 0,
    worstATS: redFlags.length > 0 ? Math.min(...redFlags.map(f => f.ats)) : 5,
    expectedSeverity: redFlags.length > 0 ? 6 - Math.min(...redFlags.map(f => f.ats)) : 1,
  });
}
