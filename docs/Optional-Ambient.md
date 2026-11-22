# Optional: ambient brightness, color temperature and companion light

All of this is off by default. Every entity-linked feature lets you choose the entity yourself and falls back to a manual value if the entity is missing, so rotation never breaks.

## Art brightness (TV tab)
Modes: **off**, **manual**, **lux sensor**, **entity**, **sun**.
- Lux mode: map a lux sensor between a low and high lux value to a minimum and maximum brightness percent.
- Entity mode: follow another entity's value (set its maximum).
- Sun mode: follow the sun entity.
- Options: minimum/maximum percent, disable the TV's own light sensor, minimum seconds between updates.

## Color temperature
Modes: **off**, **manual** (a Kelvin value), **entity**, **sun** (night and day values). The entity mode can follow another light or switch, such as an Adaptive Lighting switch. A *flip* option inverts the direction.

## Companion light
Pick a light that follows the TV: optionally sync its brightness and color temperature, within a minimum and maximum percent.
