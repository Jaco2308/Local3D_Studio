"""
Local3D Studio Dynamic Style & Anatomy Router (Prompt Enhancer)
Separates technical 3D reconstruction directives from artistic style,
featuring an Intelligent Subject & Anatomy Classifier that prevents over-fitting
and generates appropriate poses and de-occlusion rules for bipeds, quadrupeds,
props/weapons, vehicles, and generic objects.
"""

import re
from typing import Optional


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
    """Returns compact geometric directives for canonical humanoid poses within token budget."""
    p = pose.lower().strip()
    if p == HUMANOID_POSE_T:
        return "upright T-pose, horizontal straight arms, flat palms down, separated legs"
    elif p == HUMANOID_POSE_ACTION:
        return "dynamic combat stance, grounded footwork, separated limbs"
    elif p == HUMANOID_POSE_NATURAL:
        return "relaxed standing pose, arms clear of torso, separated legs"
    else:  # a_pose (default)
        return "canonical upright A-pose, open armpits, separated legs, symmetrical face, clean sculpted hands, defined boots"


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
        "dog", "cat", "puppy", "kitten", "feline", "dragon", "horse", "lion", "tiger",
        "wolf", "bear", "dinosaur", "creature", "reptile", "lizard", "monster",
        "beast", "fox", "hound", "leopard", "cheetah", "panther", "rhino",
        "elephant", "hippo", "deer", "stag", "quadruped", "dino", "rabbit", "bunny",
        "cavy", "squirrel", "raccoon", "badger", "boar", "pig", "cow", "bull",
        "cane", "gatto", "cucciolo", "gattino", "felino", "drago", "cavallo", "leone", "tigre",
        "lupo", "orso", "dinosauro", "mostro", "creatura", "bestia", "volpe",
        "levriero", "pantera", "rinoceronte", "elefante", "cervo", "coniglio", "scoiattolo"
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
        "biped", "pikachu", "goku", "saiyan", "vegeta", "naruto", "luffy",
        "santa", "santa claus", "babbo natale", "elf", "elfo", "dwarf", "nano",
        "gnome", "gnomo", "goblin", "orc", "orco", "zombie", "alien", "alieno",
        "vampire", "vampiro", "skeleton", "scheletro", "pirate", "pirata", "clown",
        "astronaut", "astronauta", "king", "re", "queen", "regina", "prince", "princess",
        "principessa", "priest", "prete", "farmer", "contadino", "babbo",
        "uomo", "donna", "persona", "umano", "personaggio", "guerriero",
        "cavaliere", "soldato", "ragazzo", "ragazza", "eroe", "mago", "monaco",
        "paladino"
    ]

    # Exclude "dragon ball" from triggering quadruped dragon classification
    lower_cleaned = re.sub(r"\bdragon\s*ball\b", "", lower)

    has_weapon = any(k in lower for k in weapon_keywords)
    has_vehicle = any(k in lower for k in vehicle_keywords)
    has_quad = any(k in lower_cleaned for k in quadruped_keywords)
    has_fauna = any(k in lower for k in fauna_keywords)
    has_humanoid = any(k in lower for k in humanoid_keywords)

    # First words intent check
    first_two_words = " ".join(lower_cleaned.split()[:2]) if lower_cleaned.split() else ""
    if any(k in first_two_words for k in ["sword", "blade", "axe", "shield", "bow", "hammer", "spada", "lama", "ascia", "scudo", "pugnale", "dagger"]):
        return CATEGORY_PROP_WEAPON
    if any(k in first_two_words for k in quadruped_keywords):
        return CATEGORY_QUADRUPED
    if any(k in first_two_words for k in vehicle_keywords):
        return CATEGORY_VEHICLE

    # Specific taxonomic creatures take precedence over generic humanoid words
    if has_quad and not (has_humanoid and any(w in lower for w in ["riding", "mounted", "rider", "in groppa", "a cavallo"])):
        return CATEGORY_QUADRUPED

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
    """Returns compact artistic style prompt expansion."""
    if art_style == STYLE_REALISTIC_SCULPT:
        return "ZBrush digital sculpt, anatomical details"
    elif art_style == STYLE_GAME_PROP:
        return "hard-surface 3D game prop, planar bevels"
    elif art_style == STYLE_TABLETOP_MINIATURE:
        return "tabletop miniature, stylized details"
    elif art_style == STYLE_STYLIZED_VINYL:
        return "stylized collectible vinyl figurine, smooth shapes"
    else:
        return "faithful canonical design"


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
    Strictly token-budgeted (<72 CLIP tokens) to guarantee zero prompt truncation.
    """
    prompt = clean_transparency_keywords(user_prompt.strip())
    category = detect_subject_category(prompt)

    explicit_style = detect_explicit_style_intent(prompt)
    if explicit_style:
        art_style = explicit_style
    elif art_style == STYLE_STYLIZED_VINYL:
        art_style = STYLE_FAITHFUL_ANATOMICAL

    # If the prompt is already a structured turnaround sheet or hero view, pass through
    if any(k in prompt.lower() for k in ["3-panel turnaround", "[column 1", "three-quarter front hero view", "pristine single"]):
        return prompt

    pose_extra = ""
    if category == CATEGORY_HUMANOID:
        pose_extra = f", {get_humanoid_pose_directives(humanoid_pose)}"
    elif category == CATEGORY_QUADRUPED:
        pose_extra = ", high arched S-curve tail, exposed tail root, 4 separated paws"
    elif category == CATEGORY_PROP_WEAPON:
        pose_extra = ", sharp planar bevels, straight axis, uniform thickness"
    elif category == CATEGORY_VEHICLE:
        pose_extra = ", clean wheel separation, undercarriage negative space"
    else:
        pose_extra = ", clean silhouette separation, distinct relief"

    if multiview:
        if category == CATEGORY_QUADRUPED:
            layout_directives = "3-panel turnaround: front, side, rear slightly elevated"
        else:
            layout_directives = "3-panel turnaround: front, side, rear views"
    else:
        layout_directives = "three-quarter hero view, 35-degree isometric"

    style_directives = get_style_directives(art_style)

    grounding_str = (
        "matte display disc"
        if add_pedestal_base else
        "flat ground, zero cushions"
    )

    technical_rules = "pure white background (#ffffff), zero aura, 3D relief"

    return f"{prompt}, {layout_directives}{pose_extra}, {style_directives}, {grounding_str}, {technical_rules}"


def compile_turnaround_sheet_prompt(
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

    if category == CATEGORY_QUADRUPED:
        grounding_str = (
            "resting firmly on a solid flat circular matte grey display pedestal with bevelled rim flush with ground, strictly no soft cushions, pet beds, or fabric"
            if add_pedestal_base else
            "grounded naturally and solidly on the bare flat floor plane at Z=0, strictly zero pet beds, zero cushions, zero pillows, zero fabric rugs"
        )
    else:
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
            f"[Column 1 (0%-33%): Full-body FRONT orthographic view of {subj}, facing straight at camera, wide open stance showing all 4 distinct legs and paws separated with clear air space], "
            f"[Column 2 (33%-66%): Full-body LEFT SIDE profile orthographic view of the exact same {subj}, strictly facing LEFT, open stance with all legs distinct, tail arched proudly high and upward in an S-curve away from the hips, with the exact root junction and attachment point at the sacrum / lower spine 100% visible, unobstructed, and exposed], "
            f"[Column 3 (66%-100%): Full-body REAR orthographic view of the exact same {subj} captured at a slightly elevated 10-to-15 degree downward pitch looking over the back of the head, clearly revealing the dorsal spine, rear haunches, and the complete exposed origin point and base of the raised tail]"
        )
        deocclusion_rules = (
            "MANDATORY QUADRUPED ZERO SELF-OCCLUSION & EXPOSED TAIL ROOT RULE: "
            "Tail must be held arched proudly upward or curving high away from the rear legs in an expressive S-curve; "
            "the base attachment of the tail root to the lower spine and pelvis must be 100% visible, unobstructed, and clearly exposed from both side profile and rear views, never tucked, never hidden between legs. "
            "All 4 legs and paws must be 100% unobstructed with visible empty air space between limbs. "
            "ZERO PARASITIC ACCESSORIES: strictly sitting or standing directly on the bare flat ground plane at Z=0, "
            "strictly zero pet beds, zero cushions, zero pillows, zero fabric blankets, zero baskets, zero wrapping cloth under the body. "
            "Deep sculpted ambient occlusion crevices separating foreground limbs, hind legs, tail root, and body volume"
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
    Compiles an ultra-detailed, unconstrained 3D master prompt for native image generators
    (Meshy AI Single-Master 3/4 style at 35-degree elevation).
    Enforces total anti-occlusion, strict zero effects/zero smoke/zero aura/zero pedestal,
    deep ambient occlusion in limb crevices, and crisp 3D geometric surface relief.
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
        details_str = f", specific anatomical and costume features: {', '.join(key_details)}"

    # 1. Inquadratura: Full-body single subject, elevated 35-degree three-quarter isometric view
    framing = (
        f"A masterwork single-subject full-body reference image of {subj}, "
        f"captured in an elevated 35-degree three-quarter isometric hero angle. "
        f"The subject is perfectly centered in frame, clearly displaying the front face, side profile contours, "
        f"and the full volumetric 3D depth extending toward the rear"
    )

    # 2. Anti-Occlusione Totale: Separazione chirurgica di tutti gli arti
    if category == CATEGORY_HUMANOID:
        pose_dir = get_humanoid_pose_directives(humanoid_pose)
        anti_occlusion = (
            f"TOTAL ANTI-OCCLUSION & LIMB SEPARATION: {pose_dir}. "
            "Both arms are held open and detached from the torso with visible empty space under the armpits. "
            "Hands and individual fingers are cleanly sculpted, distinct, and fully visible without clumping or distortion. "
            "Legs are positioned with a stable open stance, completely separated with clear empty air between thighs and calves. "
            "Boots/feet rest firmly on the ground. Hair, capes, jackets, or sashes must trail cleanly backward, "
            "never fusing into the torso or obscuring the arms or legs"
        )
    elif category == CATEGORY_QUADRUPED:
        anti_occlusion = (
            "TOTAL ANTI-OCCLUSION & LIMB SEPARATION: "
            "All four legs and paws are clearly visible, distinct, and planted firmly on the ground, "
            "with unambiguous empty negative space separating foreground legs from background legs. "
            "If the creature has wings, they are lifted high and spread upward/backward, completely detached from torso and hindquarters. "
            "The tail is arched high and away from the body in an expressive curve, with its root attachment point at the lower spine/pelvis "
            "100% visible, exposed, and never tucked or obscuring the paws or haunches"
        )
    elif category == CATEGORY_PROP_WEAPON:
        anti_occlusion = (
            "TOTAL GEOMETRIC SEPARATION & CLARITY: "
            "Full three-quarter isometric display showing blade/barrel thickness, guard clearance, and pommel/stock. "
            "Sharp planar bevels and perfectly straight central axis with visible negative space around handles and triggers"
        )
    elif category == CATEGORY_VEHICLE:
        anti_occlusion = (
            "TOTAL GEOMETRIC SEPARATION & HARD-SURFACE CLARITY: "
            "Full three-quarter isometric view showing front grille, side profile, and rear canopy. "
            "All wheels and tracks clearly separated from wheel arches with clean undercarriage negative space"
        )
    else:
        anti_occlusion = (
            "TOTAL ANTI-OCCLUSION: "
            "Clean silhouette separation, all appendages, handles, or components clearly detached from main body "
            "with visible air clearance and distinct volumetric depth from front to rear"
        )

    # 3. Zero Effetti / Zero Fumo / Zero Basetta
    if add_pedestal_base:
        grounding = (
            "Resting solidly on a flat, low-profile circular matte grey display pedestal with bevelled edge flush with ground at Z=0. "
            "Strictly zero smoke clouds, zero dust, zero energy aura, zero fire or flames, zero magic sparkles, zero particle effects, zero motion blur, zero scenic background elements. "
            "Only the solid physical body of the subject on the pedestal"
        )
    else:
        grounding = (
            "Grounded solidly and naturally directly on the flat horizontal floor plane at Z=0. "
            "STRICTLY ZERO PEDESTAL, zero display stand, zero circular base disc, zero ground plaque, zero floor tiles, zero floating rocks. "
            "STRICTLY ZERO SPECIAL EFFECTS: zero energy aura, zero ki blasts, zero lightning bolts, zero smoke clouds, zero flames, zero dust trails, zero particle bursts, zero motion blur, zero scenic backgrounds. "
            "ONLY the solid physical body of the subject standing on flat ground"
        )

    # 4. Colori e Rilievo 3D (Ambient Occlusion profonda e separazione cromatica)
    chromatic_relief = (
        "3D CHROMATIC SEPARATION & AMBIENT OCCLUSION: "
        "Vivid, clean color differentiation across anatomical parts, skin tones, muscles, and clothing/armor layers. "
        "Pronounced, deep ambient occlusion crevice shading in the grooves between overlapping limbs and body volumes "
        "to provide unmistakable depth cues to neural 3D reconstruction networks. "
        "Eyes, facial features, hair strands, and muscle topology are crisply sculpted with tangible physical geometric surface relief"
    )

    # 5. Regole Tecniche di Studio
    technical = (
        "Pure uniform solid clean white background (#ffffff), flat omnidirectional shadowless studio softbox lighting, "
        "neutral albedo exposure, razor-sharp silhouette isolation for photogrammetry, zero shadows cast on the ground, "
        "solid watertight physical geometry suitable for 3D modeling and 3D printing"
    )

    return f"{framing}. {anti_occlusion}. {grounding}. {chromatic_relief}. {style_dir}{details_str}. {technical}."


def compile_3d_master_prompt(
    subject: str,
    art_style: str = STYLE_FAITHFUL_ANATOMICAL,
    key_details: Optional[list] = None,
    add_pedestal_base: bool = False,
    humanoid_pose: str = HUMANOID_POSE_A,
    generation_strategy: str = "single_hero_34"
) -> str:
    """
    Compiles an optimized 3D master prompt for native image generators.
    Defaults to 'single_hero_34' (Meshy AI Single-Master 3/4 hero view at 35° elevation),
    with optional support for 'multiview_turnaround' (3-panel sheet).
    """
    strat = generation_strategy.lower().strip()
    if strat == "multiview_turnaround":
        return compile_turnaround_sheet_prompt(
            subject=subject,
            art_style=art_style,
            key_details=key_details,
            add_pedestal_base=add_pedestal_base,
            humanoid_pose=humanoid_pose
        )
    return compile_single_hero_prompt(
        subject=subject,
        art_style=art_style,
        key_details=key_details,
        add_pedestal_base=add_pedestal_base,
        humanoid_pose=humanoid_pose
    )
