/**
 * Phenomena shown in the house (static electricity) and garden (heredity) areas.
 * Ids must match backend/phenomena.py.
 *
 * Layout rects are [x, y, width, height] in Figma pixels on a 1463×823 frame
 * (the map frame is 1463×889), copied from the Lab-Design file.
 */
export type Area = 'house' | 'garden'
export type Rect = [number, number, number, number]

export interface SceneLayer {
  src: string
  rect: Rect
}

/** One arrangement of the scene: full-screen intro, or shifted left beside the chat */
export interface SceneLayout {
  background: SceneLayer
  /** Washes out the background so the characters stand out */
  wash?: Rect
  characters?: SceneLayer
  icon?: SceneLayer
}

export interface Phenomenon {
  id: string
  area: Area
  room: string
  label: string
  /** Nova's fixed first line when the child enters the room */
  opening: string
  /** Magnifier bubble on the area screen */
  magnifier: [number, number]
  /** Clickable region of the room on the area screen */
  hitbox: Rect
  intro: SceneLayout
  chat: SceneLayout
}

const HOUSE = '/imgs/house'
const GARDEN = '/imgs/garden'

export const PHENOMENA: Record<string, Phenomenon> = {
  balloon: {
    id: 'balloon',
    area: 'house',
    room: 'living_room',
    label: 'Living room',
    opening: 'Here we are in the living room! What do you find strange here?',
    magnifier: [754, 426],
    hitbox: [225, 488, 1065, 262],
    intro: {
      background: { src: `${HOUSE}/living-room-background.png`, rect: [-304, -91, 2071, 1166] },
      wash: [0, 0, 1463, 849],
      characters: { src: `${HOUSE}/living-room-balloon-girls.png`, rect: [112, 0, 1186.5, 791] },
      icon: { src: `${HOUSE}/living-room-surprise-icon.png`, rect: [1019, 96, 310, 207] }
    },
    chat: {
      background: { src: `${HOUSE}/living-room-background.png`, rect: [-312, 0, 1839, 1036] },
      wash: [-26, 0, 1515, 880],
      characters: { src: `${HOUSE}/living-room-balloon-girls.png`, rect: [-160, 80, 1042, 695] },
      icon: { src: `${HOUSE}/living-room-surprise-icon.png`, rect: [646, 110, 198.5, 132.3] }
    }
  },
  bend: {
    id: 'bend',
    area: 'house',
    room: 'bathroom',
    label: 'Bathroom',
    opening: 'Hey there! What do you find odd in this bathroom?',
    magnifier: [1020, 99],
    hitbox: [848, 188, 442, 285],
    intro: {
      background: { src: `${HOUSE}/bathroom-background.png`, rect: [0, -126, 1558, 1039] },
      wash: [0, -48, 1466, 884],
      characters: { src: `${HOUSE}/bathroom-comb-boys.png`, rect: [137, 59, 1230, 820] }
    },
    chat: {
      background: { src: `${HOUSE}/bathroom-background.png`, rect: [-255, -112, 1742, 979] },
      wash: [-26, -62, 1555, 942],
      characters: { src: `${HOUSE}/bathroom-comb-boys.png`, rect: [-27, 235, 909, 606] }
    }
  },
  pepper: {
    id: 'pepper',
    area: 'house',
    room: 'kitchen',
    label: 'Kitchen',
    opening: 'Welcome to the kitchen! What do you find odd here?',
    magnifier: [574, 87],
    hitbox: [225, 188, 600, 285],
    intro: {
      background: { src: `${HOUSE}/kitchen-background.png`, rect: [0, -48, 1536, 1024] },
      wash: [0, -48, 1466, 884],
      characters: { src: `${HOUSE}/kitchen-pepper-girls.png`, rect: [111, 75, 1243.5, 829] }
    },
    chat: {
      background: { src: `${HOUSE}/kitchen-background.png`, rect: [-300, 16, 1964, 807] },
      wash: [-26, 25, 1515, 880],
      characters: { src: `${HOUSE}/kitchen-pepper-girls.png`, rect: [0, 282, 852, 568] }
    }
  },
  // Garden scenes are full-frame illustrations; each chat frame (07B/08B/09B) has its
  // own artwork with the subject moved left of the panel
  puppies: {
    id: 'puppies',
    area: 'garden',
    room: 'dog_house',
    label: 'Dog house',
    opening: 'Cute little puppies! Is there anything surprising about these puppies?',
    magnifier: [339, 90],
    hitbox: [0, 120, 340, 260],
    intro: { background: { src: `${GARDEN}/dog-house-puppies.png`, rect: [0, 0, 1463, 823] } },
    chat: { background: { src: `${GARDEN}/dog-house-chat.png`, rect: [0, 0, 1463, 823] } }
  },
  corn: {
    id: 'corn',
    area: 'garden',
    room: 'corn_field',
    label: 'Corn field',
    opening: 'We have two corns here! What stands out to you about these corns?',
    magnifier: [1315, 364],
    hitbox: [1110, 450, 353, 373],
    intro: { background: { src: `${GARDEN}/corn-field-two-corns.png`, rect: [0, 0, 1463, 823] } },
    chat: { background: { src: `${GARDEN}/corn-field-chat.png`, rect: [0, 0, 1463, 823] } }
  },
  chickens: {
    id: 'chickens',
    area: 'garden',
    room: 'chicken_coop',
    label: 'Chicken coop',
    opening: 'Here we have a chicken family! What do you find interesting about these chickens?',
    magnifier: [862, 152],
    hitbox: [600, 165, 750, 375],
    intro: { background: { src: `${GARDEN}/chicken-coop-family.png`, rect: [0, 0, 1463, 823] } },
    chat: { background: { src: `${GARDEN}/chicken-coop-chat.png`, rect: [0, 0, 1463, 823] } }
  }
}

export interface AreaConfig {
  id: Area
  label: string
  scene: SceneLayer
  /** Nova's lines on the area's room-selection screen */
  intro: string[]
  /** Chat-screen button that returns to this area's room selection */
  backButton: string
}

export const AREAS: Record<Area, AreaConfig> = {
  house: {
    id: 'house',
    label: 'house',
    scene: { src: `${HOUSE}/house-rooms.png`, rect: [-150, -87, 1770, 996] },
    intro: [
      'Welcome to the house!',
      'There are three rooms in this house waiting for your closer look. Which room would you like to explore first?',
      "Click on the room you'd like to explore!"
    ],
    backButton: '/imgs/ui/house-button.png'
  },
  garden: {
    id: 'garden',
    label: 'garden',
    scene: { src: `${GARDEN}/garden-zones.png`, rect: [-157, -40, 1688, 932] },
    intro: [
      'Welcome to the garden!',
      'There are three zones in this garden waiting for your closer look. Which place would you like to explore first?',
      "Click on the zone you'd like to explore!"
    ],
    backButton: '/imgs/ui/garden-button.png'
  }
}

export const phenomenaInArea = (area: Area) =>
  Object.values(PHENOMENA).filter(p => p.area === area)

/** Map page (1463×889 frame) */
export const MAP = {
  images: {
    default: '/imgs/map/map-default.png',
    houseHover: '/imgs/map/map-house-hover.png',
    gardenHover: '/imgs/map/map-garden-hover.png',
    houseCompleted: '/imgs/map/map-house-completed.png',
    gardenCompleted: '/imgs/map/map-garden-completed.png'
  },
  hitboxes: {
    house: [22, 120, 638, 458] as Rect,
    garden: [700, 300, 763, 589] as Rect
  },
  firstVisit: [
    "Hi, I'm Nova, your friendly science assistant!",
    "We're going to explore some science mysteries happening around the house and the garden together.",
    'Which one would you like to explore first? Move your mouse and click on the place you are curious about!'
  ],
  returnVisit: (area: Area) => [
    "Welcome back! I'm Nova, your friendly science assistant.",
    "I'm here with you again since we have one more mystery to explore together.",
    `Move your mouse and click on the ${area} to start our last science adventure!`
  ]
}

/** Legacy routes only carry the image path (e.g. /imgs/balloon.jpg). */
export function phenomenonForImage(imagePath?: string): Phenomenon | undefined {
  if (!imagePath) return undefined
  return Object.values(PHENOMENA).find(p => imagePath.includes(`${p.id}.`))
}
