"""
Local3D Studio Dynamic Style & Anatomy Router (Prompt Enhancer)
Separates technical 3D reconstruction directives from artistic style,
featuring an Intelligent Subject & Anatomy Classifier that prevents over-fitting
and generates appropriate poses and de-occlusion rules for bipeds, quadrupeds,
props/weapons, vehicles, and generic objects.
"""

import re
from typing import Optional, List, Dict, Any


STYLE_FAITHFUL_ANATOMICAL = "faithful_anatomical"
STYLE_REALISTIC_SCULPT = "realistic_sculpt"
STYLE_GAME_PROP = "game_prop"
STYLE_TABLETOP_MINIATURE = "tabletop_miniature"
STYLE_STYLIZED_VINYL = "stylized_vinyl"

SUPPORTED_ART_STYLES = [
    STYLE_FAITHFUL_ANATOMICAL,
    STYLE_REALISTIC_SCULPT,
    STYLE_GAME_PROP,
    STYLE_TABLETOP_MINIATURE,
    STYLE_STYLIZED_VINYL
]

CATEGORY_HUMANOID = "humanoid_biped"
CATEGORY_QUADRUPED = "quadruped_creature"
CATEGORY_PROP_WEAPON = "prop_weapon"
CATEGORY_VEHICLE = "vehicle_hard_surface"
CATEGORY_FAUNA_OTHER = "fauna_other"
CATEGORY_GENERIC_OBJECT = "generic_object"

HUMANOID_POSE_A = "a_pose"
HUMANOID_POSE_T = "t_pose"
HUMANOID_POSE_ACTION = "action_pose"
HUMANOID_POSE_NATURAL = "natural"

SUPPORTED_HUMANOID_POSES = [
    HUMANOID_POSE_A,
    HUMANOID_POSE_T,
    HUMANOID_POSE_ACTION,
    HUMANOID_POSE_NATURAL
]


def get_humanoid_pose_directives(pose: str = HUMANOID_POSE_A) -> str:
    """Returns exact geometric directives for canonical humanoid poses."""
    p = pose.lower().strip()
    if p == HUMANOID_POSE_T:
        return (
            "canonical upright T-pose: arms extended horizontally straight out at 90 degrees from shoulders, "
            "elbows straight, wrists aligned, flat open hands with palms facing down toward the floor, straight upright spine, "
            "legs straight and shoulder-width apart with clear open negative space"
        )
    elif p == HUMANOID_POSE_ACTION:
        return (
            "heroic dynamic action stance: expressive combat posture, grounded balanced footwork, "
            "asymmetrical limb placement with distinct silhouette separation between arms, torso, and legs"
        )
    elif p == HUMANOID_POSE_NATURAL:
        return (
            "relaxed natural standing pose: casual upright posture, arms hanging comfortably at sides with visible clearance "
            "from the waist, natural weight distribution on both feet"
        )
    else:  # a_pose (default)
        return (
            "canonical upright A-pose: arms abducted at a 35-to-45 degree downward angle away from the torso, "
            "wrists straight, palms facing inward toward the thighs, straight spine, legs straight and shoulder-width apart, "
            "ample clear open air space under armpits and between inner thighs to guarantee zero limb fusion"
        )


def detect_subject_category(text: str) -> str:
    """
    Intelligently classifies subject into architectural categories
    to dynamically adapt pose, turnarounds, de-occlusion rules, and pedestal shapes.
    Supports English and Italian prompts with intelligent primary-subject resolution.
    """
    lower = text.lower().strip()

    # Base keyword sets (EN + IT)
    weapon_keywords = [
        "sword", "blade", "axe", "shield", "bow", "hammer", "spear", "dagger",
        "gun", "rifle", "pistol", "wand", "staff", "chest", "helmet", "gauntlet",
        "weapon", "relic", "chalice", "potion", "ring", "amulet", "scroll", "tome",
        "saber", "katana", "mace", "scythe", "armor", "armour",
        "spada", "lama", "ascia", "scudo", "arco", "martello", "lancia", "pugnale",
        "pistola", "fucile", "bacchetta", "bastone", "elmo", "forziere", "baule",
        "calice", "pozione", "anello", "amuleto", "sciabola", "alabarda", "reliquia"
    ]

    vehicle_keywords = [
        "car", "vehicle", "truck", "tank", "plane", "airplane", "spaceship",
        "starship", "ship", "boat", "motorcycle", "bike", "submarine", "train",
        "drone", "rover", "mecha", "helicopter", "chassis", "automobile",
        "macchina", "veicolo", "camion", "aereo", "astronave", "nave", "barca",
        "moto", "motocicletta", "sommergibile", "treno", "elicottero", "automobile", "auto"
    ]

    quadruped_keywords = [
        "dog", "cat", "puppy", "kitten", "dragon", "horse", "lion", "tiger",
        "wolf", "bear", "dinosaur", "creature", "reptile", "lizard", "monster",
        "beast", "fox", "hound", "leopard", "cheetah", "panther", "rhino",
        "elephant", "hippo", "deer", "stag", "quadruped", "dino",
        "cane", "gatto", "cucciolo", "gattino", "drago", "cavallo", "leone", "tigre",
        "lupo", "orso", "dinosauro", "mostro", "creatura", "bestia", "volpe",
        "levriero", "pantera", "rinoceronte", "elefante", "cervo"
    ]

    fauna_keywords = [
        "bird", "eagle", "hawk", "owl", "parrot", "fish", "shark", "whale",
        "dolphin", "snake", "serpent", "cobra", "octopus", "squid", "spider", "insect",
        "uccello", "aquila", "falco", "gufo", "pappagallo", "pesce", "squalo",
        "balena", "delfino", "serpente", "vipera", "polpo", "ragno", "insetto"
    ]

    humanoid_keywords = [
        "man", "woman", "person", "human", "character", "warrior", "knight",
        "soldier", "boy", "girl", "hero", "superhero", "wizard", "monk",
        "ninja", "samurai", "cyborg", "android", "anime", "guy", "lady",
        "figure", "figurine", "biped", "pikachu", "chibi", "statue",
        "santa", "santa claus", "babbo natale", "elf", "elfo", "dwarf", "nano",
        "gnome", "gnomo", "goblin", "orc", "orco", "zombie", "alien", "alieno",
        "vampire", "vampiro", "skeleton", "scheletro", "pirate", "pirata", "clown",
        "astronaut", "astronauta", "king", "re", "queen", "regina", "prince", "princess",
        "principessa", "priest", "prete", "farmer", "contadino", "babbo",
        "uomo", "donna", "persona", "umano", "personaggio", "guerriero",
        "cavaliere", "soldato", "ragazzo", "ragazza", "eroe", "mago", "monaco",
        "statuetta", "statuina", "paladino"
    ]

    has_weapon = any(k in lower for k in weapon_keywords)
    has_vehicle = any(k in lower for k in vehicle_keywords)
    has_quad = any(k in lower for k in quadruped_keywords)
    has_fauna = any(k in lower for k in fauna_keywords)
    has_humanoid = any(k in lower for k in humanoid_keywords)

    # If prompt starts with a weapon keyword (e.g. "sword of knight", "spada del cavaliere")
    first_word = lower.split()[0] if lower.split() else ""
    if any(k in first_word for k in ["sword", "blade", "axe", "shield", "bow", "hammer", "spada", "lama", "ascia", "scudo", "pugnale", "dagger"]):
        return CATEGORY_PROP_WEAPON

    # Otherwise, characters and creatures are prioritized over held accessories
    if has_humanoid:
        return CATEGORY_HUMANOID

    if has_quad:
        return CATEGORY_QUADRUPED

    if has_vehicle:
        return CATEGORY_VEHICLE

    if has_weapon:
        return CATEGORY_PROP_WEAPON

    if has_fauna:
        return CATEGORY_FAUNA_OTHER

    return CATEGORY_GENERIC_OBJECT


def detect_explicit_style_intent(text: str) -> Optional[str]:
    """Detects if user explicitly demanded a specific style via keywords."""
    lower = text.lower()
    if any(k in lower for k in ["funko", "chibi", "vinyl toy"]):
        return STYLE_STYLIZED_VINYL
    if any(k in lower for k in ["zbrush", "realistic sculpt", "hyperrealistic", "anatomical sculpt"]):
        return STYLE_REALISTIC_SCULPT
    if any(k in lower for k in ["game prop", "hard surface", "hard-surface", "weapon", "chest", "vehicle", "prop"]):
        return STYLE_GAME_PROP
    if any(k in lower for k in ["miniature", "tabletop", "wargame", "warhammer", "heroic scale"]):
        return STYLE_TABLETOP_MINIATURE
    return None


def clean_transparency_keywords(text: str) -> str:
    """Removes transparent/glass descriptors that degrade depth map and surface reconstruction."""
    patterns = [
        r"\btransparent\b", r"\btransparency\b", r"\bclear glass\b", r"\bacrylic\b",
        r"\bsee-through\b", r"\btranslucent\b", r"\bglass stand\b", r"\bacrylic peg\b"
    ]
    for pattern in patterns:
        text = re.sub(pattern, "solid opaque", text, flags=re.IGNORECASE)
    return text


def get_style_directives(art_style: str) -> str:
    """Returns artistic style prompt expansion."""
    if art_style == STYLE_REALISTIC_SCULPT:
        return "ZBrush high-detail realistic digital sculpture, fine anatomical surface detailing, authentic muscular and skeletal structure"
    elif art_style == STYLE_GAME_PROP:
        return "hard-surface 3D game prop asset, crisp planar bevels, sharp mechanical definition, clean chamfers"
    elif art_style == STYLE_TABLETOP_MINIATURE:
        return "32mm/75mm tabletop wargaming miniature, heroic scale stylized anatomy, accentuated surface edge depth"
    elif art_style == STYLE_STYLIZED_VINYL:
        return "stylized collectible figurine, smooth minimal rounded shapes"
    else:
        return "official canonical design, 100% faithful authentic anatomy and original character proportions, true-to-lore body-to-head ratio"


def enhance_prompt_for_3d(
    user_prompt: str,
    mode: str = "3d_print",
    art_style: str = STYLE_FAITHFUL_ANATOMICAL,
    multiview: bool = True,
    add_pedestal_base: bool = False,
    humanoid_pose: str = HUMANOID_POSE_A
) -> str:
    """
    Dynamic Style & Anatomy Router for 3D Prompt Enhancement.
    """
    prompt = clean_transparency_keywords(user_prompt.strip())
    category = detect_subject_category(prompt)

    explicit_style = detect_explicit_style_intent(prompt)
    if explicit_style:
        art_style = explicit_style
    elif art_style == STYLE_STYLIZED_VINYL:
        art_style = STYLE_FAITHFUL_ANATOMICAL

    pose_extra = ""
    if category == CATEGORY_HUMANOID:
        pose_extra = f", {get_humanoid_pose_directives(humanoid_pose)}"

    technical_rules = (
        f"centered full subject{pose_extra}, neutral studio softbox lighting from all directions, even albedo, "
        "no harsh cast shadows, zero specular glare, pure solid uniform neutral white background (#ffffff), "
        "clear silhouette separation, crisp 3D surface relief, watertight solid geometry, "
        "distinct well-articulated 3D shapes with defined depth around every limb and appendage, "
        "zero flat backdrop slabs, zero tombstone wall fusion, zero relief plaque melting"
    )

    monochrome_sculpt_rules = (
        "tangible physical 3D relief on all details, recessed eye sockets with raised pupils, "
        "sculpted mouth cavity depth, raised anatomical contour lines casting distinct physical shadows "
        "for single-color monochrome 3D printing"
    )

    style_directives = get_style_directives(art_style)

    if add_pedestal_base:
        grounding_directives = (
            "resting firmly on a solid flat circular matte grey display pedestal with clean bevelled edges "
            "flush with the ground plane, perfectly flat bottom base"
        )
    else:
        grounding_directives = (
            "standing or resting naturally and directly on the ground plane at Z=0 without any artificial pedestal disc, "
            "self-supporting base with a flat grounded footprint for print bed adhesion"
        )

    if multiview:
        layout_directives = (
            "3-view character model sheet showing three synchronized orthographic angles side-by-side in one image: "
            "[Left: Front Orthographic View], "
            "[Center: Left Side Profile View showing distinct appendage depth and clear silhouette], "
            "[Right: Back Orthographic View showing rear spine and anatomy]. "
            "Perfect anatomical consistency across all 3 views, perfectly aligned horizontal eyelines"
        )
    else:
        layout_directives = "front-three-quarter orthographic hero angle, full body view, centered"

    mode_extra = "structural stability, manifold solid volume, print bed adhesion calibrated"

    return (
        f"{prompt}, {style_directives}, {layout_directives}, {technical_rules}, "
        f"{monochrome_sculpt_rules}, {grounding_directives}, {mode_extra}"
    )


def compile_3d_master_prompt(
    subject: str,
    art_style: str = STYLE_FAITHFUL_ANATOMICAL,
    key_details: Optional[list] = None,
    add_pedestal_base: bool = False,
    humanoid_pose: str = HUMANOID_POSE_A
) -> str:
    """
    Compiles an adaptive 3-Panel Orthographic Turnaround prompt tailored to the subject's anatomy.
    Dynamically adjusts pose, columns, and de-occlusion rules based on detected category.
    """
    subj = clean_transparency_keywords(subject.strip())
    category = detect_subject_category(subj)

    explicit_style = detect_explicit_style_intent(subj)
    if explicit_style:
        art_style = explicit_style
    elif art_style == STYLE_STYLIZED_VINYL:
        art_style = STYLE_FAITHFUL_ANATOMICAL

    style_dir = get_style_directives(art_style)

    details_str = ""
    if key_details and len(key_details) > 0:
        details_str = f", key anatomical details: {', '.join(key_details)}"

    grounding_str = (
        "resting firmly on a solid flat circular matte grey display pedestal with bevelled rim flush with ground"
        if add_pedestal_base else
        "grounded naturally and solidly on the floor plane at Z=0 without any artificial pedestal disc"
    )

    # Adaptive columns and de-occlusion rules based on subject category
    if category == CATEGORY_HUMANOID:
        pose_desc = get_humanoid_pose_directives(humanoid_pose)
        columns_spec = (
            f"A horizontal 3-panel turnaround model sheet of {subj}: "
            f"[Column 1 (0%-33%): Full-body FRONT orthographic view of {subj}, facing straight at camera, {pose_desc}], "
            f"[Column 2 (33%-66%): Full-body LEFT SIDE profile orthographic view of the exact same {subj}, strictly facing LEFT, clean side profile of torso and limbs with visible clearance between foreground and background arms], "
            f"[Column 3 (66%-100%): Full-body BACK orthographic view of the exact same {subj}, clearly showing rear anatomy, spine, shoulder blades, and rear legs]"
        )
        deocclusion_rules = (
            f"MANDATORY ZERO SELF-OCCLUSION RULE: {pose_desc}. "
            "Hair, capes, or cloaks must not fuse into the torso or hide the arms and legs. "
            "Deep high-contrast sculpted ambient occlusion crevices separating limbs from torso"
        )
    elif category == CATEGORY_QUADRUPED:
        columns_spec = (
            f"A horizontal 3-panel turnaround model sheet of {subj}: "
            f"[Column 1 (0%-33%): Full-body FRONT orthographic view of {subj}, facing straight at camera, wide staggered stance showing all 4 distinct legs and paws clearly separated], "
            f"[Column 2 (33%-66%): Full-body LEFT SIDE profile orthographic view of the exact same {subj}, strictly facing LEFT, open staggered gait with both front and rear legs visible, wings or back features raised high], "
            f"[Column 3 (66%-100%): Full-body BACK orthographic view of the exact same {subj}, clearly showing rear haunches, spine attachment, and clean tail extension]"
        )
        deocclusion_rules = (
            "MANDATORY ZERO SELF-OCCLUSION RULE: "
            "all 4 legs (both front legs AND both hind legs/haunches) must be 100% unobstructed, distinct, and clearly separated with visible empty air space between limbs. "
            "Any wings or side appendages raised high above the waist, NEVER hanging down over the hips, thighs, or hind legs. "
            "Staggered wide stance: rear legs clearly visible outside front legs. "
            "Tail extending cleanly behind along the floor without wrapping over or in front of the legs. "
            "Deep sculpted ambient occlusion crevices separating foreground limbs from background limbs"
        )
    elif category == CATEGORY_PROP_WEAPON:
        columns_spec = (
            f"A horizontal 3-panel orthographic model sheet of {subj}: "
            f"[Column 1 (0%-33%): Flat FRONT orthographic view of {subj}, perfectly vertical, centered, displaying full frontal reliefs, bevels, and filigree], "
            f"[Column 2 (33%-66%): SIDE cross-section profile view of the exact same {subj}, strictly facing LEFT, clearly showing volumetric thickness, blade edge bevels, guard depth, and hilt proportions], "
            f"[Column 3 (66%-100%): Flat BACK orthographic view of the exact same {subj}, showing matching reverse reliefs and rear crossguard symmetry]"
        )
        deocclusion_rules = (
            "MANDATORY GEOMETRIC INTEGRITY: "
            "sharp planar bevels, perfectly straight central axis, uniform cross-sectional thickness, "
            "clear air clearance around guards, handles, and hilts, zero warped or melted axes"
        )
    elif category == CATEGORY_VEHICLE:
        columns_spec = (
            f"A horizontal 3-panel orthographic model sheet of {subj}: "
            f"[Column 1 (0%-33%): FRONT orthographic view of {subj}, showing front grille, headlights, chassis width, and grounded wheels/tracks], "
            f"[Column 2 (33%-66%): SIDE profile orthographic view of the exact same {subj}, strictly facing LEFT, showing complete wheelbase, cabin silhouette, and roofline], "
            f"[Column 3 (66%-100%): REAR orthographic view of the exact same {subj}, showing rear bumper, exhausts, and rear aerodynamic profile]"
        )
        deocclusion_rules = (
            "MANDATORY MECHANICAL SEPARATION: "
            "all wheels/tracks clearly separated from wheel arches with visible negative space, "
            "undercarriage clearance cleanly defined, crisp hard-surface panel lines and planar bevels"
        )
    else:  # Generic object or fauna
        columns_spec = (
            f"A horizontal 3-panel turnaround model sheet of {subj}: "
            f"[Column 1 (0%-33%): FRONT orthographic view of {subj}, perfectly centered and upright], "
            f"[Column 2 (33%-66%): LEFT SIDE profile orthographic view of the exact same {subj}, strictly facing LEFT, showing complete side depth and volumetric contours], "
            f"[Column 3 (66%-100%): BACK orthographic view of the exact same {subj}, showing complete rear anatomy and symmetry]"
        )
        deocclusion_rules = (
            "MANDATORY 360-DEGREE SEPARATION: "
            "clean silhouette separation, distinct sculpted relief across all angles, "
            "unobstructed volume with visible air space around appendages or handles, zero flat relief melting"
        )

    separation_rules = (
        "3 distinct non-overlapping figures arranged horizontally in 3 separate columns "
        "with wide empty neutral margins between them, identical scale and height, "
        "no overlapping parts between columns, deeply sculpted 3D geometric surface relief, "
        "flat studio lighting, zero cast shadows"
    )

    technical_rules = (
        "pure solid uniform clean white background (#ffffff), omnidirectional shadowless studio softbox lighting, "
        "neutral albedo, razor-sharp silhouette separation, tangible physical 3D relief on all details "
        "for single-color monochrome 3D printing, watertight solid geometry"
    )

    return f"{columns_spec}. {deocclusion_rules}. {separation_rules}. {style_dir}{details_str}. {grounding_str}. {technical_rules}."


def compile_single_hero_prompt(
    subject: str,
    art_style: str = STYLE_FAITHFUL_ANATOMICAL,
    key_details: Optional[list] = None,
    add_pedestal_base: bool = False,
    humanoid_pose: str = HUMANOID_POSE_A
) -> str:
    """
    Compiles a Meshy-style single 3/4 hero view prompt with rich chromatic contrast,
    tailored to the detected subject category.
    """
    subj = clean_transparency_keywords(subject.strip())
    category = detect_subject_category(subj)

    explicit_style = detect_explicit_style_intent(subj)
    if explicit_style:
        art_style = explicit_style
    elif art_style == STYLE_STYLIZED_VINYL:
        art_style = STYLE_FAITHFUL_ANATOMICAL

    style_dir = get_style_directives(art_style)

    details_str = ""
    if key_details and len(key_details) > 0:
        details_str = f", key anatomical details: {', '.join(key_details)}"

    grounding_str = (
        "resting firmly on a solid flat circular matte grey display pedestal with bevelled rim flush with ground"
        if add_pedestal_base else
        "grounded naturally and solidly on the floor plane at Z=0 without any artificial pedestal disc"
    )

    pose_desc = f" in {get_humanoid_pose_directives(humanoid_pose)}" if category == CATEGORY_HUMANOID else ""

    hero_spec = (
        f"A pristine single three-quarter front hero view of {subj}{pose_desc} captured at an elevated 35-degree isometric angle. "
        f"Full subject centered in frame displaying the front, side profile, and clear volumetric depth extending toward the rear"
    )

    if category == CATEGORY_PROP_WEAPON:
        chromatic_separation = (
            "RICH CHROMATIC ALBEDO SEPARATION: distinct color values and metallic contrast between blade/head, guard, grip, "
            "and pommel accents. Crisp beveled cutting edges and clearly defined geometric volumes"
        )
    elif category == CATEGORY_VEHICLE:
        chromatic_separation = (
            "RICH CHROMATIC ALBEDO SEPARATION: distinct color contrast between bodywork, glass canopy, wheels/tracks, and chassis. "
            "Crisp hard-surface planar bevels and clear undercarriage negative space"
        )
    elif category == CATEGORY_HUMANOID:
        chromatic_separation = (
            "RICH CHROMATIC ALBEDO SEPARATION: distinct color values between skin, clothing layers, armor, and hair. "
            "Visible negative space between arms and torso and between legs, allowing vision encoders to cleanly differentiate depth layers"
        )
    else:
        chromatic_separation = (
            "RICH CHROMATIC ALBEDO SEPARATION: distinct, high-contrast color values and subtle tone variations between foreground features, "
            "background parts, and body torso so vision encoders cleanly differentiate depth layers. "
            "Visible negative space between distinct appendages"
        )

    technical_rules = (
        "pure solid uniform clean white background (#ffffff), omnidirectional shadowless studio softbox lighting, "
        "neutral albedo, razor-sharp silhouette separation, tangible physical 3D relief on all details "
        "for single-color monochrome 3D printing, watertight solid geometry, zero cast shadows"
    )

    return f"{hero_spec}. {chromatic_separation}. {style_dir}{details_str}. {grounding_str}. {technical_rules}."
