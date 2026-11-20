# Phase 3 ADR · Fuel and dawn

Each lantern stores fuel as integer sixtieths of a unit. Natural decay subtracts one increment per simulation tick and each draining Shade subtracts five. The output rounds only when serializing. Scenario setup can establish lantern history without increasing the player's successful light count or score.

Fuel decay and draining run before interaction. An empty lantern goes out and clears its deposit immediately. A subsequent interaction may relight it in the same tick. Loss of the last flame takes priority over the dawn check. Dawn uses the number of lit lanterns after all tick actions.

The old immediate-win regression was replaced by a scenario that lights the last lantern on tick 1, remains playing and wins at dawn on tick 3. The historical Phase 2 output remains in its proof folder. The current tests also cover depletion and relight, drain and refuel, increased capacity, and death at dawn.

The Panda3D dash returns to the contract duration of 12 ticks so that the previous interface-only tuning does not diverge from the simulation used for assessment.
