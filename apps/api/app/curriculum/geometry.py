"""Euclidean and coordinate geometry, ages 12–14. Quest codes match the blueprint."""

from app.curriculum.shape import course, ladder, ordering, quest, rubric, standard, traps, unit

COMPETENCIES = [
    ("axioms", "A claim must chain back to an axiom, not to a picture that only looks equal."),
    ("rigid-motion", "Congruence is a rigid motion that does not stretch the shape."),
    ("congruence-lock", "SSS and SAS lock one triangle. AAA and SSA do not."),
    ("similarity", "A dilation keeps angles and makes constant side ratios."),
    ("trig-ratio", "Sine, cosine, and tangent are ratios inside similar right triangles."),
    ("coordinate-proof", "Slope and distance can prove a quadrilateral on the grid."),
    ("circles", "Inscribed angles, circle equations, and volume extend the same logic."),
]


def _bridge_truss() -> dict:
    """GEO-U2-Q2 written beats, including the ordering proof."""
    beats = [
        {
            "role": "mystery_hook",
            "bloom_level": "analyze",
            "cognitive_load": "medium",
            "prompt": (
                "Two bridge trusses both have 60-60-60 angles (AAA). "
                "Are they guaranteed congruent clones?"
            ),
            "rubric": rubric(
                ("not-size", "Says no, AAA does not lock size.", 50),
                (
                    "similarity",
                    "Side lengths can scale while angles stay 60 degrees, so this is similarity rather than congruence.",
                    50,
                ),
            ),
            "misconception_map": traps(
                (
                    "zoom",
                    "Matching angles mean the bridges are the same size.",
                    "A zoom lens keeps the angles and changes the size.",
                )
            ),
            "hint_ladder": ladder(
                "If you zoom a photo, which measurements stay the same?",
                "Two equilateral frames can share every angle and still be a model and a full-size bridge.",
                "AAA locks ____, not ____. That is similarity, not congruence.",
            ),
            "widget": None,
        },
        {
            "role": "interactive_toy",
            "bloom_level": "analyze",
            "cognitive_load": "medium",
            "prompt": (
                "With 8 m and 5 m beams and a 30 degree angle, why does SAS "
                "(included elbow hinge) lock one triangle while SSA (non-included angle) fails?"
            ),
            "rubric": rubric(
                (
                    "swing",
                    "The shorter side at the unlocked hinge swings like a pendulum and can hit the base in two places.",
                    100,
                )
            ),
            "misconception_map": traps(
                (
                    "zero",
                    "SSA always makes zero triangles.",
                    "The ambiguous case can make two triangles, not none.",
                ),
                (
                    "angles-never",
                    "Angles never have anything to do with locking sides.",
                    "An included angle is exactly what makes SAS lock.",
                ),
            ),
            "hint_ladder": ladder(
                "Is the 30 degree angle sandwiched between the two given sides, or hanging off one end?",
                "A door on a hinge can slam shut in two places if the hinge is not the included elbow.",
                "The shorter side swings and can meet the base in ____ places.",
            ),
            "widget": {
                "type": "single",
                "prompt": (
                    "With 8 m and 5 m beams and a 30 degree angle, why does SAS lock one triangle while SSA fails?"
                ),
                "choices": [
                    {
                        "id": "none",
                        "text": "SSA makes 0 triangles.",
                        "misconception": "SSA does not always make zero triangles. The swinging side can land twice.",
                    },
                    {
                        "id": "swing",
                        "text": "The shorter side at the unlocked hinge swings like a pendulum and hits the base in two places, acute or obtuse.",
                        "misconception": "",
                    },
                    {
                        "id": "never",
                        "text": "Angles never lock sides.",
                        "misconception": "An included angle is what lets SAS lock the third vertex.",
                    },
                ],
                "answer": "swing",
                "explain": False,
                "misconception": "Look at where the hinge sits, not at whether angles matter at all.",
            },
        },
        {
            "role": "diagnostic_gate",
            "bloom_level": "apply",
            "cognitive_load": "high",
            "prompt": (
                "Order the 4 steps of a two-column SAS proof for triangle ABC congruent to triangle ADC "
                "sharing central beam AC, and explain why AC congruent to AC (reflexive property) is needed."
            ),
            "rubric": rubric(
                (
                    "sequence",
                    "The order is Given, then Angle Bisector, then Reflexive Shared Side, then SAS.",
                    60,
                ),
                (
                    "shared",
                    "Explains the shared wall AC is the second side sandwiching the angle.",
                    40,
                ),
            ),
            "misconception_map": traps(
                (
                    "skip-shared",
                    "SAS can be named without the shared side, because the picture shows it.",
                    "The reflexive side is the second side of the included angle.",
                )
            ),
            "hint_ladder": ladder(
                "Which statement is a fact you were handed, and which one is the same segment used twice?",
                "You cannot sandwich an angle with only one slice of bread.",
                "The shared wall AC is the ____ side around the angle.",
            ),
            "widget": ordering(
                "Order the 4 steps of the two-column SAS proof.",
                [
                    ("given", "Given: the stated pieces of the bridge."),
                    ("bisector", "Angle bisector: the included angle is split into two congruent angles."),
                    ("reflexive", "Reflexive shared side: AC is congruent to AC."),
                    ("sas", "SAS: two sides and the included angle lock triangle ABC congruent to triangle ADC."),
                ],
                ["given", "bisector", "reflexive", "sas"],
                explain=True,
                misconception="Start from what is given, then the bisector, then the shared side, then SAS.",
            ),
        },
        {
            "role": "feynman_flip",
            "bloom_level": "evaluate",
            "cognitive_load": "high",
            "prompt": (
                "Rookie Architect Bot claims PQ congruent to XY, QR congruent to YZ, and angle P congruent "
                "to angle X proves SAS. Audit the bot. Show that PQ and QR meet at Q, so angle P is invalid SSA, "
                "and specify angle Q congruent to angle Y instead."
            ),
            "rubric": rubric(
                (
                    "ssa",
                    "Shows PQ and QR meet at Q, so angle P is not the included angle and the claim is SSA.",
                    50,
                ),
                (
                    "angle-q",
                    "Specifies angle Q congruent to angle Y as the included angle that would make SAS.",
                    50,
                ),
            ),
            "misconception_map": traps(
                (
                    "any-angle",
                    "Any angle in the triangle can stand in for the included angle.",
                    "SAS names the angle between the two sides you were given.",
                )
            ),
            "hint_ladder": ladder(
                "Where do the two named sides touch, and where is the named angle?",
                "The elbow of the hinge has to be the corner where those two beams meet.",
                "The sides meet at ____, so the included angle is angle ____.",
            ),
            "widget": None,
        },
    ]
    return quest(
        "GEO-U2-Q2",
        "Bridge Truss Locks: Why SSS and SAS Lock While AAA and SSA Fail",
        "core",
        ["GEO-U2-Q1"],
        ["congruence-lock", "rigid-motion"],
        "At dinner, ask why two bridges with the same angles can still be different sizes.",
        beats,
    )


def geometry_course() -> dict:
    return course(
        "geometry",
        "Euclidean and Coordinate Geometry I: Visual Logic, Proofs and Space",
        "12-14",
        "Common Core CCSS.MATH.HSG",
        COMPETENCIES,
        [
            unit(
                1,
                "Points, Lines, Angles and Deductive Logic",
                "Looking equal is not proof. Claims must chain to axioms.",
                "A picture that looks equal is not a proof. Every later congruence and similarity claim has to chain back to an axiom the way this unit chains angles.",
                [
                    standard(
                        "GEO-U1-Q1",
                        "Segment Addition",
                        "core",
                        [],
                        ["axioms"],
                        "Ask why a point between the ends of a segment lets you add the two pieces.",
                        hook="Point B sits between A and C on a straight segment. The picture looks like AB + BC = AC. Why is that a postulate you may use, not a guess from the drawing?",
                        hook_pair=(
                            ("between", "B is between A and C, so the pieces meet only at B and cover AC."),
                            ("postulate", "The equality is the segment-addition postulate, not a measurement you eyeball."),
                        ),
                        hook_hints=(
                            "What would a bent path do to the sum?",
                            "Two rods butted end to end on a straight line.",
                            "Between means ____. The license to add them is the ____.",
                        ),
                        hook_trap=("eyeball", "If it looks equal on the screen, the lengths are proved.", "A picture is not the postulate."),
                        toy_prompt="AB is 3 and BC is 5, with B between A and C. What is AC, and why may you add?",
                        choices=[
                            ("eight-guess", "8, because the picture looks about 8.", "Looking is not the reason."),
                            ("eight-postulate", "8, by the segment-addition postulate.", ""),
                            ("two", "2, because you always subtract the pieces.", "Between means the pieces add, not subtract."),
                        ],
                        answer="eight-postulate",
                        toy_trap=("subtract", "Collinear pieces are combined by subtraction.", "Subtraction is what you do when a piece is cut off a known whole."),
                        gate="Why does a ruler drawing of AB + BC still fail as a proof if you never name the betweenness?",
                        gate_pair=(
                            ("need-between", "Without betweenness, the two pieces might overlap or leave a gap."),
                            ("not-ink", "Ink on the page is not a reason in the proof."),
                        ),
                        gate_hints=(
                            "Where could B sit if you do not say between?",
                            "Two sticks can cross or leave a hole if you never say they meet end to end.",
                            "You need betweenness because ____. The drawing fails because ____.",
                        ),
                        gate_trap=("ink", "A careful sketch is a proof.", "The chain has to name the postulate."),
                        flip="Sketch Bot says the segment is 8 because the pixels look right. Teach the bot segment addition from the postulate.",
                        flip_pair=(
                            ("postulate", "Names the segment-addition postulate."),
                            ("between", "Uses betweenness of B."),
                        ),
                        flip_hints=(
                            "Take the pencil away from the bot and give it the hypothesis.",
                            "A straight rod with a marked joint.",
                            "Because B is ____, AB + BC = AC by ____.",
                        ),
                        flip_trap=("pixels", "Screen length is an axiom.", "Axioms are the agreements, not the pixels."),
                    ),
                    standard(
                        "GEO-U1-Q2",
                        "Linear Pairs and Vertical Angles",
                        "core",
                        ["GEO-U1-Q1"],
                        ["axioms"],
                        "Ask why two crossing lines make the opposite angles equal without measuring them.",
                        hook="Two lines cross. One pair of adjacent angles forms a straight line. Why does that linear pair force the vertical angles to match?",
                        hook_pair=(
                            ("linear", "A linear pair sums to 180 degrees."),
                            ("vertical", "Each vertical angle is 180 minus the same neighbor, so the opposite angles are equal."),
                        ),
                        hook_hints=(
                            "What do two angles that share a straight line add to?",
                            "Two slices that both complete the same straight cracker.",
                            "The linear pair sums to ____, so the opposite angles ____.",
                        ),
                        hook_trap=("measure", "Vertical angles are equal only after you measure both.", "The equality is deduced from the linear pair."),
                        toy_prompt="Angle 1 and angle 2 are vertical angles. Angle 1 is 40 degrees. What is angle 2, and why?",
                        choices=[
                            ("fifty", "50 degrees, because vertical angles add to 90.", "They are equal, not complementary."),
                            ("forty", "40 degrees, because vertical angles are congruent.", ""),
                            ("hundred", "140 degrees, because you subtract from 180 and that is the vertical angle.", "140 is the adjacent angle, not the vertical one."),
                        ],
                        answer="forty",
                        toy_trap=("adjacent", "The angle across the intersection is the supplement.", "The supplement is next door. The vertical angle matches."),
                        gate="Explain the chain from a linear pair to congruent vertical angles without using a protractor.",
                        gate_pair=(
                            ("chain-180", "Uses the 180-degree linear pair."),
                            ("chain-equal", "Concludes the two vertical angles equal the same difference."),
                        ),
                        gate_hints=(
                            "Write the two supplements of the same angle.",
                            "If two people both need the rest of the same dollar, they need the same amount.",
                            "Both vertical angles equal 180 minus ____, so they are ____.",
                        ),
                        gate_trap=("protractor", "The chain has to include a measurement step.", "The point of the quest is a deduction."),
                        flip="Protractor Bot measured one angle and refuses to trust the opposite one. Teach the vertical-angle chain.",
                        flip_pair=(
                            ("teach-pair", "Teaches the linear pair."),
                            ("teach-vertical", "Teaches why the vertical angle matches."),
                        ),
                        flip_hints=(
                            "Show the bot the neighbor it already believes.",
                            "The leftover of a straight line is forced.",
                            "Linear pair says ____. Therefore the vertical angle ____.",
                        ),
                        flip_trap=("trust-tool", "Only a tool can know an angle.", "The theorem is the knowing."),
                    ),
                    standard(
                        "GEO-U1-Q3",
                        "Parallel Transversal Laser Grid",
                        "core",
                        ["GEO-U1-Q2"],
                        ["axioms"],
                        "Ask which angles a laser transversal makes equal when the tracks are parallel.",
                        hook="Two parallel tracks are cut by one laser transversal. Which angles match, and which theorem lets you say so without sliding the laser?",
                        hook_pair=(
                            ("corresponding", "Corresponding angles are congruent when the lines are parallel."),
                            ("reason", "The reason is the corresponding-angles postulate, or alternate interior angles that follow from it."),
                        ),
                        hook_hints=(
                            "Find the angle in the same seat at the next intersection.",
                            "The same corner of two identical crossroads.",
                            "The matching angles are ____ because the lines are ____.",
                        ),
                        hook_trap=("any", "Every angle in the grid is equal.", "Adjacent angles on the straight laser are supplements."),
                        toy_prompt="Lines m and n are parallel. A transversal makes a 70 degree corresponding angle at m. What is the corresponding angle at n?",
                        choices=[
                            ("twenty", "20 degrees.", "That does not follow from corresponding angles."),
                            ("seventy", "70 degrees, because corresponding angles are congruent.", ""),
                            ("hundred-ten", "110 degrees, because corresponding angles are supplements.", "The supplement is the adjacent angle, not the corresponding one."),
                        ],
                        answer="seventy",
                        toy_trap=("supplement", "Corresponding angles add to 180.", "Same-side interior angles are the supplements."),
                        gate="Why does dropping the parallel mark break the laser-grid equality even if the picture still looks close?",
                        gate_pair=(
                            ("needs-parallel", "The congruence needs the parallel lines."),
                            ("looks", "A picture that looks close is not the postulate."),
                        ),
                        gate_hints=(
                            "What word in the theorem is doing the work?",
                            "Two roads that almost do not meet still eventually do.",
                            "Without parallel, corresponding angles ____. Looking close ____.",
                        ),
                        gate_trap=("close-enough", "Nearly parallel is parallel for proofs.", "The postulate is exact."),
                        flip="Grid Bot copied a 70 degree angle across a transversal on lines that are not marked parallel. Audit the bot.",
                        flip_pair=(
                            ("missing", "The proof is missing the parallel lines."),
                            ("fix", "The fix is to establish parallel, or stop claiming the angles match."),
                        ),
                        flip_hints=(
                            "Which hypothesis did the bot skip?",
                            "A stamp is not valid on the wrong form.",
                            "The bot skipped ____. It may claim the match only if ____.",
                        ),
                        flip_trap=("copy", "Copying a number across a diagram is a theorem.", "The theorem has a hypothesis."),
                    ),
                    standard(
                        "GEO-U1-BOSS",
                        "Multi-Transversal Angle Maze",
                        "capstone",
                        ["GEO-U1-Q3"],
                        ["axioms"],
                        "Ask your child to chase one angle across two parallels and say the reason at each hop.",
                        hook="Two parallels are cut by two transversals. Give a two-hop chain from one angle to a far angle, naming the reason at each hop.",
                        hook_pair=(
                            ("hop", "Each hop uses vertical angles or a parallel-line angle theorem."),
                            ("end", "The far angle is identified, not just described as somewhere in the maze."),
                        ),
                        hook_hints=(
                            "Do not jump the whole maze in one word.",
                            "Cross one intersection, then slide along the parallel.",
                            "First hop: ____ because ____. Second hop: ____ because ____.",
                        ),
                        hook_trap=("one-word", "Saying corresponding once solves a two-transversal maze.", "Each crossing needs its own reason."),
                        toy_prompt="Which chain is a valid reason across parallels?",
                        choices=[
                            ("looks", "They look equal on the page.", "Looking is not a reason."),
                            ("corresponding", "Corresponding angles on the parallel cut are congruent.", ""),
                            ("add", "All angles in the maze add to the first angle.", "Angles are not summed into the next angle."),
                        ],
                        answer="corresponding",
                        toy_trap=("appearance", "A clean diagram is a proof.", "The reason has to be a theorem."),
                        gate="Why must every hop in the maze cite a theorem instead of the final picture?",
                        gate_pair=(
                            ("cite", "Each equality needs a named theorem."),
                            ("picture", "The final picture can hide a non-parallel or a wrong angle pair."),
                        ),
                        gate_hints=(
                            "What would you hand a skeptic at hop two?",
                            "A trail of receipts, not a photo of the destination.",
                            "Cite a theorem because ____. The picture can hide ____.",
                        ),
                        gate_trap=("destination", "If the last angle is labeled, the middle reasons are optional.", "The chain is the proof."),
                        flip="Maze Bot jumped from the start angle to the end angle because the figure is tidy. Teach a two-hop chain with reasons.",
                        flip_pair=(
                            ("two", "Gives two hops."),
                            ("reasons", "Names a theorem on each hop."),
                        ),
                        flip_hints=(
                            "Make the bot stop at the first intersection.",
                            "Vertical, then corresponding, is a legal walk.",
                            "Hop 1 uses ____. Hop 2 uses ____.",
                        ),
                        flip_trap=("tidy", "Tidiness is the missing postulate.", "Tidiness is not a hypothesis."),
                        flip_bloom="create",
                    ),
                ],
            ),
            unit(
                2,
                "Rigid Transformations and Triangle Congruence",
                "Congruence means rigid motions map one shape onto another without stretching.",
                "Rigid motions preserve exact side lengths and angles without scaling. Congruence means one of those motions maps one triangle onto the other, which is the lock the next proofs use.",
                [
                    standard(
                        "GEO-U2-Q1",
                        "Translations, Reflections and Rotations on the Grid",
                        "core",
                        ["GEO-U1-BOSS"],
                        ["rigid-motion"],
                        "Ask which moves keep every length and angle, and which move would stretch the figure.",
                        hook="A triangle is translated, reflected, or rotated on the grid. What stays exactly the same, and what kind of change would break congruence?",
                        hook_pair=(
                            ("same", "Side lengths and angles stay the same under a rigid motion."),
                            ("stretch", "A dilation or other stretch breaks congruence."),
                        ),
                        hook_hints=(
                            "Did any side get longer, or did the triangle only move?",
                            "Sliding, flipping, or turning a cutout, versus pulling it.",
                            "Rigid motions keep ____. Stretching ____.",
                        ),
                        hook_trap=("slide-size", "A translation changes side lengths.", "A translation copies every length."),
                        toy_prompt="Which move guarantees a congruent image?",
                        choices=[
                            ("scale", "Multiply every coordinate by 2.", "That is a dilation. Lengths change."),
                            ("rotate", "Rotate 90 degrees about the origin.", ""),
                            ("stretch", "Keep x and double y.", "That stretch changes lengths and angles."),
                        ],
                        answer="rotate",
                        toy_trap=("double", "Doubling a coordinate is a rigid motion.", "Doubling is a stretch."),
                        gate="Why is 'it landed on the other triangle' not enough unless the move was rigid?",
                        gate_pair=(
                            ("cover", "Landing on top is the picture of a mapping."),
                            ("rigid", "Congruence needs a rigid motion, so the landing did not stretch anything."),
                        ),
                        gate_hints=(
                            "Could a stretched sheet still cover the outline if you allow distortion?",
                            "A rubber sheet can be forced onto a different triangle.",
                            "Covering is ____. Congruence also needs ____.",
                        ),
                        gate_trap=("cover-enough", "Any mapping that covers the shape is a congruence.", "The mapping has to preserve distance."),
                        flip="Rubber Bot stretched a triangle until it covered another and calls that a rotation. Teach the bot what a rigid motion is allowed to do.",
                        flip_pair=(
                            ("preserve", "A rigid motion preserves lengths and angles."),
                            ("not-stretch", "A stretch is not a translation, reflection, or rotation."),
                        ),
                        flip_hints=(
                            "Name the three legal moves and the one illegal pull.",
                            "Tracing paper may slide, flip, or turn. It may not be yanked.",
                            "Legal moves ____. The bot's stretch ____.",
                        ),
                        flip_trap=("cover", "Coverage is the definition of rotation.", "Rotation keeps distances."),
                    ),
                    _bridge_truss(),
                    standard(
                        "GEO-U2-Q3",
                        "ASA, AAS and Hypotenuse-Leg",
                        "core",
                        ["GEO-U2-Q2"],
                        ["congruence-lock"],
                        "Ask which extra triangle locks still count once SSS and SAS are understood.",
                        hook="ASA and AAS both use two angles and a side. What is the difference in where the side sits, and why does hypotenuse-leg need a right angle?",
                        hook_pair=(
                            ("where", "ASA includes the side between the angles. AAS uses a side that is not between them."),
                            ("right", "Hypotenuse-leg needs the right angle so the hypotenuse is the longest side in a right triangle."),
                        ),
                        hook_hints=(
                            "Draw the side relative to the two angles before you name the theorem.",
                            "The side can be the floor between two walls, or a wall that is not between them.",
                            "ASA puts the side ____. HL needs ____.",
                        ),
                        hook_trap=("same", "ASA and AAS are two names for the same picture.", "The side's seat is the difference."),
                        toy_prompt="Two angles and the included side are marked congruent. Which lock is that?",
                        choices=[
                            ("ssa", "SSA.", "SSA is two sides and a non-included angle."),
                            ("asa", "ASA.", ""),
                            ("aaa", "AAA.", "AAA has no side, so it does not lock size."),
                        ],
                        answer="asa",
                        toy_trap=("no-side", "Two angles are enough to name ASA.", "ASA includes the side between them."),
                        gate="Why may you use HL on right triangles and not on a slanted triangle with a long side and a leg?",
                        gate_pair=(
                            ("right-angle", "HL uses the right angle as known structure."),
                            ("not-oblique", "Without the right angle, a hypotenuse is not defined and the lock fails."),
                        ),
                        gate_hints=(
                            "What does the word hypotenuse require?",
                            "The longest side is only called the hypotenuse in a right triangle.",
                            "HL needs ____. A slanted triangle ____.",
                        ),
                        gate_trap=("long-side", "Any longest side may be called a hypotenuse.", "The right angle is part of the definition."),
                        flip="Label Bot stamps HL on a triangle with no right angle. Correct the stamp and say when HL would be legal.",
                        flip_pair=(
                            ("illegal", "HL is illegal without a right angle."),
                            ("legal", "HL is legal when the hypotenuse and a leg are congruent in two right triangles."),
                        ),
                        flip_hints=(
                            "Make the bot find the right-angle mark before the letters.",
                            "No square corner, no hypotenuse.",
                            "Illegal because ____. Legal when ____.",
                        ),
                        flip_trap=("letters", "Any three-letter stamp is a theorem.", "The letters name a hypothesis."),
                    ),
                    standard(
                        "GEO-U2-BOSS",
                        "CPCTC and Two-Column Bridge Proof Arena",
                        "capstone",
                        ["GEO-U2-Q3"],
                        ["congruence-lock", "rigid-motion"],
                        "Ask why matching leftover parts is legal only after the triangles are congruent.",
                        hook="You have proved two triangles congruent. A later line claims two leftover angles are congruent. What permission lets you say that, and what would make the line illegal?",
                        hook_pair=(
                            ("cpctc", "CPCTC lets corresponding parts of congruent triangles match."),
                            ("illegal", "The line is illegal if the triangles are not yet congruent, or the parts are not corresponding."),
                        ),
                        hook_hints=(
                            "Corresponding parts of what?",
                            "Once the bridges are the same bridge, matching bolts are the same bolts.",
                            "The permission is ____. It is illegal if ____.",
                        ),
                        hook_trap=("early", "CPCTC can be the first line of a proof.", "It is a consequence, not a starting lock."),
                        toy_prompt="When is CPCTC allowed?",
                        choices=[
                            ("first", "As the given, before any congruence.", "You cannot take parts from a congruence you have not proved."),
                            ("after", "After the triangles are proved congruent, for corresponding parts.", ""),
                            ("aaa", "Whenever the angles look equal.", "Looking equal is the Unit 1 trap."),
                        ],
                        answer="after",
                        toy_trap=("early-cpctc", "CPCTC is a reason you may use on line 1.", "Line 1 has to earn the congruence first."),
                        gate="In a two-column proof, why must the congruence statement appear before the CPCTC line?",
                        gate_pair=(
                            ("order", "CPCTC cites the congruence, so the congruence line comes first."),
                            ("parts", "Only then are the named parts corresponding parts of congruent triangles."),
                        ),
                        gate_hints=(
                            "What would CPCTC be pointing at if the congruence is still unproved?",
                            "You cannot claim the bolts match before you know the bridges match.",
                            "The congruence line comes first because ____. Then the parts ____.",
                        ),
                        gate_trap=("style", "Column order is a style choice.", "The order is logical dependence."),
                        flip="Arena Bot uses CPCTC to prove the triangles congruent. Reverse the bot's order and explain why.",
                        flip_pair=(
                            ("reverse", "Congruence has to be proved before CPCTC."),
                            ("why", "CPCTC takes corresponding parts from triangles already congruent."),
                        ),
                        flip_hints=(
                            "Show the bot the arrow of dependence.",
                            "The lock first, then the matching bolts.",
                            "Prove ____ first. CPCTC then gives ____.",
                        ),
                        flip_trap=("cycle", "The parts can prove the congruence that proves the parts.", "That circle is not a proof."),
                        flip_bloom="create",
                    ),
                ],
            ),
            unit(
                3,
                "Dilations, Similarity and Right-Triangle Trig",
                "Scaling preserves angles and creates constant side ratios. That is all sine, cosine, and tangent are.",
                "Congruence refused to scale. Similarity is the scaling that keeps angles and makes the side ratios we later name sine, cosine, and tangent.",
                [
                    standard(
                        "GEO-U3-Q1",
                        "AA Similarity",
                        "core",
                        ["GEO-U2-BOSS"],
                        ["similarity"],
                        "Ask why two pairs of equal angles are enough to make triangles similar, and not enough to make them congruent.",
                        hook="Two triangles each have a 40 degree angle and a 60 degree angle. Why are they similar, and why might they still not be congruent?",
                        hook_pair=(
                            ("aa", "AA gives similarity because the third angles match too."),
                            ("size", "No side is locked, so one triangle may be a scaled copy."),
                        ),
                        hook_hints=(
                            "What is 180 minus 40 minus 60 in both triangles?",
                            "The same corner angles on a small photo and a poster.",
                            "Similar because ____. Not necessarily congruent because ____.",
                        ),
                        hook_trap=("aa-congruent", "Two angles prove the triangles are the same size.", "Angles without a side do not lock size."),
                        toy_prompt="Which statement is true of two triangles with two pairs of congruent angles?",
                        choices=[
                            ("congruent", "They must be congruent.", "AA does not give a side, so size can change."),
                            ("similar", "They are similar, and a third angle pair matches.", ""),
                            ("nothing", "Two angles tell you nothing.", "The third angle is forced, so the shape is fixed."),
                        ],
                        answer="similar",
                        toy_trap=("must-congruent", "Same angles means same triangle.", "Same shape, not necessarily same size."),
                        gate="Why does AA fix the shape and leave the scale free?",
                        gate_pair=(
                            ("shape", "All three angles are determined, so the shape is fixed."),
                            ("scale", "Without a side, every length can be multiplied by the same factor."),
                        ),
                        gate_hints=(
                            "If you double every side, what happens to the angles?",
                            "A zoom keeps the corners and changes the frame.",
                            "Shape is fixed because ____. Scale is free because ____.",
                        ),
                        gate_trap=("angles-change", "Scaling a triangle changes its angles.", "Dilation preserves angles."),
                        flip="Clone Bot says AA means the bridges are congruent clones. Teach the bot what AA actually locks.",
                        flip_pair=(
                            ("locks-angles", "AA locks the angles and therefore the shape."),
                            ("not-size", "AA does not lock size."),
                        ),
                        flip_hints=(
                            "Hand the bot a small equilateral and a large one.",
                            "Same corners, different beams.",
                            "AA locks ____. It does not lock ____.",
                        ),
                        flip_trap=("clone", "Similar is a synonym for congruent.", "Similar allows a scale factor."),
                    ),
                    standard(
                        "GEO-U3-Q2",
                        "Special Right Triangles",
                        "core",
                        ["GEO-U3-Q1"],
                        ["similarity"],
                        "Ask why every 45-45-90 triangle is a scaled copy of one model, and the same for 30-60-90.",
                        hook="Every 45-45-90 triangle has the same angles. How does that tell you the side ratios without measuring a new one?",
                        hook_pair=(
                            ("similar", "They are similar by AA, so the side ratios are constant."),
                            ("model", "One model triangle's ratios transfer by the scale factor."),
                        ),
                        hook_hints=(
                            "If the angles match, what is free to change?",
                            "A set of photo enlargements of one right corner.",
                            "They are similar because ____. The ratios come from ____.",
                        ),
                        hook_trap=("new-measure", "Each new 45-45-90 triangle needs its own unrelated measurements.", "The family shares ratios."),
                        toy_prompt="The legs of a 45-45-90 triangle are each 1 in the model. What is true of a larger 45-45-90 triangle?",
                        choices=[
                            ("random", "Its hypotenuse can be any ratio to the leg.", "The ratio is fixed by similarity."),
                            ("same-ratio", "The hypotenuse is still the leg times square root of 2.", ""),
                            ("triple", "The hypotenuse is three times the leg because it is a bigger triangle.", "The scale changes both, not the ratio."),
                        ],
                        answer="same-ratio",
                        toy_trap=("grows-ratio", "A larger triangle has a larger hypotenuse-to-leg ratio.", "The ratio stays. The scale changes."),
                        gate="Explain how a 30-60-90 triangle's side ratios are a similarity fact, not a memorized trick with no reason.",
                        gate_pair=(
                            ("angles", "The angles 30, 60, and 90 force one similarity class."),
                            ("ratio", "Every such triangle is a scale of the model, so opposite the 30 the side is half the hypotenuse."),
                        ),
                        gate_hints=(
                            "What do all 30-60-90 triangles share before any side length?",
                            "One stencil, many enlargements.",
                            "The angles force ____. Therefore the sides ____.",
                        ),
                        gate_trap=("spell", "The ratios are a spelling trick with no angle reason.", "The angles are the reason."),
                        flip="Flashcard Bot recites 1 : √3 : 2 and cannot say why. Teach the bot the similarity reason.",
                        flip_pair=(
                            ("why-similar", "All 30-60-90 triangles are similar."),
                            ("why-ratio", "The ratio is the model's ratio under scaling."),
                        ),
                        flip_hints=(
                            "Start from the angles, not from the card.",
                            "The card is a photo of one model.",
                            "Similar because ____. The card's ratio survives because ____.",
                        ),
                        flip_trap=("memory", "A ratio with no angle story is the whole theorem.", "The story is AA plus scale."),
                    ),
                    standard(
                        "GEO-U3-Q3",
                        "Sin, Cos and Tan as Similarity Ratios",
                        "core",
                        ["GEO-U3-Q2"],
                        ["trig-ratio"],
                        "Ask why sine of 35 degrees is a ratio you can read from any right triangle with that angle.",
                        hook="In a right triangle, sine of an acute angle is opposite over hypotenuse. Why is that ratio the same in every right triangle with that angle?",
                        hook_pair=(
                            ("similar", "Those right triangles are similar by AA."),
                            ("ratio", "Similarity keeps the opposite-to-hypotenuse ratio constant."),
                        ),
                        hook_hints=(
                            "What else matches if the right angle and one acute angle match?",
                            "Every enlargement of the same ramp has the same steepness ratio.",
                            "They are similar by ____. So the ratio ____.",
                        ),
                        hook_trap=("size-changes-sin", "A bigger triangle has a bigger sine.", "Sine is a ratio, so the size cancels."),
                        toy_prompt="Why is sin 35° the same on a small ramp and a large ramp with the same angle?",
                        choices=[
                            ("bigger", "The large ramp has a larger sine because the opposite side is longer.", "The hypotenuse grew by the same factor."),
                            ("ratio", "The ramps are similar, so opposite over hypotenuse does not change.", ""),
                            ("degrees", "35 degrees means the opposite side is 35 long.", "The degree measure is not a length."),
                        ],
                        answer="ratio",
                        toy_trap=("length", "Sine outputs a side length.", "Sine outputs a ratio of lengths."),
                        gate="Explain tangent as a similarity ratio, and say what it compares.",
                        gate_pair=(
                            ("compares", "Tangent compares the opposite side to the adjacent side."),
                            ("constant", "The ratio is constant for a fixed acute angle because the right triangles are similar."),
                        ),
                        gate_hints=(
                            "Which two sides touch the angle you are not calling the right angle, and which one is across from it?",
                            "Rise over run on similar ramps.",
                            "Tangent compares ____ to ____, and it stays constant because ____.",
                        ),
                        gate_trap=("hyp", "Tangent uses the hypotenuse.", "The hypotenuse is in sine and cosine, not tangent."),
                        flip="Ramp Bot says sine gets bigger when the triangle gets bigger. Correct the bot using similarity.",
                        flip_pair=(
                            ("cancel", "Both opposite and hypotenuse scale, so the ratio holds."),
                            ("name", "That constant ratio is what sine means."),
                        ),
                        flip_hints=(
                            "Multiply the top and the bottom by the same scale factor.",
                            "A fraction unchanged by enlarging the photo.",
                            "The sides ____. Sine is ____.",
                        ),
                        flip_trap=("grows", "Every trig value grows with the triangle.", "The values are scale-free."),
                    ),
                    standard(
                        "GEO-U3-BOSS",
                        "Rocket Altitude",
                        "capstone",
                        ["GEO-U3-Q3"],
                        ["trig-ratio"],
                        "Ask how a ground angle and a distance give a height, and which ratio does that job.",
                        hook="You stand 40 m from a rocket launch and measure a 50 degree angle up to the nose. Which ratio turns that into a height, and what similar-triangle fact makes the ratio legal?",
                        hook_pair=(
                            ("tan", "Tangent uses opposite over adjacent, and the height is opposite the 50 degree angle."),
                            ("legal", "Any other right triangle with a 50 degree angle is similar, so tan 50° is the same ratio."),
                        ),
                        hook_hints=(
                            "Which side is the ground distance relative to the angle you measured?",
                            "The ground is the adjacent run. The rocket is the opposite rise.",
                            "Use ____ because height and 40 m are ____. It is legal because ____.",
                        ),
                        hook_trap=("sin-ground", "Sine always takes the ground distance.", "Sine would need the line of sight as the hypotenuse."),
                        toy_prompt="The angle of elevation is at your eye, and the ground distance is adjacent. Which equation fits the height h?",
                        choices=[
                            ("sin", "sin 50° = h / 40.", "That treats 40 m as the hypotenuse."),
                            ("tan", "tan 50° = h / 40.", ""),
                            ("cos", "cos 50° = h / 40.", "Cosine compares adjacent to hypotenuse, not opposite to adjacent."),
                        ],
                        answer="tan",
                        toy_trap=("wrong-pair", "Any trig name works if a 50 is in the problem.", "The side pair picks the name."),
                        gate="Why would moving farther from the rocket change the angle but not the meaning of tangent?",
                        gate_pair=(
                            ("angle", "A new distance makes a new angle in a new right triangle."),
                            ("meaning", "Tangent of that new angle is still opposite over adjacent in a similar family."),
                        ),
                        gate_hints=(
                            "You built a different triangle, not a different definition.",
                            "A new ramp, same kind of steepness ratio.",
                            "The angle changes because ____. Tangent still means ____.",
                        ),
                        gate_trap=("breaks", "Leaving the first spot makes trig stop applying.", "Every new right triangle has its own ratio of the same kind."),
                        flip="Launch Bot divides the height by the line of sight and calls it tangent. Correct the sides.",
                        flip_pair=(
                            ("not-hyp", "Tangent does not use the line of sight."),
                            ("opp-adj", "Tangent is height over ground distance here."),
                        ),
                        flip_hints=(
                            "Point at the two sides that make the angle on the ground.",
                            "Rise over run, not rise over the slant.",
                            "Not the hypotenuse. Tangent uses ____ and ____.",
                        ),
                        flip_trap=("slant", "The slanted sight line is the adjacent side.", "The adjacent side is on the ground."),
                        flip_bloom="create",
                    ),
                ],
            ),
            unit(
                4,
                "Quadrilaterals and Coordinate Proofs",
                "Classify quadrilaterals by the properties that force them, then prove those properties with slope and distance.",
                "Triangles locked by congruence and similarity now classify four-sided figures. On a coordinate grid, slope and distance take the place of a ruler.",
                [
                    standard(
                        "GEO-U4-Q1",
                        "Parallelogram Hierarchy",
                        "core",
                        ["GEO-U3-BOSS"],
                        ["coordinate-proof"],
                        "Ask which extra property turns a parallelogram into a rectangle, a rhombus, or a square.",
                        hook="Every square is a rectangle and a rhombus. What extra property does a rectangle add to a parallelogram, and what extra property does a rhombus add?",
                        hook_pair=(
                            ("rectangle", "A rectangle adds a right angle, which forces the other angles right."),
                            ("rhombus", "A rhombus adds four congruent sides."),
                        ),
                        hook_hints=(
                            "One extra is about a corner. One extra is about the edges.",
                            "A pushed box made square at the corner, versus a pushed box with equal rails.",
                            "Rectangle adds ____. Rhombus adds ____.",
                        ),
                        hook_trap=("same-extra", "Rectangle and rhombus add the same extra property.", "Angles and sides are different extras."),
                        toy_prompt="A parallelogram has one right angle. What must it be?",
                        choices=[
                            ("rhombus-only", "A rhombus, and not necessarily a rectangle.", "The right angle is the rectangle property."),
                            ("rectangle", "A rectangle.", ""),
                            ("nothing", "Still only a general parallelogram, because one angle never forces the others.", "In a parallelogram, consecutive angles are supplementary, so one right angle forces the rest."),
                        ],
                        answer="rectangle",
                        toy_trap=("one-useless", "One right angle in a parallelogram is a coincidence.", "Consecutive angles are supplements, so the rest follow."),
                        gate="Why is a square both a rectangle and a rhombus, while a rectangle need not be a rhombus?",
                        gate_pair=(
                            ("both", "A square has the right angle and the equal sides."),
                            ("not-rhombus", "A rectangle can have unequal adjacent sides, so it need not be a rhombus."),
                        ),
                        gate_hints=(
                            "List the two extras a square has.",
                            "A right-angled frame can be long and skinny.",
                            "A square has ____ and ____. A rectangle can fail to be a rhombus because ____.",
                        ),
                        gate_trap=("all-same", "Rectangle, rhombus, and square are three words for one shape.", "The hierarchy is nested, not flat."),
                        flip="Label Bot calls every rectangle a square. Teach the missing property.",
                        flip_pair=(
                            ("has", "A rectangle has a right angle."),
                            ("missing", "A square also needs four congruent sides, which a rectangle may lack."),
                        ),
                        flip_hints=(
                            "Put a long rectangle next to a square and ask which side changed.",
                            "Right corners do not force equal rails.",
                            "The rectangle has ____. It may lack ____.",
                        ),
                        flip_trap=("corners", "Right angles force all sides equal.", "They do not."),
                    ),
                    standard(
                        "GEO-U4-Q2",
                        "Coordinate Slope and Distance Proofs",
                        "core",
                        ["GEO-U4-Q1"],
                        ["coordinate-proof"],
                        "Ask how slope shows parallel or perpendicular, and how distance shows equal sides.",
                        hook="On a grid, two sides have the same slope and two adjacent sides have slopes whose product is -1. What have you proved, and what have you not yet proved about the side lengths?",
                        hook_pair=(
                            ("parallel-perp", "Equal slopes give parallel sides. A product of -1 gives perpendicular sides."),
                            ("not-length", "Slope does not show that the sides are the same length. Distance does."),
                        ),
                        hook_hints=(
                            "Slope is a direction. Length is a different measurement.",
                            "Two arrows pointing the same way, versus two arrows of the same size.",
                            "Slope proves ____. It does not prove ____.",
                        ),
                        hook_trap=("slope-is-length", "Matching slopes means matching lengths.", "A long side and a short side can share a slope."),
                        toy_prompt="Which tool shows two grid segments are congruent?",
                        choices=[
                            ("slope", "Equal slopes.", "That shows parallel direction, not equal length."),
                            ("distance", "The distance formula giving equal lengths.", ""),
                            ("look", "They look equal on the graph paper.", "Looking is not a coordinate proof."),
                        ],
                        answer="distance",
                        toy_trap=("direction", "Direction and length are the same coordinate fact.", "They use different formulas."),
                        gate="Outline a coordinate proof that a quadrilateral with the right vertices is a rectangle, naming where slope is used and where distance is not required.",
                        gate_pair=(
                            ("slope-use", "Uses equal slopes for the parallel pairs and slope product -1 for a right angle."),
                            ("enough", "A parallelogram with one right angle is a rectangle, so all four distances are not required for that claim."),
                        ),
                        gate_hints=(
                            "You already know what one right angle does inside a parallelogram.",
                            "Show the arrows are parallel, then show one corner is square.",
                            "Slope shows ____. Distance is unnecessary because ____.",
                        ),
                        gate_trap=("all-distances", "A rectangle proof must compute all four side lengths.", "The right angle plus the parallelogram properties are enough."),
                        flip="Grid Bot proves a rhombus using only slopes. Tell the bot which tool is missing.",
                        flip_pair=(
                            ("missing-distance", "A rhombus needs four equal sides, which slope does not show."),
                            ("use-distance", "The distance formula has to show the side lengths match."),
                        ),
                        flip_hints=(
                            "Ask the bot how long each side is.",
                            "Parallel rails can be different lengths. A rhombus cannot.",
                            "Slope missed ____. Compute ____.",
                        ),
                        flip_trap=("slopes-enough", "Four equal slopes would mean four equal sides.", "Slope never reports length."),
                    ),
                ],
            ),
            unit(
                5,
                "Circles",
                "Inscribed angles and circle equations still rest on distance, and volume turns that logic into a solid.",
                "Circle angle measures and a circle's equation still rest on the same distance logic. Volume is that logic turned into a solid.",
                [
                    standard(
                        "GEO-U5-Q1",
                        "Inscribed Angles and Circle Equations",
                        "core",
                        ["GEO-U4-Q2"],
                        ["circles"],
                        "Ask why an inscribed angle is half the arc, and why a circle equation is a distance statement.",
                        hook="An inscribed angle cuts the same arc as a central angle. How are their measures related, and what does (x - h)² + (y - k)² = r² say in plain language?",
                        hook_pair=(
                            ("half", "The inscribed angle is half the central angle that subtends the same arc."),
                            ("distance", "The equation says every point is distance r from the center (h, k)."),
                        ),
                        hook_hints=(
                            "One vertex is on the circumference. The other is at the center.",
                            "A slice from the rim is half the slice from the middle, and the equation is a leash of length r.",
                            "The inscribed angle is ____. The equation means ____.",
                        ),
                        hook_trap=("same-measure", "Inscribed and central angles on the same arc are equal.", "The inscribed angle is half."),
                        toy_prompt="A central angle is 80 degrees. What is the inscribed angle on the same arc?",
                        choices=[
                            ("eighty", "80 degrees.", "That copies the central angle."),
                            ("forty", "40 degrees.", ""),
                            ("hundred-sixty", "160 degrees.", "That doubles it. The inscribed angle is the smaller one."),
                        ],
                        answer="forty",
                        toy_trap=("double", "The inscribed angle is twice the central angle.", "It is half."),
                        gate="Why is graphing x² + y² = 25 a distance proof that you are on the circle, not a new kind of fact?",
                        gate_pair=(
                            ("origin", "The equation is distance from the origin equal to 5."),
                            ("same", "Being on the circle means that distance condition, so the graph is the distance statement."),
                        ),
                        gate_hints=(
                            "What does x² + y² already mean from the coordinate unit?",
                            "The Pythagorean leash from the center.",
                            "x² + y² is ____. The circle is the set of points where that equals ____.",
                        ),
                        gate_trap=("new-fact", "A circle equation has nothing to do with distance.", "It is distance."),
                        flip="Graph Bot says the inscribed angle and the central angle match because they see the same arc. Correct the factor, and say what a radius is.",
                        flip_pair=(
                            ("factor", "The inscribed angle is half the central angle."),
                            ("radius", "A radius is the fixed distance named by the circle equation."),
                        ),
                        flip_hints=(
                            "Half, not a copy.",
                            "Same arc, different vertex.",
                            "The factor is ____. A radius is ____.",
                        ),
                        flip_trap=("same-arc-same-angle", "Seeing the same arc forces the same angle measure.", "The vertex changes the measure."),
                    ),
                    standard(
                        "GEO-U5-BOSS",
                        "3D Volume",
                        "capstone",
                        ["GEO-U5-Q1"],
                        ["circles"],
                        "Ask how the area of a base and a height become a volume, and where a circle's area enters a cylinder or cone.",
                        hook="A cylinder uses the area of a circle as its base. How do you build its volume from that area, and what changes when the solid is a cone with the same base and height?",
                        hook_pair=(
                            ("cylinder", "Cylinder volume is base area times height, so πr²h."),
                            ("cone", "A cone with the same base and height has one third of that volume."),
                        ),
                        hook_hints=(
                            "Stack the circular area up through the height, then ask what a cone keeps and what it cuts away.",
                            "A stack of coins versus a party hat of the same height.",
                            "The cylinder is ____. The cone is ____.",
                        ),
                        hook_trap=("same-volume", "A cone and a cylinder with the same base and height hold the same amount.", "The cone holds one third."),
                        toy_prompt="A cylinder and a cone share a radius and a height. How do their volumes compare?",
                        choices=[
                            ("equal", "They are equal.", "The cone is the smaller solid."),
                            ("third", "The cone is one third of the cylinder.", ""),
                            ("three", "The cone is three times the cylinder.", "That flips the factor."),
                        ],
                        answer="third",
                        toy_trap=("flip-third", "The 1/3 belongs on the cylinder.", "The 1/3 belongs on the cone."),
                        gate="Why does a volume formula that starts from πr² still depend on the circle facts from the last quest?",
                        gate_pair=(
                            ("area", "πr² is the area of the circular base, which comes from the circle's radius."),
                            ("height", "Volume then multiplies or thirds that area by the height, so the circle fact is still inside the solid."),
                        ),
                        gate_hints=(
                            "Where did πr² enter the formula?",
                            "The floor of the solid is the circle you already described by distance.",
                            "πr² is ____. It stays inside the volume because ____.",
                        ),
                        gate_trap=("unrelated", "Volume formulas replace circle facts instead of using them.", "They use the area."),
                        flip="Solid Bot computes a cone by multiplying πr²h and stopping. Teach the missing factor and why the base is a circle.",
                        flip_pair=(
                            ("third-factor", "The cone needs the factor 1/3."),
                            ("base", "The base area is the circle's area, πr²."),
                        ),
                        flip_hints=(
                            "The bot built the cylinder and named it cone.",
                            "Party hat, not a stack of coins.",
                            "Multiply by ____. The πr² is ____.",
                        ),
                        flip_trap=("stop", "Base times height is every solid.", "The cone is the exception with a factor."),
                        flip_bloom="create",
                    ),
                ],
            ),
        ],
    )
