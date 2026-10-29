"""Registry of phenomena, keyed by the phenomenon id the frontend sends.

Each house room / garden zone maps to one phenomenon. Image descriptions live in
prompts/phenomenon.json and knowledge graphs in knowledge/kg.json (under kg_key).
"""

DEFAULT_PHENOMENON = "balloon"

PHENOMENA = {
    # House: static electricity
    "balloon": {
        "area": "house",
        "room": "living_room",
        "kg_key": "Hair Stands Up Near a Balloon",
        # Fills "we are going to figure out why ___" in the initial hypothesis line
        "why": "the girl's hair stands up near the balloon",
    },
    "bend": {
        "area": "house",
        "room": "bathroom",
        "kg_key": "Bending Water Stream with a Comb",
        "why": "the water stream bends toward the comb",
    },
    "pepper": {
        "area": "house",
        "room": "kitchen",
        "kg_key": "Pepper Leaping up to Spoon",
        "why": "the pepper jumps up to the spoon while the salt stays behind",
    },
    # Garden: heredity
    "puppies": {
        "area": "garden",
        "room": "dog_house",
        "kg_key": "Labrador Puppy Family",
        "why": "one puppy has golden fur when its mom and the other puppies are dark",
    },
    "corn": {
        "area": "garden",
        "room": "corn_field",
        "kg_key": "Multicolored Corn Kernels on One Cob",
        "why": "the kernels on one corn cob are so many different colors",
    },
    "chickens": {
        "area": "garden",
        "room": "chicken_coop",
        "kg_key": "Chicken Siblings with Different Comb Shapes",
        "why": "one young chicken has a tall, pointed comb when the others have low, bumpy ones",
    },
}

AREAS = ("house", "garden")


def resolve_phenomenon(phenomenon_id=None, image_path=""):
    """Return a known phenomenon id, preferring the explicit id over the image path."""
    if phenomenon_id in PHENOMENA:
        return phenomenon_id
    # Legacy clients only send the image path (e.g. /imgs/balloon.jpg)
    for pid in PHENOMENA:
        if f"{pid}." in (image_path or ""):
            return pid
    return DEFAULT_PHENOMENON


def kg_key(phenomenon):
    """Knowledge-graph key in kg.json for a phenomenon id."""
    key = PHENOMENA.get(phenomenon, {}).get("kg_key")
    return key or PHENOMENA[DEFAULT_PHENOMENON]["kg_key"]


def initial_hypothesis_line(phenomenon):
    """Fixed Nova line once the child has identified the phenomenon (discover state)."""
    why = PHENOMENA.get(phenomenon, {}).get("why")
    if not why:
        return None
    return (
        f"Perfect! So yes, we are going to figure out why {why}. "
        "To explain what might have happened here, you need to ask questions, "
        "and I'll be right here to help you answer any science questions you have "
        "along the way. Alrighty, then let's take a first guess. "
        "Why do you think this happens?"
    )
