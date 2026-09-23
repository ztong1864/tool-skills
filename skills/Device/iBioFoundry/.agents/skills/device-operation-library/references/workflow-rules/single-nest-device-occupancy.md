# Single-Nest Device Occupancy

Use this rule when a device action uses a single physical nest and the process needs to operate on more than one labware item through that nest.

## ALPS3000

- `ALPS3000 [Seal]` uses `ALPS3000:Nest`, a single sealing position.
- If one plate has just been sealed on `ALPS3000:Nest`, move that plate to its next destination before sealing another plate.
- Do not schedule two `ALPS3000 [Seal]` actions back-to-back on different plates without an intervening move/load action for the first plate, unless the active protocol explicitly shows that Momentum can clear the nest automatically.

## XPeel

- `XPeel [Remove Seal]` uses `XPeel:Nest`, a single peeling position.
- After one plate has been unsealed on `XPeel:Nest`, move that plate to its next destination or staging location before sending another plate to `XPeel:Nest`.
- Do not schedule two `XPeel [Remove Seal]` actions back-to-back on different plates without an intervening move/load action for the first plate; the next plate cannot enter while the current plate still occupies the XPeel nest.

## General Pattern

For any single-nest device:

1. Load or present the labware at the device nest.
2. Run the device action.
3. Move the labware to the next destination or staging location.
4. Only then use the same nest for the next labware item.
