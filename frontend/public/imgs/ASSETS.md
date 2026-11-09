# Figma assets

Exported from the "scaffolding version" page of Lab-Design (copy: `eJfRDgzFmPrACig7yyCiXo`).
Files are the original Figma image fills, byte-for-byte, with no resizing or compression.
The one exception is the mic sprite, split losslessly into two PNGs and cropped to the button.

| File | Figma frame (node) |
| --- | --- |
| map/map-default.png | Component 3 / default (301:71) |
| map/map-house-hover.png | Component 3 / House Hover (253:54) |
| map/map-garden-hover.png | Component 3 / Garden Hover (253:55) |
| map/map-house-completed.png | 00. Map — House Completed (301:102) |
| map/map-garden-completed.png | 00. Map — Garden Completed (301:111) |
| house/house-rooms.png | 02 — Room selection (Static Electricity) (7:27) |
| house/living-room-background.png | 03C — Living Room Phenomenon (55:36) |
| house/living-room-balloon-girls.png | 03C, characters layer |
| house/living-room-surprise-icon.png | 03C, "icon_surprise" |
| house/bathroom-background.png | 04C — Bathroom Phenomenon (45:14) |
| house/bathroom-comb-boys.png | 04C, characters layer |
| house/kitchen-background.png | 05D — Kitchen Phenomenon 2 (51:89) |
| house/kitchen-pepper-girls.png | 05D, characters layer |
| garden/garden-zones.png | 06 — Room selection (Heredity) (171:12) |
| garden/dog-house-puppies.png | 07A — Dog Phenomenon (200:42), manual export |
| garden/dog-house-chat.png | 07B — Dog Chat (201:48) background, manual export |
| garden/corn-field-two-corns.png | 08A — Corn Phenomenon (204:42), manual export |
| garden/corn-field-chat.png | 08B — Corn Chat (204:47) background, manual export |
| garden/chicken-coop-family.png | 09A — chicken Phenomenon (301:116), manual export |
| garden/chicken-coop-chat.png | 09B — Chicken Chat (301:120) background, manual export |
| nova/nova-thinking.png | "NOVA 1" on choose screens (7:15, 253:93) |
| nova/nova-waving.png | "waving Nova illustration" (286:40) |
| nova/nova-avatar-circle.png | "NOVA circle" in chat panels |
| nova/nova-happy.png | "happy NOVA" on the all-done popup (206:95), manual export |
| ui/narrative-bubble-arrow.svg | "Polygon 1" next-line arrow (7:24) |
| ui/magnifier-bubble.png | Magnifier marker for rooms not explored yet (updated 2026-10-29, manual export) |
| ui/done.png | "Done!" marker for rooms already explored (2026-10-29, manual export) |
| ui/back-to-map-button.png, -hover.png | Back to map button variants (268:143), re-exported 2026-10-29 |
| ui/house-button.png | Room Selection Button (126:110), re-exported 2026-10-29 |
| ui/finish-exploring-button.png, -hover.png | Finish Exploring button, default (yellow) / hover (blue), frames 02 and 06 (2026-11-04, manual export) |
| ui/garden-button.png | outdoor button (236:229) |
| ui/mic-button.png, -active.png | Mic Button default / active (100:15), split from one sprite |
| ui/star.png | "star" on the all-done popup (206:97); the three stars are one image at three sizes |
| nova/nova-peeking-hd.png | "nova chat 1" above the explanation bubble, direct-instruction frames 03D/04D/05E/07B-09B: original 1536×1024 image from Figma (2026-11-04) |
| ui/arrow-button-hd.png | Next arrow beside the explanation bubble (direct-instruction frames), original 1536×1024 from Figma; mirrored in CSS for the back arrow, as in Figma (2026-11-04) |
| ui/listen-to-nova-button.png | "Listen to Nova!" button on the direct-instruction room screen (2026-11-04, manual export, renamed from "nova/listen to NOVA 2.png") |
| nova/nova-peeking.png, ui/next.png, ui/prev.png | 1x manual exports of the Nova and arrows above (2026-11-04), superseded by the originals; not used |
| ui/speech bubble.png | Explanation bubble (2026-11-04, manual export); reference only, the bubble is built in CSS so it can grow with longer bullets |
| ui/transparent_bubble.png | Caption bar from the "Talk to Nova!" frames (2026-11-04, manual export); not used, "Talk to Nova" dropped from the direct-instruction version |

## Direct-instruction garden description frames (Figma updated by 2026-11-09)

Artwork made for Nova's explanation screen (subject centred, above the bubble).
Manual exports (2026-11-09) of what each frame shows, 1463×823, so they sit at
[0, 0, 1463, 823] on the frame:

| File | Source (direct instruction version page) |
| --- | --- |
| garden/dog-house-explain.png | 07B — Dog Chat, layer "dog direct_upscayl_2x_upscayl-standard-4x 1" |
| garden/corn-field-explain.png | 08B — Corn Chat, layer "corn chat _upscayl_2x_upscayl-standard-4x 1" |
| garden/chicken-coop-explain.png | 09B — Chicken Chat, layer "Cheerful Chicken Coop Farmyard Scene 1" |

A 2x export of the same area (2926×1646) can replace them as is for sharper Retina screens.

Bubbles, popups and buttons (Nova narrative bubble, check-in and all-done popups) are built
as components with CSS shapes and real text, not images. Only illustrations live here.
