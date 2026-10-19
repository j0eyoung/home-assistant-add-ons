"""Mind & Body: yoga poses, Baduanjin qigong and cool-down picks, as cards in the same shape as the
exercise library (api.library_card). Written for Joe's constraints: left kidney pyeloplasty adhesions
(no deep twists, deep backbends, compression or inversion-type loading in automatic picks) and a
hypertonic pelvic floor (nothing that makes him grip or bear down; long slow exhales).
General wellness guidance, not medical advice. Pictures: Yoga Posture Dataset on Kaggle by Mrinal Tyagi, CC0."""
import datetime
import os
import random

import library

PHOTO_SOURCE = "Yoga Posture Dataset (Kaggle, CC0)"

# slug -> pictures on the media server (workout/yoga/<slug>-<n>.jpg)
PHOTOS = {
    "adho-mukha-svanasana": 5, "adho-mukha-vrksasana": 5, "alanasana": 5, "anjaneyasana": 5, "ardha-chandrasana": 5,
    "ardha-matsyendrasana": 5, "ardha-navasana": 3, "ardha-pincha-mayurasana": 5, "ashta-chandrasana": 2,
    "baddha-konasana": 5, "bakasana": 5, "balasana": 5, "bitilasana": 5, "camatkarasana": 5, "dhanurasana": 5,
    "eka-pada-rajakapotasana": 5, "garudasana": 2, "halasana": 5, "hanumanasana": 5, "malasana": 5,
    "marjaryasana": 5, "navasana": 5, "padmasana": 5, "parsva-virabhadrasana": 4, "parsvottanasana": 5,
    "paschimottanasana": 5, "phalakasana": 5, "pincha-mayurasana": 5, "salamba-bhujangasana": 5,
    "salamba-sarvangasana": 5, "setu-bandha-sarvangasana": 5, "sivasana": 1, "supta-kapotasana": 3,
    "trikonasana": 4, "upavistha-konasana": 0, "urdhva-dhanurasana": 5, "urdhva-mukha-svsnssana": 5,
    "ustrasana": 5, "utkatasana": 5, "uttanasana": 5, "utthita-hasta-padangusthasana": 5,
    "utthita-parsvakonasana": 5, "vasisthasana": 5, "virabhadrasana-one": 5, "virabhadrasana-three": 5,
    "virabhadrasana-two": 5, "vrksasana": 4,
}

BREATH = "Breathe slowly through the nose; make each exhale longer than the inhale and keep your belly and pelvic floor soft."

# Why a pose is left out of automatic picks (shown as the warning on its card).
_WHY = {
    "twist": "Deep twist: twisting compresses the kidney area, so it stays out of your automatic picks.",
    "backbend": "Deep backbend: arching loads the flank and kidney area, so it stays out of your automatic picks.",
    "inversion": "Inversion or heavy shoulder and neck loading: skipped in your automatic picks while the kidney adhesions are healing.",
    "core": "Hard core or hip-flexor clamp: it makes the pelvic floor grip, so it stays out of your automatic picks.",
    "extreme": "Extreme stretch for the hips and pelvic floor: skipped in your automatic picks.",
}


def P(slug, sanskrit, english, cat, level, steps, tip, *, cool=False, caution=None, unsafe=None, muscles=(), dose="30-60 sec"):
    return {"slug": slug, "sanskrit": sanskrit, "english": english, "cat": cat, "level": level, "steps": steps,
            "tip": tip, "cool": cool, "caution": caution, "unsafe": unsafe, "muscles": list(muscles), "dose": dose}


YOGA = [
    P("balasana", "Balasana", "Child's pose", "restorative", "beginner",
      ["Kneel and sit back toward your heels, knees hip-width apart.", "Fold forward and rest your forehead on the floor or a pillow.",
       "Arms long in front or resting by your feet.", "Breathe into your back ribs."],
      "Put a cushion under your hips or forehead if anything feels pinched.", cool=True, muscles=["lower back", "hips"]),
    P("sivasana", "Savasana", "Final rest", "restorative", "beginner",
      ["Lie on your back, legs a little apart, arms by your sides palms up.", "Let your feet fall open and let your jaw and belly go soft.",
       "Breathe normally and rest for 2-5 minutes."],
      "A pillow under your knees takes the load off your lower back.", cool=True, dose="2-5 min", muscles=["whole body"]),
    P("marjaryasana", "Marjaryasana", "Cat pose", "spine", "beginner",
      ["On hands and knees, wrists under shoulders, knees under hips.", "Exhale and round your back toward the ceiling, chin toward your chest.",
       "Keep it small and slow; this is a gentle spine wave."],
      "Pair with cow pose and move with your breath.", cool=True, dose="8-10 slow rounds", muscles=["spine", "core"]),
    P("bitilasana", "Bitilasana", "Cow pose", "spine", "beginner",
      ["On hands and knees, wrists under shoulders, knees under hips.", "Inhale and let your belly drop slightly while you lift your chest and tailbone gently.",
       "Keep the arch small and your neck long."],
      "Stay well short of a deep arch; this is a soft movement.", cool=True, caution="Keep the arch small and gentle to protect the kidney area.",
      dose="8-10 slow rounds", muscles=["spine"]),
    P("uttanasana", "Uttanasana", "Standing forward fold", "forward fold", "beginner",
      ["Stand with feet hip-width apart and bend your knees generously.", "Hinge from the hips and let your upper body hang.",
       "Hold your elbows or rest hands on shins or a block.", "Roll up slowly, head last."],
      "Bend your knees as much as you like; only fold as far as is comfortable.", cool=True, caution="Fold only as far as is comfortable and come up slowly.",
      muscles=["hamstrings", "lower back"]),
    P("paschimottanasana", "Paschimottanasana", "Seated forward fold", "forward fold", "beginner",
      ["Sit with legs straight in front, a folded blanket under your hips.", "Sit tall, then hinge forward from the hips.",
       "Rest your hands on your legs, wherever they reach.", "Keep your back long, not forced down."],
      "Bend your knees or loop a strap around your feet. Go only as far as is comfortable.", cool=True,
      caution="Fold only as far as is comfortable; never pull yourself down.", muscles=["hamstrings", "lower back"]),
    P("baddha-konasana", "Baddha Konasana", "Bound angle pose", "hips", "beginner",
      ["Sit with the soles of your feet together and knees falling out.", "Sit on a folded blanket so your hips are above your knees.",
       "Hold your ankles and sit tall.", "Let your knees drop; do not push them down."],
      "Rest your knees on cushions so your hips and pelvic floor can soften.", cool=True,
      caution="Let your hips soften; do not push your knees down.", muscles=["inner thighs", "hips"]),
    P("malasana", "Malasana", "Garland pose (supported squat)", "hips", "beginner",
      ["Stand with feet wider than hips, toes turned out.", "Lower into a squat, heels down or on a rolled towel.",
       "Press your elbows gently into your knees, palms together.", "Sit on a block if you like."],
      "Sit on a block or hold a doorframe so you can relax your pelvic floor rather than grip.", cool=True,
      caution="Support your hips so your pelvic floor can relax.", muscles=["hips", "glutes"]),
    P("adho-mukha-svanasana", "Adho Mukha Svanasana", "Downward-facing dog", "strength", "beginner",
      ["Start on hands and knees, tuck your toes and lift your hips up and back.", "Keep your knees soft and your back long.",
       "Press your hands into the floor and relax your head and neck.", "Lower with a long exhale."],
      "Bend your knees as much as you need; the goal is a long back, not straight legs.", cool=True,
      caution="Keep a long back and soft knees; skip it on days your head feels pressured.", muscles=["shoulders", "hamstrings", "calves"]),
    P("phalakasana", "Phalakasana", "Plank pose", "strength", "intermediate",
      ["From hands and knees, step your feet back into a straight line.", "Stack shoulders over wrists, keep your belly gently engaged.",
       "Breathe steadily; do not clench your pelvic floor.", "Drop your knees to rest."],
      "Hold on your knees or against a wall to keep it easy.", caution="Skip it on days your pelvic floor feels tight.",
      dose="15-30 sec", muscles=["core", "shoulders"]),
    P("salamba-bhujangasana", "Salamba Bhujangasana", "Sphinx pose", "gentle backbend", "beginner",
      ["Lie on your belly, forearms on the floor with elbows under shoulders.", "Lift your chest softly, keeping your hips pressed down.",
       "Keep your neck long and your lower back relaxed.", "Lower slowly."],
      "Small lift only. Stop if your left flank feels any pinching.", caution="Keep the lift small and stop if your kidney area feels pinched.",
      muscles=["spine", "chest"]),
    P("vrksasana", "Vrksasana", "Tree pose", "balance", "beginner",
      ["Stand tall and shift your weight onto one foot.", "Place the other foot on your calf or inner thigh, never on the knee.",
       "Hands at your chest or overhead.", "Fix your eyes on a still spot; switch sides."],
      "Keep your toes on the floor with your heel against your ankle for a lower version.", dose="20-30 sec each side",
      muscles=["legs", "balance"]),
    P("utkatasana", "Utkatasana", "Chair pose", "strength", "beginner",
      ["Stand with feet hip-width apart and bend your knees as if sitting on a chair.", "Reach your arms forward or overhead.",
       "Keep your weight in your heels and your ribs down."],
      "Sit back only as far as is comfortable; keep it shallow.", caution="Keep it shallow; don't bear down.", dose="15-30 sec",
      muscles=["quads", "glutes"]),
    P("anjaneyasana", "Anjaneyasana", "Low lunge", "hips", "beginner",
      ["From hands and knees, step one foot forward between your hands.", "Lower your back knee onto a cushion.",
       "Slide your hips forward slightly, hands on your front thigh.", "Keep your chest tall; switch sides."],
      "Stay low and keep the lift in your chest small; no deep arch.", cool=True, caution="Keep your chest tall and don't arch back.",
      dose="30-45 sec each side", muscles=["hip flexors"]),
    P("alanasana", "Alanasana", "High crescent lunge", "strength", "intermediate",
      ["Step one foot forward into a lunge and lift your torso.", "Reach your arms overhead, ribs down.", "Keep your front knee over your ankle.",
       "Switch sides."],
      "Keep your hands on your hips if raising your arms feels like too much.", caution="Keep your ribs down; no deep arch.",
      dose="20-30 sec each side", muscles=["legs", "hip flexors"]),
    P("ashta-chandrasana", "Ashta Chandrasana", "High lunge, arms overhead", "strength", "intermediate",
      ["Step into a lunge with your back heel lifted.", "Reach your arms up beside your ears.", "Keep your hips square and your ribs down."],
      "Rest your hands on your front thigh for a simpler version.", caution="Keep your ribs down; no deep arch.", dose="20-30 sec each side",
      muscles=["legs"]),
    P("virabhadrasana-one", "Virabhadrasana I", "Warrior I", "strength", "intermediate",
      ["Step one foot back, back foot turned out slightly.", "Bend your front knee over your ankle, hips facing forward.", "Raise your arms and lift your chest.",
       "Switch sides."],
      "Keep your stance short and your hips square; no arch.", caution="Keep your hips square; do not arch back or twist.",
      dose="20-30 sec each side", muscles=["legs", "hips"]),
    P("virabhadrasana-two", "Virabhadrasana II", "Warrior II", "strength", "beginner",
      ["Step your feet wide, front toes forward and back foot turned in slightly.", "Bend your front knee over your ankle.",
       "Reach your arms out to the sides at shoulder height.", "Keep your torso upright; look over the front hand."],
      "Keep the stance short and your torso over your hips (no leaning).", caution="Keep your torso upright; no leaning into the side.",
      dose="20-30 sec each side", muscles=["legs", "hips"]),
    P("virabhadrasana-three", "Virabhadrasana III", "Warrior III", "balance", "intermediate",
      ["Stand on one leg, hinge forward and lift the back leg.", "Keep your hips level and arms by your sides.", "Hold with a slight bend in the standing knee."],
      "Practice with your hands on a chair.", caution="Keep your hips square and level; don't rotate.", dose="10-20 sec each side",
      muscles=["hamstrings", "glutes", "balance"]),
    P("parsvottanasana", "Parsvottanasana", "Pyramid pose", "forward fold", "intermediate",
      ["Step one foot back, both feet facing forward, hips square.", "Hinge forward from the hips over your front leg.", "Rest your hands on blocks or your shin.", "Switch sides."],
      "Keep your hips square and fold only as far as is comfortable.", caution="Keep your hips square and fold only as far as is comfortable.",
      dose="20-30 sec each side", muscles=["hamstrings"]),
    P("trikonasana", "Utthita Trikonasana", "Triangle pose", "standing", "intermediate",
      ["Stand with feet wide, front toes forward.", "Reach long over your front leg, then rest your hand on your shin or a block.", "Keep your chest open and your top arm up.",
       "Return slowly; switch sides."],
      "Rest your hand high on your leg. Don't twist your chest toward the ceiling.", caution="Side-bending loads the flank: keep it short, especially on your left.",
      dose="20-30 sec each side", muscles=["hamstrings", "sides of waist"]),
    P("utthita-parsvakonasana", "Utthita Parsvakonasana", "Extended side angle", "standing", "intermediate",
      ["Step wide, bend your front knee and rest your forearm on your thigh.", "Reach your top arm over your head.", "Keep your chest open without twisting."],
      "Keep your forearm on your thigh, not the floor.", caution="Side-bending and rotation load the flank; keep it small, especially on your left.",
      dose="20-30 sec each side", muscles=["legs", "sides of waist"]),
    P("parsva-virabhadrasana", "Parsva Virabhadrasana", "Reverse warrior", "standing", "intermediate",
      ["From Warrior II, flip your front palm up and reach your back arm over.", "Rest the back hand on your back leg.", "Keep your chest open."],
      "Keep the side bend small.", caution="Side-bending loads the flank; keep it small, especially on your left.", dose="15-20 sec each side",
      muscles=["sides of waist", "legs"]),
    P("ardha-chandrasana", "Ardha Chandrasana", "Half moon", "balance", "intermediate",
      ["From a lunge, rest your hand on a block and lift the back leg.", "Stack your hips and open your chest.", "Reach your top arm up."],
      "Practice at a wall for balance.", caution="Rotating and side-bending load the flank; use a wall and keep it small.", dose="10-20 sec each side",
      muscles=["legs", "balance"]),
    P("utthita-hasta-padangusthasana", "Utthita Hasta Padangusthasana", "Standing hand-to-big-toe", "balance", "advanced",
      ["Stand tall and lift one knee, holding it with your hand.", "Extend the leg forward if you can, holding your big toe or a strap.", "Keep your hips square."],
      "Hold your knee or use a strap and stay near a wall.", caution="Keep your hips square; don't pull the leg across your body.",
      dose="15-20 sec each side", muscles=["hamstrings", "balance"]),
    P("garudasana", "Garudasana", "Eagle pose", "balance", "intermediate",
      ["Bend your knees and cross one thigh over the other.", "Cross your arms with elbows stacked.", "Sink your hips slightly and lift your elbows."],
      "Keep your toes on the floor for a lower version.", caution="The wrapped shape can twist the trunk: keep it shallow.", dose="15-20 sec each side",
      muscles=["hips", "shoulders", "balance"]),
    P("vasisthasana", "Vasisthasana", "Side plank", "strength", "advanced",
      ["From plank, roll onto the outside of one foot and lift your top arm.", "Stack your hips and keep your body in a line.", "Lower your bottom knee to ease it."],
      "Drop the bottom knee or lean on a wall.", caution="Side loading on the left flank: keep it short and on your knees.",
      dose="10-20 sec each side", unsafe="core", muscles=["core", "shoulders"]),
    P("setu-bandha-sarvangasana", "Setu Bandha Sarvangasana", "Bridge pose", "gentle backbend", "beginner",
      ["Lie on your back, knees bent and feet hip-width apart.", "Press your feet down and lift your hips a few inches.", "Keep your thighs parallel, then lower slowly."],
      "Stay low, or rest your hips on a block.", caution="Stay low (a few inches) to protect the kidney area.", dose="5 slow lifts",
      muscles=["glutes", "hamstrings"]),
    P("upavistha-konasana", "Upavistha Konasana", "Wide-angle seated forward fold", "hips", "intermediate",
      ["Sit with your legs wide, toes pointing up.", "Sit on a folded blanket and hinge forward from your hips.", "Rest your hands in front of you."],
      "Bend your knees slightly and lean on cushions.", caution="Fold only as far as is comfortable.", muscles=["inner thighs", "hamstrings"]),
    P("padmasana", "Padmasana", "Lotus pose (easy seat)", "seated", "intermediate",
      ["Sit tall on a cushion with your legs crossed.", "Rest your hands on your knees.", "Keep your spine long and your shoulders loose."],
      "Use an easy cross-legged seat; full lotus isn't needed.", caution="Use an easy cross-legged seat; skip full lotus if your knees complain.",
      dose="1-5 min", muscles=["hips"]),

    # Left out of automatic picks for Joe's kidney and pelvic floor.
    P("ardha-matsyendrasana", "Ardha Matsyendrasana", "Seated spinal twist", "twist", "intermediate",
      ["Sit tall with your legs crossed or extended.", "Place a hand behind you and turn gently.", "Look over your shoulder."],
      "Turn your head only, keeping hips square.", unsafe="twist", dose="20-30 sec each side", muscles=["spine"]),
    P("dhanurasana", "Dhanurasana", "Bow pose", "backbend", "intermediate",
      ["Lie on your belly and hold your ankles.", "Lift your chest and thighs.", "Breathe and lower."], "A deep backbend.",
      unsafe="backbend", dose="15-20 sec", muscles=["spine"]),
    P("urdhva-dhanurasana", "Urdhva Dhanurasana", "Wheel pose", "backbend", "advanced",
      ["Lie on your back with hands by your ears.", "Press into hands and feet and lift into an arch."], "A deep backbend.",
      unsafe="backbend", dose="10 sec", muscles=["spine"]),
    P("ustrasana", "Ustrasana", "Camel pose", "backbend", "intermediate",
      ["Kneel, hands on your hips.", "Lift your chest and arch back.", "Reach for your heels if comfortable."], "A deep backbend.",
      unsafe="backbend", dose="15-20 sec", muscles=["spine"]),
    P("urdhva-mukha-svsnssana", "Urdhva Mukha Svanasana", "Upward-facing dog", "backbend", "intermediate",
      ["Lie on your belly with hands by your ribs.", "Press up with straight arms and lift your thighs.", "Lower."], "A strong backbend: use sphinx instead.",
      unsafe="backbend", dose="10-15 sec", muscles=["spine", "chest"]),
    P("camatkarasana", "Camatkarasana", "Wild thing", "backbend", "advanced",
      ["From downward dog, lift one leg and arch back into a flip.", "Reach your free arm overhead."], "A deep backbend with a twist.",
      unsafe="backbend", dose="10 sec each side", muscles=["spine", "hips"]),
    P("eka-pada-rajakapotasana", "Eka Pada Rajakapotasana", "Pigeon pose", "hips", "intermediate",
      ["From plank, bring one knee forward and place your shin on the floor.", "Extend your other leg behind you.", "Fold forward over your front leg."],
      "Try a reclined figure-four stretch on your back instead.", unsafe="extreme", dose="30-60 sec each side", muscles=["hips"]),
    P("supta-kapotasana", "Supta Kapotasana", "Sleeping pigeon", "backbend", "advanced",
      ["From pigeon, lean back and lift your chest.", "Reach your hands toward your back foot."], "A deep backbend.", unsafe="backbend",
      dose="10 sec each side", muscles=["spine", "hips"]),
    P("halasana", "Halasana", "Plow pose", "inversion", "intermediate",
      ["Lie on your back and lift your legs overhead.", "Lower your toes toward the floor behind you."], "Skip; try legs up the wall instead.",
      unsafe="inversion", dose="20-30 sec", muscles=["spine", "hamstrings"]),
    P("salamba-sarvangasana", "Salamba Sarvangasana", "Shoulder stand", "inversion", "intermediate",
      ["Lie on your back and lift your legs overhead.", "Support your back with your hands.", "Lift into a vertical line."], "Skip; try legs up the wall instead.",
      unsafe="inversion", dose="20-30 sec", muscles=["shoulders"]),
    P("adho-mukha-vrksasana", "Adho Mukha Vrksasana", "Handstand", "inversion", "advanced",
      ["Kick up into a handstand against a wall."], "Skip.", unsafe="inversion", dose="10 sec", muscles=["shoulders"]),
    P("pincha-mayurasana", "Pincha Mayurasana", "Forearm stand", "inversion", "advanced",
      ["Kick up onto your forearms against a wall."], "Skip.", unsafe="inversion", dose="10 sec", muscles=["shoulders"]),
    P("ardha-pincha-mayurasana", "Ardha Pincha Mayurasana", "Dolphin pose", "inversion", "intermediate",
      ["From forearms and knees, lift your hips like downward dog on forearms."], "Use downward dog on your hands instead.",
      unsafe="inversion", dose="15-20 sec", muscles=["shoulders"]),
    P("bakasana", "Bakasana", "Crow pose", "core", "advanced",
      ["Squat and rest your knees on your upper arms.", "Lean forward and lift your feet."], "Skip.", unsafe="core", dose="10 sec", muscles=["core", "arms"]),
    P("navasana", "Navasana", "Boat pose", "core", "intermediate",
      ["Sit and lean back, lifting your feet and shins."], "Skip; try a gentle dead bug on your back instead.", unsafe="core", dose="10-20 sec", muscles=["core"]),
    P("ardha-navasana", "Ardha Navasana", "Half boat", "core", "intermediate",
      ["Sit and lean back slightly, lifting your feet."], "Skip.", unsafe="core", dose="10-20 sec", muscles=["core"]),
    P("hanumanasana", "Hanumanasana", "Splits", "hips", "advanced",
      ["From a lunge, slide your front leg forward and back leg back."], "Skip.", unsafe="extreme", dose="20 sec each side", muscles=["hamstrings", "hip flexors"]),
]


# Text-only additions (no photos): gentle floor work, supports and breathing, plus common poses without pictures.
YOGA += [
    P("viparita-karani", "Viparita Karani", "Legs up the wall", "restorative", "beginner",
      ["Sit sideways next to a wall, then swing your legs up as you lie back.", "Scoot your hips close to the wall, or a few inches away if your hamstrings are tight.",
       "Arms relaxed by your sides, palms up.", "Rest for 3-10 minutes, then bend your knees and roll to the side to come out."],
      "Put a folded blanket under your hips if you like. Stay calm and don't push into the stretch.", cool=True, dose="3-10 min",
      caution="Skip it if your legs tingle or your kidney area feels uncomfortable lying this way.", muscles=["legs", "lower back"]),
    P("supta-baddha-konasana", "Supta Baddha Konasana", "Reclined bound angle", "restorative", "beginner",
      ["Lie on your back with the soles of your feet together and knees falling open.", "Support each knee with a cushion or block.",
       "Rest your hands on your belly and let your hips and pelvic floor soften.", "Stay for 2-5 minutes."],
      "Use enough support under your knees that you feel nothing pulling.", cool=True, dose="2-5 min", muscles=["inner thighs", "hips", "pelvic floor"]),
    P("apanasana", "Apanasana", "Knees to chest", "restorative", "beginner",
      ["Lie on your back and draw both knees gently toward your chest.", "Hold your shins or knees, keeping your shoulders on the floor.",
       "Rock slightly side to side if it feels good (small)."],
      "Keep the pull gentle; don't force your knees in.", cool=True, dose="30-60 sec", muscles=["lower back", "hips"]),
    P("ananda-balasana", "Ananda Balasana", "Happy baby", "restorative", "beginner",
      ["Lie on your back and bring your knees toward your armpits.", "Hold your shins, ankles or the backs of your thighs.",
       "Let your knees fall wide and relax your pelvic floor.", "Rock gently if it feels good."],
      "Hold behind your thighs if reaching your feet strains your neck or back.", cool=True, dose="30-60 sec",
      caution="Keep your belly soft; don't pull your legs hard.", muscles=["hips", "inner thighs"]),
    P("constructive-rest", "Constructive rest", "Constructive rest pose", "restorative", "beginner",
      ["Lie on your back with your knees bent and feet flat, hip-width apart.", "Let your knees lean in toward each other or rest them together.",
       "Rest your hands on your belly and let your breath settle.", "Stay for 2-5 minutes."],
      "A good reset for your back and pelvic floor.", cool=True, dose="2-5 min", muscles=["lower back", "pelvic floor"]),
    P("supta-padangusthasana", "Supta Padangusthasana", "Reclined hand-to-toe (with strap)", "forward fold", "beginner",
      ["Lie on your back and loop a strap around one foot.", "Straighten that leg up toward the ceiling, the other leg bent or straight on the floor.",
       "Keep your hips level and your shoulders down.", "Switch sides."],
      "Bend the raised knee as much as you need.", cool=True, dose="30-45 sec each side", caution="Keep your hips level; don't let the leg pull across your body.",
      muscles=["hamstrings"]),
    P("reclined-figure-four", "Supta Kapotasana (reclined)", "Reclined figure four", "hips", "beginner",
      ["Lie on your back, knees bent.", "Cross one ankle over the opposite thigh.", "Hold behind the lower thigh and draw it gently toward you.", "Switch sides."],
      "Go slowly; stop at a mild stretch in your outer hip.", cool=True, dose="30-45 sec each side", muscles=["hips", "glutes"]),
    P("tadasana", "Tadasana", "Mountain pose", "standing", "beginner",
      ["Stand with feet hip-width apart, weight even on both feet.", "Let your arms hang by your sides.", "Lengthen through the crown of your head and soften your knees.",
       "Breathe low into your belly."],
      "A quiet reset between poses.", dose="30-60 sec", muscles=["posture"]),
    P("urdhva-hastasana", "Urdhva Hastasana", "Mountain with arms up", "standing", "beginner",
      ["Stand in Tadasana and sweep your arms up overhead.", "Keep your ribs down and your belly soft.", "Lower slowly on the exhale."],
      "Don't lean back; keep it a gentle lift.", caution="Keep your ribs down; don't arch your lower back.", dose="5 slow breaths", muscles=["shoulders", "sides"]),
    P("ardha-uttanasana", "Ardha Uttanasana", "Half forward fold", "forward fold", "beginner",
      ["From a forward fold, rest your hands on your shins or thighs.", "Lengthen your spine so your back is flat.", "Look at the floor a few feet ahead."],
      "Bend your knees generously.", cool=True, dose="5 breaths", caution="Keep your back flat; don't arch.", muscles=["hamstrings", "back"]),
    P("prasarita-padottanasana", "Prasarita Padottanasana", "Wide-leg forward fold", "forward fold", "intermediate",
      ["Step your feet wide, toes slightly in.", "Hinge forward from the hips with your hands on blocks.", "Let your head and neck relax."],
      "Keep your hands high on blocks; fold only as far as is comfortable.", caution="Fold only as far as is comfortable; come up slowly.",
      dose="30-45 sec", muscles=["hamstrings", "inner thighs"]),
    P("janu-sirsasana", "Janu Sirsasana", "Head-to-knee forward fold", "forward fold", "beginner",
      ["Sit with one leg straight and the other foot against your inner thigh.", "Hinge forward over the straight leg.", "Rest your hands wherever they land."],
      "Sit on a blanket and keep your hips square.", cool=True, dose="30-45 sec each side", caution="Keep your hips square; fold only as far as is comfortable.",
      muscles=["hamstrings"]),
    P("sukhasana", "Sukhasana", "Easy seat", "seated", "beginner",
      ["Sit on a cushion with your legs loosely crossed.", "Rest your hands on your knees.", "Lengthen your spine and soften your shoulders."],
      "Raise your hips until your knees are below them.", cool=True, dose="1-5 min", muscles=["hips"]),
    P("virasana", "Virasana", "Hero pose", "seated", "intermediate",
      ["Kneel and sit between your heels on a block or cushion.", "Rest your hands on your thighs.", "Sit tall and breathe."],
      "Use a high block; stop if you feel any knee pain.", dose="1-3 min", caution="Skip it if your knees complain.", muscles=["quads", "ankles"]),
    P("dandasana", "Dandasana", "Staff pose", "seated", "beginner",
      ["Sit with your legs straight in front and your hands by your hips.", "Press your thighs down and lengthen your spine."],
      "Sit on a blanket if your lower back rounds.", dose="30 sec", muscles=["posture"]),
    P("table-top", "Bharmanasana", "Tabletop", "spine", "beginner",
      ["Come onto hands and knees with wrists under shoulders and knees under hips.", "Keep your spine neutral and your neck long."],
      "A starting position for cat and cow.", cool=True, dose="5 breaths", muscles=["core", "shoulders"]),
    P("uttana-shishosana", "Uttana Shishosana", "Melting heart (puppy pose)", "spine", "beginner",
      ["From tabletop, walk your hands forward and lower your chest.", "Keep your hips over your knees.", "Rest your forehead on the floor."],
      "Keep the dip small, with your hips high.", dose="30 sec", caution="Keep the dip small and your hips over your knees.", muscles=["shoulders", "spine"]),
    P("wide-knee-childs-pose", "Balasana (wide)", "Wide-knee child's pose", "restorative", "beginner",
      ["Kneel with your big toes together and knees wide.", "Sit back and fold forward, arms long.", "Rest your forehead on a cushion."],
      "Gives your belly and pelvic floor room to soften.", cool=True, dose="1-2 min", muscles=["hips", "lower back"]),
    P("goddess-pose", "Utkata Konasana", "Goddess pose", "standing", "intermediate",
      ["Step your feet wide, toes turned out.", "Bend your knees over your ankles.", "Hands at your chest or on your thighs, back tall."],
      "Keep the squat shallow.", caution="Keep it shallow and your pelvic floor soft; don't bear down.", dose="15-20 sec", muscles=["legs", "hips"]),
    P("lizard", "Utthan Pristhasana", "Lizard lunge", "hips", "intermediate",
      ["From a low lunge, lower your hands inside your front foot.", "Rest on your forearms or on blocks.", "Keep your back knee down."],
      "Rest on blocks; stay within a mild stretch.", dose="30 sec each side", muscles=["hips", "hip flexors"]),
    P("skandasana", "Skandasana", "Side lunge", "hips", "intermediate",
      ["Step your feet wide.", "Shift into one bent knee while the other leg stays straight.", "Rest your hands on a block or your thigh."],
      "Keep your chest tall and the depth small.", dose="20 sec each side", caution="Keep your torso upright; no twisting.", muscles=["inner thighs", "quads"]),
    P("mandukasana", "Mandukasana", "Frog pose", "hips", "advanced",
      ["On hands and knees, slide your knees wide and sink your hips back."], "A strong hip and pelvic floor stretch.", unsafe="extreme",
      dose="20 sec", muscles=["inner thighs", "hips"]),
    P("parighasana", "Parighasana", "Gate pose", "standing", "intermediate",
      ["Kneel and extend one leg to the side.", "Reach your arm over and bend to the side."], "Side-bend loads the flank; it's a modest stretch.",
      dose="20 sec each side", caution="Side-bending loads the flank: keep it small, especially on your left.", muscles=["sides of waist"]),
    P("seated-side-bend", "Parsva Sukhasana", "Seated side bend", "seated", "beginner",
      ["Sit in an easy cross-legged seat.", "Rest one hand beside your hip and reach the other arm over.", "Keep both hips on the floor; switch sides."],
      "Keep the bend small.", dose="30 sec each side", caution="Side-bending loads the flank: keep it small, especially on your left.", muscles=["sides of waist"]),
    P("neck-rolls", "Neck stretch", "Gentle neck release", "mobility", "beginner",
      ["Sit or stand tall with your shoulders relaxed.", "Tip your right ear toward your right shoulder and hold for 3 breaths.", "Return to center and tip to the left."],
      "Keep it slow and small; no big circles.", cool=True, dose="3 breaths each side", muscles=["neck"]),
    P("shoulder-rolls", "Shoulder rolls", "Shoulder rolls", "mobility", "beginner",
      ["Sit or stand tall.", "Lift your shoulders toward your ears, roll them back and down.", "Do 5 slow rolls, then reverse."],
      "Move slowly with your breath.", cool=True, dose="5 each way", muscles=["shoulders", "upper back"]),
    P("wrist-release", "Wrist release", "Wrist and forearm stretch", "mobility", "beginner",
      ["On hands and knees, turn your hands so your fingers point toward your knees.", "Rock back slightly until you feel a stretch in your forearms."],
      "Take it slowly; stop short of pain.", dose="30 sec", muscles=["wrists", "forearms"]),
    P("makarasana", "Makarasana", "Crocodile (belly-breathing rest)", "restorative", "beginner",
      ["Lie on your belly, forearms stacked under your forehead.", "Let your belly press softly into the floor as you inhale.", "Let it soften on the exhale."],
      "A classic for learning to relax your pelvic floor and belly.", cool=True, dose="2-3 min", caution="Skip it if lying on your belly is uncomfortable for your kidney area.",
      muscles=["diaphragm", "pelvic floor"]),

    # Breathing: no holds, long exhales
    P("diaphragmatic-breathing", "Diaphragmatic breathing", "Belly breathing", "breath", "beginner",
      ["Lie on your back with your knees bent. Rest one hand on your belly and one on your chest.", "Breathe in through your nose so your belly rises, with your chest almost still.",
       "Let your belly fall as you breathe out slowly through soft lips.", "Let your pelvic floor drop and soften with each inhale."],
      "Count 4 in, 6 out. No holds.", cool=True, dose="3-5 min", muscles=["diaphragm", "pelvic floor"]),
    P("extended-exhale", "Extended exhale breathing", "Long-exhale breathing", "breath", "beginner",
      ["Sit or lie comfortably.", "Breathe in through your nose for a count of 4.", "Breathe out gently for a count of 6 to 8, making the exhale long and soft.",
       "Keep your jaw and belly relaxed. Repeat for several minutes."],
      "If you feel dizzy, go back to normal breathing.", cool=True, dose="3-5 min", muscles=["nervous system"]),
    P("humming-breath", "Bhramari", "Humming breath", "breath", "beginner",
      ["Sit tall and take a gentle breath in through your nose.", "Breathe out slowly with a soft hum, lips lightly closed.", "Feel the vibration in your face and chest. Repeat 6-8 times."],
      "Keep the hum soft and low.", cool=True, dose="6-8 breaths", muscles=["nervous system"]),
    P("alternate-nostril", "Nadi Shodhana", "Alternate-nostril breathing (no holds)", "breath", "beginner",
      ["Sit tall. Close your right nostril with your thumb and breathe in through the left.", "Switch: close the left with your ring finger and breathe out through the right.",
       "Breathe in through the right, switch, and breathe out through the left. That's one round.", "Never hold your breath; keep the breath slow and even. 5-8 rounds."],
      "If your nose is blocked, breathe normally instead.", cool=True, dose="5-8 rounds", muscles=["nervous system"]),
]


# Pictures for text-only poses, bundled in static/yoga-extra (free licences from Wikimedia Commons, resized)
# slug -> (artist, licence, page)
EXTRA_PHOTOS = {
    "apanasana": ("Flora-Victoria", "CC0", "https://commons.wikimedia.org/wiki/File:Hatha_Yoga,_Pawanmuktasana,_Zhengzhou,_China.JPG"),
    "ananda-balasana": ("Christy Collins", "CC BY-SA 3.0", "https://commons.wikimedia.org/wiki/File:IMG_0377_2_Happy_Baby.jpg"),
    "viparita-karani": ("Shixart1985", "CC BY 2.0", "https://commons.wikimedia.org/wiki/File:Woman_reading_a_book._Legs_up_the_wall_pose.jpg"),
    "supta-baddha-konasana": ("Trollderella (cropped by Ludmiła Pilecka)", "CC BY-SA 2.0", "https://commons.wikimedia.org/wiki/File:Supta_baddha_konasana_variation.jpg"),
    "tadasana": ("Kennguru", "CC BY 3.0", "https://commons.wikimedia.org/wiki/File:Tadasana_Yoga-Asana_Nina-Mel.jpg"),
    "dandasana": ("Thamizhpparithi Maari", "CC BY-SA 3.0", "https://commons.wikimedia.org/wiki/File:A_style_of_Dandasana.JPG"),
    "goddess-pose": ("Loveobx23", "CC BY-SA 3.0", "https://commons.wikimedia.org/wiki/File:2007-08-24_ytc_hawaii_5821.jpg"),
    "janu-sirsasana": ("Nicholas A. Tonelli", "CC BY 2.0", "https://commons.wikimedia.org/wiki/File:Flickr_-_Nicholas_T_-_Long-Named_Pose.jpg"),
    "makarasana": ("Satheesan.vn", "CC BY-SA 3.0", "https://commons.wikimedia.org/wiki/File:Crocodile_pose.JPG"),
    "parighasana": ("Nikiwiki242", "CC BY-SA 4.0", "https://commons.wikimedia.org/wiki/File:Gate_Pose.jpg"),
    "prasarita-padottanasana": ("LYUbdevanshi77", "CC0", "https://commons.wikimedia.org/wiki/File:Devanshi_Chatrasan.jpg"),
    "sukhasana": ("lululemon athletica", "CC BY 2.0", "https://commons.wikimedia.org/wiki/File:Cross-legged_sitting,_female.jpg"),
    "upavistha-konasana": ("LYUbdevanshi77", "CC0", "https://commons.wikimedia.org/wiki/File:Devanshi_Ugrasan.jpg"),
    "wrist-release": ("BruceBlaus", "CC BY-SA 4.0", "https://commons.wikimedia.org/wiki/File:Exercise_Wrist_Flexor_Stretch.png"),
}


def media_base():
    """Where the page loads yoga pictures from: this add-on (private B2 bucket) or a public address from Settings.
    The relative path keeps working behind Home Assistant ingress."""
    import media
    if media.configured():
        return "api/media/yoga"
    return (library.load_settings().get("media_base_url") or "").rstrip("/")


def _yoga_card(p):
    base = media_base()
    n = PHOTOS.get(p["slug"], 0)
    images = [f"{base}/{p['slug']}-{i}.jpg" for i in range(1, n + 1)] if base else []
    credit = None
    extra = EXTRA_PHOTOS.get(p["slug"])
    if extra and not images:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "yoga-extra", f"{p['slug']}.jpg")
        if os.path.exists(path):
            images = [f"static/yoga-extra/{p['slug']}.jpg"]
            credit = f"Photo: {extra[0]}, {extra[1]}, via Wikimedia Commons (resized)"
    unsafe = p["unsafe"]
    warning = _WHY[unsafe] if unsafe else p["caution"]
    return {
        "name": f"{p['english']} ({p['sanskrit']})", "dose": p["dose"], "sets": 1, "why": None,
        "images": images[:2], "gallery": images if not credit else [], "image_note": None,
        "steps": p["steps"] + [BREATH], "tips": [p["tip"]], "safe": not unsafe, "warning": warning,
        "muscles": p["muscles"], "equipment": "bodyweight", "level": p["level"],
        "sources": ["Yoga", PHOTO_SOURCE] if images and not credit else ["Yoga"], "credit": credit,
        "category": p["cat"], "cooldown": bool(p["cool"]) and not unsafe,
    }


# --- Baduanjin (Eight Pieces of Brocade) qigong, adapted for the kidney and pelvic floor ---------------------

QIGONG = [
    ("Baduanjin 1: Two Hands Hold Up the Heavens", [
        "Stand with feet shoulder-width apart, knees soft, hands low in front of your belly.",
        "Interlace your fingers, palms up, and slowly raise your hands to chest height as you inhale.",
        "Turn your palms up and press toward the sky, lifting only as far as is comfortable.",
        "Exhale and let your hands float down. Repeat 6-8 times."], "Lift gently; don't arch your lower back."),
    ("Baduanjin 2: Draw the Bow to Shoot the Eagle", [
        "Step out into a shallow stance, knees only slightly bent.",
        "Cross your arms in front of your chest and extend one arm to the side as if drawing a bow.",
        "Turn your head only to look over the extending hand; keep your hips and chest facing forward.",
        "Return to center and switch sides. 4 each side."], "Kidney-safe change: only your head turns; your hips stay square."),
    ("Baduanjin 3: Separate Heaven and Earth", [
        "Stand with feet shoulder-width apart.",
        "Raise one palm up overhead while the other presses down beside your hip.",
        "Stretch long through both arms without leaning to the side.",
        "Switch hands. 6 each side."], "Keep your ribs stacked over your hips; no side bend."),
    ("Baduanjin 4: Wise Owl Gazes Backward", [
        "Stand tall with arms relaxed by your sides, palms turned back.",
        "Turn only your head slowly to look over one shoulder.",
        "Return to center and look over the other shoulder.",
        "Breathe slowly. 5 each side."], "Kidney-safe: turn the head only. Keep your shoulders and hips facing forward."),
    ("Baduanjin 5: Sway the Head and Shake the Tail", [
        "Stand with feet wide and knees slightly bent, hands resting on your thighs.",
        "Tip your head gently side to side and let your upper body sway softly.",
        "Keep your hips square and your motion small and loose.",
        "Come back to center. 6-8 sways."], "Skip the deep forward fold of the original; keep it a small, relaxed sway."),
    ("Baduanjin 6: Two Hands Climb the Feet to Strengthen the Kidneys", [
        "Stand with feet shoulder-width apart.",
        "Slide your hands down your legs as far as is comfortable, knees soft.",
        "Hands on your lower back, rub gently up and down your waist.",
        "Rise slowly. Repeat 6 times."], "Fold only as far as is comfortable; skip the backward arch of the original."),
    ("Baduanjin 7: Clench Fists and Glare Fiercely", [
        "Take a shallow stance and make loose fists at your sides.",
        "Slowly punch one fist forward at chest height, exhaling.",
        "Pull it back as you punch with the other hand.",
        "Keep your shoulders loose. 6 each side."], "Keep your stance shallow and your pelvic floor soft; don't brace."),
    ("Baduanjin 8: Bouncing on the Toes", [
        "Stand tall with your feet together.",
        "Rise slowly onto your toes as you inhale.",
        "Let your heels lower softly to the floor as you exhale.",
        "Keep the movement tiny and gentle. 7 times."], "Lower your heels softly; no hard drops."),
]


QIGONG_CREDIT = "Baduanjin photos: Alexander Callegari, CC BY-SA 3.0 de, via Wikimedia Commons (resized)."
# Pictures show the traditional movement; these moves are done differently here for the left kidney
_QIGONG_NOTES = {
    4: "The picture shows the traditional full turn. Your version turns the head only, hips and chest facing forward.",
    5: "The picture shows a deep side bend. Your version is a small, loose sway only.",
    6: "The picture shows the full fold. Fold only as far as is comfortable, and skip any backward arch.",
    8: "The picture shows the standing posture around the move. The movement itself is a slow rise onto your toes and a soft lowering.",
}


def qigong_session(seconds_per_move=45):
    """Spoken script for a guided Baduanjin session: a short intro, each move with its kidney-safe cue and quiet time
    to do it, and a breathing finish. Returns segments for tts.start_session and the matching cards."""
    cards_ = [_qigong_card(*q, n=i) for i, q in enumerate(QIGONG, 1)]
    segments = [{"text": "Welcome to your Baduanjin practice. Stand with your feet shoulder-width apart, knees soft, "
                         "belly soft. Breathe slowly through your nose, with long, easy exhales.", "hold": 8}]
    for i, (name, steps, tip) in enumerate(QIGONG, 1):
        title = name.split(":", 1)[1].strip()
        segments.append({"text": f"Move {i}. {title}. " + " ".join(steps) + f" {tip} Begin now, slowly, with your breath.",
                         "hold": seconds_per_move})
    segments.append({"text": "Well done. Let your arms hang. Close your eyes if you like, and take a few slow breaths, "
                             "letting each exhale be a little longer than the inhale.", "hold": 30})
    return segments, cards_


def guided_segments(cards_, seconds=45):
    """Any list of cool-down cards as a spoken session: each one read out, then quiet time to do it. One-sided poses
    get a left side and a right side. Returns (segments for tts.start_session, picture steps for the player)."""
    segments = [{"text": "Time to cool down. Find a quiet spot, let your breathing slow, and keep your belly soft.", "hold": 5}]
    steps = [{"name": "Getting ready", "image": None}]
    for c in cards_:
        name = c["name"]
        spoken = name.split(":", 1)[1].strip() if name.startswith("Baduanjin") else name.split(" (")[0]
        body = " ".join(s for s in c.get("steps", []) if s != BREATH)
        tip = (c.get("tips") or [""])[0]
        hold = 60 if c.get("category") == "breath" else 90 if c.get("category") == "recovery tool" else seconds
        pic = {"name": name, "image": (c.get("images") or [None])[0], "note": c.get("image_note") or c.get("warning")}
        if "each side" in (c.get("dose") or ""):
            segments.append({"text": f"{spoken}. {body} {tip} Start with your left side.", "hold": hold})
            steps.append(dict(pic, name=f"{name}: left side"))
            segments.append({"text": "Now switch to your right side.", "hold": hold})
            steps.append(dict(pic, name=f"{name}: right side"))
        else:
            segments.append({"text": f"{spoken}. {body} {tip} Begin now.", "hold": hold})
            steps.append(pic)
    segments.append({"text": "That's your cool-down. Take one more slow breath, and well done today.", "hold": 3})
    steps.append({"name": "Finished", "image": None})
    return segments, steps


def _qigong_card(name, steps, tip, n=0):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "qigong", f"{n}.jpg")
    images = [f"static/qigong/{n}.jpg"] if n and os.path.exists(path) else []
    return {
        "name": name, "dose": "6-8 slow repeats", "sets": 1, "why": None, "images": images, "gallery": images,
        "image_note": _QIGONG_NOTES.get(n) if images else None,
        "steps": steps + [BREATH], "tips": [tip], "safe": True, "warning": None, "muscles": ["whole body"],
        "equipment": "bodyweight", "level": "beginner", "sources": ["Baduanjin qigong"] + (["Photo: A. Callegari, CC BY-SA 3.0 de"] if images else []),
        "category": "qigong", "cooldown": True,
    }


def cards():
    return {"yoga": [_yoga_card(p) for p in YOGA], "qigong": [_qigong_card(*q, n=i) for i, q in enumerate(QIGONG, 1)],
            "media_base": media_base(), "qigong_credit": QIGONG_CREDIT}


def _breathing(c):
    return [y for y in c["yoga"] if y["category"] == "breath" and y["cooldown"]]


# Recovery equipment from Joe's gym. His PT said both can help and Joe finds them fine at any symptom level (helpful
# when he is tight), so they are never gated on symptoms; short sessions, skipped when untoggled in Settings.
_TOOL_WARNING = {
    "vibration plate": "Lowest setting only and short. Step off if you feel dizzy or any sharp pain.",
    "inversion table": "Shallow angle only and short. Come up slowly, and stop at any pressure in your head, dizziness or sharp pain.",
}


def _tool(name, equipment, dose, steps, tip, muscles):
    return {"name": name, "dose": dose, "sets": 1, "why": None, "images": [], "gallery": [], "image_note": None,
            "steps": steps + [BREATH], "tips": [tip], "safe": True, "warning": _TOOL_WARNING[equipment],
            "muscles": muscles, "equipment": equipment, "level": "beginner", "sources": ["Recovery equipment"],
            "category": "recovery tool", "cooldown": True, "credit": None}


def tool_cards(equipment, kind):
    """Recovery-equipment cards for `kind` ("warmup" or "cooldown"); empty if you don't have the equipment ticked."""
    equipment = set(equipment or [])
    out = []
    if "vibration plate" in equipment:
        if kind == "warmup":
            out.append(_tool("Vibration board primer", "vibration plate", "60-90 sec, lowest setting",
                             ["Stand on the board, feet hip-width apart, knees soft.", "Start it on the lowest setting.",
                              "Stand for 30 seconds, then do 5 slow, shallow mini-squats.", "Step off slowly when the time is up."],
                             "A quick wake-up for the legs before strength work. Keep it short.", ["legs", "calves"]))
        else:
            out.append(_tool("Vibration board leg release", "vibration plate", "2-3 min, lowest setting",
                             ["Stand on the board with soft knees, or sit on a chair with your feet on it.", "Start on the lowest setting.",
                              "Let your calves, thighs and feet relax. Don't grip.", "Step off slowly."],
                             "Short and easy. More is not better here.", ["calves", "legs"]))
    if "inversion table" in equipment and kind == "cooldown":
        out.append(_tool("Inversion table decompression", "inversion table", "1-3 min, shallow angle",
                         ["Set the table to a shallow angle, about 20 to 30 degrees, nowhere near upside down.",
                          "Strap in as the table's instructions say and cross your arms over your chest.",
                          "Hang loosely for 1 to 3 minutes, belly soft.", "Come back up slowly and sit for 30 seconds before standing."],
                         "Use it after training, never before. Ask your PT about the angle that suits you.", ["spine", "back"]))
    return out


def cooldown(kidney=0, pelvic_floor=0, minutes=8, focus="strength", day=None, equipment=None):
    """A short wind-down that follows the day and changes every day (seeded by the date, so it is stable all day):
    yoga after strength, qigong or a yoga flow plus breathing after cardio, restorative yoga and breathing on
    recovery and rest days. Rest and breathing only when symptoms are high."""
    c = cards()
    rng = random.Random(str(day or datetime.date.today()))
    high = (kidney or 0) > 6 or (pelvic_floor or 0) > 7
    breathing = _breathing(c)
    yoga = [y for y in c["yoga"] if y["cooldown"]]

    def by_cat(*cats):
        return [y for y in yoga if y["category"] in cats]

    tools = tool_cards(equipment, "cooldown")   # fine at any symptom level; Joe finds them helpful when he is tight

    def with_tool(cards_, prefer=None):
        # one piece of recovery equipment at the end: always on tight or recovery days, otherwise every other day
        if tools and (high or focus in ("recovery", "rest") or rng.random() < 0.5):
            pick = [t for t in tools if prefer and prefer in t["name"].lower()] or tools
            return cards_ + [dict(rng.choice(pick))]
        return cards_

    if high or focus in ("recovery", "rest"):
        calm = by_cat("restorative")
        base = [dict(y) for y in (rng.sample(calm, min(3, len(calm))) + rng.sample(breathing, min(2, len(breathing))))]
        return with_tool(base, "inversion")
    if focus == "cardio":
        style = rng.choice(["qigong_a", "qigong_b", "qigong_all", "flow", "combo"])
        q = c["qigong"]
        if style == "qigong_a":
            picks = [q[i] for i in (0, 2, 4, 6)]
        elif style == "qigong_b":
            picks = [q[i] for i in (1, 3, 5, 7)]
        elif style == "qigong_all":
            picks = list(q)
        elif style == "combo":   # a few qigong moves and a few yoga poses
            picks = [q[i] for i in sorted(rng.sample(range(8), 3))] + [rng.choice(by_cat("spine")), rng.choice(by_cat("hips"))]
        else:   # a yoga flow for the hips and spine instead of qigong
            picks = [rng.choice(by_cat("spine")), rng.choice(by_cat("hips")), rng.choice(by_cat("forward fold")),
                     rng.choice(by_cat("restorative"))]
        return with_tool([dict(p) for p in picks] + [dict(rng.choice(breathing))], "vibration")
    # after strength: one pose from each of spine, folds, hips and rest, different poses on different days
    picks = []
    for cats in (("spine",), ("strength",), ("forward fold",), ("hips",), ("restorative",)):
        pool = [y for y in by_cat(*cats) if y not in picks]
        if pool:
            picks.append(rng.choice(pool))
    return with_tool([dict(p) for p in picks], "vibration")


def cooldown_note(kidney=0, pelvic_floor=0, focus="strength", cards_=None):
    if (kidney or 0) > 6 or (pelvic_floor or 0) > 7:
        return "Symptoms were high last time, so this is rest and breathing only."
    names = [c["name"] for c in (cards_ or [])]
    extra = " The vibration board or inversion table is included today (low setting, short)." if any(
        c.get("category") == "recovery tool" for c in (cards_ or [])) else ""
    if focus == "cardio":
        moves = sum(1 for n in names if n.startswith("Baduanjin"))
        yoga = sum(1 for c in (cards_ or []) if c.get("category") not in ("qigong", "breath", "recovery tool"))
        if moves and yoga:
            return f"A mix: {moves} qigong moves and {yoga} yoga poses, then breathing. It changes every day." + extra
        if moves:
            which = "all eight moves" if moves == 8 else f"{moves} of the 8 moves"
            return f"Baduanjin qigong, {which} in kidney-safe form, then breathing. It changes every day." + extra
        return "A yoga flow for the hips and spine, then a breathing practice. It changes every day." + extra
    if focus in ("recovery", "rest"):
        return "A recovery day: restful poses and breathing. A guided meditation (Mind & Body tab) fits well too." + extra
    return "A gentle wind-down chosen for your kidney and pelvic floor. Different poses each day. Skip it any day you like." + extra
