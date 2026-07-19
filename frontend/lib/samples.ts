// Five synthetic sample intakes for the dropdown. All fictional — no real client
// data (see the README's synthetic-data disclaimer). They deliberately vary in
// matter type and completeness so the reviewer can see extraction, the
// low-confidence path, and missing-field flagging.

export interface Sample {
  label: string;
  text: string;
}

export const SAMPLES: Sample[] = [
  {
    label: "Family — divorce & custody (complete)",
    text: `Hi, my name is Priya Menon, you can reach me at priya.menon@example.com or (415) 555-0198. My husband and I are separating and we need help with the divorce and custody of our two kids. We're in San Francisco, California. Our mediation date is set for March 3, 2026. What are the next steps?`,
  },
  {
    label: "Employment — sparse, missing contact info",
    text: `Hello, I got hurt at work last month and my employer is giving me a hard time. Can someone call me back?`,
  },
  {
    label: "Landlord/tenant — asks for legal advice",
    text: `This is David. My landlord in Austin, TX is trying to evict me and I signed the lease on 01/15/2024. Do I have a case? Should I stop paying rent until this is resolved? Please advise. My number is 512-555-7742.`,
  },
  {
    label: "Real Estate — closing question",
    text: `Good afternoon — I'm Sofia Reyes (sofia.reyes@example.com, 305-555-0142). We're buying a condo in Miami, FL and our closing is scheduled for August 12, 2026. We'd like a lawyer to review the purchase contract before we sign.`,
  },
  // The next two are seeded to collide with the synthetic matter history in
  // backend/samples/matter_history.json, so the conflict screen actually fires
  // in a demo. Neither name is spelled the way the firm's records spell it —
  // that's the point.
  {
    label: "Real Estate — CONFLICT (landlord is a former client)",
    text: `Hello, my name is Nadia Bergstrom. I rent a unit from Kestrel Properties LLC in Boise, Idaho and they are withholding my security deposit after I moved out on May 1, 2026. You can reach me at nadia.bergstrom@example.com or 208-555-0164.`,
  },
  {
    label: "Wills & Estates — CONFLICT via nickname (Kate/Katherine)",
    text: `Hi, I'm Mateo Delgado (mateo.delgado@example.com). My sister Kate Hall and I are in a dispute over our late mother's estate in Portland, Oregon. I would like to speak to someone about my options as a beneficiary.`,
  },
  {
    label: "Wills & Estates — no jurisdiction given",
    text: `My father passed away recently and I need help settling his estate and figuring out probate. I'm the executor. You can email me at jordan.k@example.com. Please let me know what documents you need.`,
  },
];
