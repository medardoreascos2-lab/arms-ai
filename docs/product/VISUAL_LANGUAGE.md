# ARMS + MEDAR visual language

The product should read as a calm financial workspace. The first scan answers where the user is, what is known, what needs review, and which evidence supports it.

- **Color:** deep navy surfaces, soft cyan for navigation and focus, restrained semantic status colors. Color never carries status alone.
- **Type:** plain language, clear heading levels, compact labels, readable body copy, and tabular numerals for verified metrics when added.
- **Space and density:** consistent token steps; dense data belongs inside clearly named cards. Do not crowd the first screen with every metric.
- **Motion:** brief state feedback only. Respect reduced-motion preferences.
- **Trust:** label missing, stale, simulated, PAPER, and hypothetical data. Never imply profits, certainty, account mutation, or LIVE authority from a visual treatment.
- **Alerts:** reserve critical treatment for genuinely urgent verified conditions. No blinking, neon, fear-based language, or gambling imagery.

Design tokens live in `frontend/src/app/product/product.module.css` and are scoped to the product shell. Product components consume them through local CSS modules, preserving legacy dashboard styles.
